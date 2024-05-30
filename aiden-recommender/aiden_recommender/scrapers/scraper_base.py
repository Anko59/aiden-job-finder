import os
from abc import ABC, abstractmethod
from uuid import uuid4

from mistralai.client import MistralClient
from qdrant_client.models import PointStruct

from aiden_recommender.constants import JOB_COLLECTION
from aiden_recommender.scrapers.models import JobOffer
from aiden_recommender.tools import qdrant_client, redis_client


def chunk_list(lst, n):
    return [lst[i : i + n] for i in range(0, len(lst), n)]


class ScraperBase(ABC):
    def __init__(self):
        self.mistral_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))

    def _embed_offers(self, job_offers: list[JobOffer]) -> list[str]:
        offers_to_embed = [offer for offer in job_offers if redis_client.get(offer.reference) is None]

        ids = [str(uuid4()) for _ in range(len(offers_to_embed))]
        for offers, ids_chunked in zip(chunk_list(offers_to_embed, 5), chunk_list(ids, 5)):
            embeddings = self.mistral_client.embeddings(
                model="mistral-embed", input=[job_offer.profile or job_offer.metadata_repr() for job_offer in offers]
            )
            qdrant_client.upload_points(
                collection_name=JOB_COLLECTION,
                points=[
                    PointStruct(id=ids_chunked[i], vector=embeddings.data[i].embedding, payload=offer.model_dump())
                    for i, offer in enumerate(offers)
                ],
            )
            for id_, offer in zip(ids_chunked, offers):
                redis_client.set(name=offer.reference, value=id_)

        return ids

    @abstractmethod
    def _fetch_results(self, search_query: str, location: str) -> list[JobOffer]:
        pass

    def search_jobs(self, search_query: str, location: str, num_results: int = 15) -> list[str]:
        jobs = self._fetch_results(search_query, location)[:num_results]
        return self._embed_offers(jobs)
