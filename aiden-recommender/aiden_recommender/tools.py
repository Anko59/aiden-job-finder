import os

import redis
from mistralai.async_client import MistralAsyncClient
from mistralai.client import MistralClient
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from zyte_api import AsyncZyteAPI, ZyteAPI

from aiden_recommender.constants import COMPANY_COLLECTION, JOB_COLLECTION

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

zyte_client = ZyteAPI(api_key=os.getenv("ZYTE_API_KEY"))
async_zyte_client = AsyncZyteAPI(api_key=os.getenv("ZYTE_API_KEY"))

async_mistral_client = MistralAsyncClient(api_key=os.environ.get("MISTRAL_API_KEY"))
mistral_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
