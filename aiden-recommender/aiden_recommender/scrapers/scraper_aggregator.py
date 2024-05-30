import os
from datetime import timedelta
from uuid import UUID

from mistralai.client import MistralClient
from mistralai.models.embeddings import EmbeddingObject

from aiden_recommender.constants import JOB_COLLECTION
from aiden_recommender.scrapers.france_travail.scraper import FranceTravailScraper
from aiden_recommender.scrapers.models import JobOffer
from aiden_recommender.scrapers.utils import cache
from aiden_recommender.scrapers.wtj.scraper import WelcomeToTheJungleScraper
from aiden_recommender.tools import qdrant_client


class ScraperAggregator:
    def __init__(self):
        self.wtj_scraper = WelcomeToTheJungleScraper()
        self.france_travail_scraper = FranceTravailScraper()
        self.mistral_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))

    @cache(retention_period=timedelta(hours=12), model=EmbeddingObject, source="search_queries")
    def _get_search_query_vector(self, search_query: str) -> list[EmbeddingObject]:
        return self.mistral_client.embeddings(model="mistral-embed", input=[search_query]).data

    def search_jobs(self, search_query: str, location: str, profile_embedding_id: UUID, num_results: int = 15) -> list[JobOffer]:
        user_profile = qdrant_client.rest.points_api.get_point(collection_name="user_profile", id=str(profile_embedding_id)).result
        if not user_profile:
            raise RuntimeError("User not present found in vector DB")
        if (user_vector := user_profile.vector) is None:
            raise RuntimeError("User has no vector embedding.")

        wtj_embedding_ids = self.wtj_scraper.search_jobs(search_query=search_query, location=location, num_results=num_results * 10)  # noqa: F841
        france_travail_embedding_ids = self.france_travail_scraper.search_jobs(  # noqa: F841
            search_query=search_query, location=location, num_results=num_results * 10
        )

        # Get embedding ids
        # embedding_ids = wtj_embedding_ids + france_travail_embedding_ids

        # Generate the search vector
        search_query_vector = self._get_search_query_vector(search_query + " " + location)[0].embedding
        search_vector = [a + (b * 0.5) for a, b in zip(search_query_vector, user_vector)]  # type: ignore

        # Filter the search to only include the job offers with the given embedding ids
        # currently not working
        # job_filter = models.Filter(must=[models.FieldCondition(key="_id", match=models.MatchValue(value=str(id))) for id in embedding_ids])  # noqa
        # Perform the search with the filter
        search_result = qdrant_client.search(
            collection_name=JOB_COLLECTION, query_vector=search_vector, with_vectors=False, with_payload=True, limit=num_results
        )

        # Return the top `num_results` search results
        return [JobOffer(**result.payload) for result in search_result]  # type: ignore


scraper_aggregator = ScraperAggregator()
