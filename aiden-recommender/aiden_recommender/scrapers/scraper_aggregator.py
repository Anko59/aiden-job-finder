from aiden_recommender.scrapers.wtj.scraper import WelcomeToTheJungleScraper
from aiden_recommender.scrapers.france_travail.scraper import FranceTravailScraper
from aiden_recommender.scrapers.indeed.scraper import IndeedScraper
from aiden_recommender import JOB_COLLECTION, qdrant_client
from aiden_recommender.scrapers.models import JobOffer
import json
from mistralai.client import MistralClient
import os
from uuid import UUID
from qdrant_client import models


class ScraperAggregator:
    wtj_scraper = WelcomeToTheJungleScraper()
    france_travail_scraper = FranceTravailScraper()
    indeed_scraper = IndeedScraper()
    mistral_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))

    @classmethod
    def _get_search_query_vector(cls, search_query: str) -> list[float]:
        return cls.mistral_client.embeddings(model="mistral-embed", input=[search_query]).data[0].embedding

    @staticmethod
    def _get_user_vector(profile_embedding_id: UUID) -> list[float]:
        user_profile = qdrant_client.rest.points_api.get_point(collection_name="user_profile", id=str(profile_embedding_id)).result
        if not user_profile:
            raise RuntimeError("User not present found in vector DB")
        if (user_vector := user_profile.vector) is None:
            raise RuntimeError("User has no vector embedding.")
        return user_vector

    @classmethod
    def search_jobs(cls, search_query: str, location: str, profile_embedding_id: UUID, num_results: int = 15) -> list[str]:
        user_vector = cls._get_user_vector(profile_embedding_id)

        wtj_embedding_ids = cls.wtj_scraper.search_jobs(search_query=search_query, location=location, num_results=num_results * 10)

        france_travail_embedding_ids = cls.france_travail_scraper.search_jobs(
            search_query=search_query, location=location, num_results=num_results * 10
        )

        indeed_embedding_ids = cls.indeed_scraper.search_jobs(search_query=search_query, location=location, num_results=num_results)
        # Get embedding ids
        embedding_ids = wtj_embedding_ids + france_travail_embedding_ids + indeed_embedding_ids

        # Generate the search vector
        search_query_vector = cls._get_search_query_vector(search_query + " " + location)
        search_vector = [a + (b * 0.5) for a, b in zip(search_query_vector, user_vector)]

        # Filter the search to only include the job offers with the given embedding ids
        # currently not working
        job_filter = models.Filter(must=[models.FieldCondition(key="_id", match=models.MatchValue(value=str(id))) for id in embedding_ids])  # noqa
        # Perform the search with the filter
        search_result = qdrant_client.search(
            collection_name=JOB_COLLECTION, query_vector=search_vector, with_vectors=False, with_payload=True, limit=num_results
        )

        # Return the top `num_results` search results
        return json.dumps([JobOffer(**result.payload).model_dump() for result in search_result])
