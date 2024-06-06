import asyncio
from uuid import UUID

from mistralai.models.embeddings import EmbeddingObject
from aiden_recommender.constants import JOB_COLLECTION

# from aiden_recommender.scrapers.france_travail.scraper import FranceTravailScraper
from aiden_recommender.scrapers.indeed.scraper import IndeedScraper
from aiden_recommender.models import JobOffer, Request
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.wtj.scraper import WelcomeToTheJungleScraper
from aiden_recommender.tools import qdrant_client, mistral_client


class ScraperAggregator:
    def __init__(self, max_workers=64):
        self.scrapers: list[AbstractScraper] = [WelcomeToTheJungleScraper(), IndeedScraper()]
        self.workers = max_workers
        self.timeout = 60
        # self.france_travail_scraper = FranceTravailScraper()
        # self.indeed_scraper = IndeedScraper()

    # @cache(retention_period=timedelta(hours=12), model=EmbeddingObject, source="search_queries")
    def _get_search_query_vector(self, search_query: str) -> list[EmbeddingObject]:
        return mistral_client.embeddings(model="mistral-embed", input=[search_query]).data

    async def _run_scraper(self, scraper, search_query, location, num_results):
        results = []
        async for result in scraper.search_jobs(search_query, location, num_results):
            results.append(result)
        return results

    async def handle_request(self, request, request_queue, results_queue):
        response = await request.coroutine
        if request.callback is not None:
            for next_item in request.callback(response):
                if isinstance(next_item, Request):
                    await request_queue.put(next_item)
                else:
                    await results_queue.put(next_item)

    async def worker(self, queue, results):
        while True:
            request = await queue.get()
            try:
                await self.handle_request(request, queue, results)
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

    async def search_jobs(self, search_query: str, location: str, profile_embedding_id: UUID, num_results: int = 15) -> list[str]:
        user_vector = self._get_user_vector(profile_embedding_id)
        request_queue = asyncio.Queue()
        results_queue = asyncio.Queue()
        for scraper in self.scrapers:
            for request in scraper.get_start_requests(search_query, location, num_results):
                await request_queue.put(request)
        workers = []
        for _ in range(self.workers):
            worker_task = asyncio.create_task(self.worker(request_queue, results_queue))
            workers.append(worker_task)
        try:
            await asyncio.wait_for(asyncio.gather(*workers), timeout=self.timeout)

        except asyncio.TimeoutError:
            print("Timeout")
        finally:
            await request_queue.join()
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

        search_query_vector = self._get_search_query_vector(search_query + " " + location)[0].embedding
        search_vector = [a + (b * 0.5) for a, b in zip(search_query_vector, user_vector)]  # type: ignore
        search_result = qdrant_client.search(
            collection_name=JOB_COLLECTION, query_vector=search_vector, with_vectors=False, with_payload=True, limit=num_results
        )

        # Return the top `num_results` search results
        # type: ignore
        return [JobOffer(**result.payload) for result in search_result]


scraper_aggregator = ScraperAggregator()
