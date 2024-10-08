import asyncio
import sys
from datetime import timedelta
from uuid import UUID

from loguru import logger
from mistralai.models.embeddings import EmbeddingObject

from aiden_shared.constants import JOB_COLLECTION
from aiden_shared.models import JobOffer, ScrapeStatus
from aiden_recommender.models import Request
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers import france_travail_scraper, indeed_scraper, wtj_scraper
from aiden_recommender.scrapers.utils import cache
from aiden_shared.tools import mistral_client, qdrant_client

logger.remove()
logger.add(sys.stderr, level="INFO")


class ScraperAggregator:
    def __init__(self, max_workers=64):
        self.scrapers: list[AbstractScraper] = [
            france_travail_scraper,
            wtj_scraper,
            indeed_scraper,
        ]
        self.workers = max_workers
        self.timeout = 15
        self.request_queue = asyncio.Queue()
        self.results_queue = asyncio.Queue()
        self.active_workers = asyncio.Semaphore(self.workers)
        self.condition = asyncio.Condition()
        self.scrape_statuses = {}

    @cache(retention_period=timedelta(hours=12), model=EmbeddingObject, source="search_queries")
    def _get_search_query_vector(self, search_query: str) -> list[EmbeddingObject]:
        return mistral_client.embeddings(model="mistral-embed", input=[search_query]).data

    async def handle_request(
        self,
        request: Request,
        request_queue: asyncio.Queue,
        results_queue: asyncio.Queue,
        active_workers: asyncio.Semaphore,
        condition: asyncio.Condition,
    ):
        async with active_workers:
            async for item in request.send():
                if isinstance(item, Request):
                    await request_queue.put(item)
                elif isinstance(item, JobOffer):
                    logger.warning(f"Job offer: {item.name} - {item.source}")
                    await results_queue.put(item)

        async with condition:
            if request_queue.empty() and active_workers._value == self.workers:
                condition.notify_all()

    async def worker(self, queue: asyncio.Queue, results: asyncio.Queue, active_workers: asyncio.Semaphore, condition: asyncio.Condition):
        while True:
            request = await queue.get()
            try:
                await self.handle_request(request, queue, results, active_workers, condition)
            finally:
                queue.task_done()

    async def start_workers(self):
        logger.warning(f"Starting {self.workers} workers")
        for _ in range(self.workers):
            asyncio.create_task(self.worker(self.request_queue, self.results_queue, self.active_workers, self.condition))

    @staticmethod
    def _get_user_vector(profile_embedding_id: UUID) -> list[float]:
        user_profile = qdrant_client.rest.points_api.get_point(collection_name="user_profile", id=str(profile_embedding_id)).result
        if not user_profile:
            raise RuntimeError("User not present found in vector DB")
        if (user_vector := user_profile.vector) is None:
            raise RuntimeError("User has no vector embedding.")
        return user_vector

    async def search_jobs(self, search_query: str, location: str, profile_embedding_id: UUID, num_results: int = 15) -> list[JobOffer]:
        user_vector = self._get_user_vector(profile_embedding_id)
        logger.warning(f"Searching for {num_results} jobs with query {search_query} in {location}")
        for scraper in self.scrapers:
            async for request in scraper.get_cached_start_requests(search_query, location, num_results * scraper.results_multiplier):
                await self.request_queue.put(request)

        logger.warning("Waiting for results")
        try:
            async with self.condition:
                await asyncio.wait_for(
                    self.condition.wait_for(lambda: self.request_queue.empty() and self.active_workers._value == self.workers),
                    timeout=self.timeout,
                )
        except asyncio.TimeoutError:
            logger.warning("Timeout reached")

        search_query_vector = self._get_search_query_vector(search_query + " " + location)[0].embedding
        search_vector = [a + (b * 0.5) for a, b in zip(search_query_vector, user_vector)]  # type: ignore
        search_result = qdrant_client.search(
            collection_name=JOB_COLLECTION, query_vector=search_vector, with_vectors=False, with_payload=True, limit=num_results
        )
        logger.warning(f"Found {len(search_result)} results")
        return [JobOffer(**result.payload) for result in search_result]  # type: ignore

    async def scrape(self, scrape_id: UUID, search_query: str, location: str, num_results: int = 15, start_index: int = 0) -> None:
        self.scrape_statuses[scrape_id] = ScrapeStatus.IN_PROGRESS
        for scraper in self.scrapers:
            async for request in scraper.get_cached_start_requests(
                search_query, location, num_results * scraper.results_multiplier, start_index
            ):
                await self.request_queue.put(request)

        logger.warning("Waiting for results")
        try:
            async with self.condition:
                await asyncio.wait_for(
                    self.condition.wait_for(lambda: self.request_queue.empty() and self.active_workers._value == self.workers),
                    timeout=self.timeout,
                )
        except asyncio.TimeoutError:
            logger.warning("Timeout reached")

        self.scrape_statuses[scrape_id] = ScrapeStatus.FINISHED
        for scraper in self.scrapers:
            scraper.set_cache(search_query, location, num_results * scraper.results_multiplier)

    def get_scrape_status(self, scrape_id: UUID) -> ScrapeStatus:
        return self.scrape_statuses.get(scrape_id, ScrapeStatus.NOT_FOUND)


scraper_aggregator = ScraperAggregator()
