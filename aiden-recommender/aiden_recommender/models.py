from __future__ import annotations
from datetime import timedelta
import json
from typing import AsyncGenerator, Callable, Optional, Any
from aiden_shared.models import JobOffer

from pydantic import BaseModel
from abc import ABC, abstractmethod
from mistralai.models.embeddings import EmbeddingObject
from qdrant_client.models import PointStruct

from aiden_shared.constants import JOB_COLLECTION
from aiden_recommender.tools import async_zyte_client, async_redis_client, async_mistral_client, async_qdrant_client
import hashlib
import uuid


def reference_to_uuid(reference: str) -> uuid.UUID:
    return uuid.UUID(hashlib.md5(reference.encode()).hexdigest())


class Request(BaseModel, ABC):
    callback: Optional[Callable] = None
    retention_period: timedelta = timedelta(hours=12)

    @abstractmethod
    def _generate_cache_keys(self) -> list[str]:
        pass

    @abstractmethod
    def get_coroutine(self, is_cached):
        pass

    async def send(self) -> AsyncGenerator[JobOffer | Request]:
        is_cached = [await async_redis_client.exists(key) for key in self._generate_cache_keys()]
        if False in is_cached:
            response = await self.get_coroutine(is_cached)
            if response and self.callback:
                for next_item in self.callback(response):
                    yield next_item
            for key in self._generate_cache_keys():
                await async_redis_client.setex(key, self.retention_period, 1)


class ZyteRequest(Request):
    query: dict[str, Any]

    def get_coroutine(self, is_cached):
        return async_zyte_client.get(query=self.query)

    def _generate_cache_keys(self) -> str:
        return [f"zyte-request-{json.dumps(self.query)}"]


class MistralEmbeddingRequest(Request):
    input: list["JobOffer"]
    retention_period: timedelta = timedelta(days=365)

    def get_coroutine(self, is_cached):
        # We only want to embed the items that are not already cached
        return async_mistral_client.embeddings(
            model="mistral-embed", input=[item.metadata_repr() for item, cache in zip(self.input, is_cached) if not cache]
        )

    def _generate_cache_keys(self) -> str:
        return [f"mistal-embed-{item.reference}" for item in self.input]


class QdrantRequest(Request):
    embeddings: list[EmbeddingObject]
    job_offers: list["JobOffer"]
    retention_period: timedelta = timedelta(days=365)

    def get_coroutine(self, is_cached):
        return async_qdrant_client.upload_points(
            collection_name=JOB_COLLECTION,
            points=[
                PointStruct(id=reference_to_uuid(job_offer.reference).hex, vector=embedding.embedding, payload=job_offer.model_dump())
                for job_offer, embedding, cache in zip(self.job_offers, self.embeddings, is_cached)
                if not cache
            ],
        )

    def _generate_cache_keys(self) -> list[str]:
        return [f"qdrant-embed-{job_offer.reference}" for job_offer in self.job_offers]


class ScraperItem(BaseModel):
    raw_data: list[dict]
