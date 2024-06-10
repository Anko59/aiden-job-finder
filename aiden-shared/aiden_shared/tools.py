import os

import redis
from mistralai.async_client import MistralAsyncClient
from mistralai.client import MistralClient
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from redis.asyncio import Redis
from .constants import COMPANY_COLLECTION, JOB_COLLECTION


if (qdrant_url := os.getenv("QDRANT_URL")) is None:
    raise Exception("QDRANT_URL env variable is not set")
qdrant_client = QdrantClient(url=qdrant_url)
async_qdrant_client = AsyncQdrantClient(url=qdrant_url)

try:
    qdrant_client.create_collection(
        collection_name=JOB_COLLECTION,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
    qdrant_client.create_collection(
        collection_name=COMPANY_COLLECTION,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
except UnexpectedResponse:
    pass

if (redis_url := os.getenv("REDIS_URL")) is None:
    raise Exception("REDIS_URL is not set")
redis_client = redis.Redis.from_url(redis_url)


async_mistral_client = MistralAsyncClient(api_key=os.getenv("MISTRAL_API_KEY"), timeout=5)
mistral_client = MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))
async_redis_client = Redis.from_url(redis_url)
