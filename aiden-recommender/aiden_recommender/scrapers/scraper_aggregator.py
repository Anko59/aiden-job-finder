import asyncio
from uuid import UUID
from loguru import logger

from mistralai.models.embeddings import EmbeddingObject
from aiden_recommender.constants import JOB_COLLECTION

from aiden_recommender.scrapers.france_travail.scraper import FranceTravailScraper
from aiden_recommender.scrapers.indeed.scraper import IndeedScraper
from aiden_recommender.models import JobOffer, Request
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.wtj.scraper import WelcomeToTheJungleScraper
from aiden_recommender.tools import qdrant_client, mistral_client
from aiden_recommender.scrapers.utils import cache
from datetime import timedelta
from contextlib import suppress


class ScraperAggregator:
    def __init__(self, max_workers=64):
        self.scrapers: list[AbstractScraper] = [WelcomeToTheJungleScraper(), IndeedScraper(), FranceTravailScraper()]
        self.workers = max_workers
        self.timeout = 60

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
        request_queue = asyncio.Queue()
        results_queue = asyncio.Queue()
        active_workers = asyncio.Semaphore(self.workers)
        condition = asyncio.Condition()
        for scraper in self.scrapers:
            async for request in scraper.get_cached_start_requests(search_query, location, num_results):
                await request_queue.put(request)
        workers = []
        for _ in range(self.workers):
            worker_task = asyncio.create_task(self.worker(request_queue, results_queue, active_workers, condition))
            workers.append(worker_task)
        try:
            async with condition:
                await asyncio.wait_for(
                    condition.wait_for(lambda: request_queue.empty() and active_workers._value == self.workers), timeout=self.timeout
                )
        except asyncio.TimeoutError:
            logger.info("Timeout reached")
        finally:
            await request_queue.join()
            for worker in workers:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker
        search_query_vector = self._get_search_query_vector(search_query + " " + location)[0].embedding
        search_vector = [a + (b * 0.5) for a, b in zip(search_query_vector, user_vector)]  # type: ignore
        search_result = qdrant_client.search(
            collection_name=JOB_COLLECTION, query_vector=search_vector, with_vectors=False, with_payload=True, limit=num_results
        )

        return [JobOffer(**result.payload) for result in search_result]


scraper_aggregator = ScraperAggregator()
