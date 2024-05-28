import os

import redis
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams

JOB_COLLECTION = "jobs"
COMPANY_COLLECTION = "companies"

if (qdrant_url := os.getenv("QDRANT_URL")) is None:
    raise Exception("QDRANT_URL env variable is not set")
qdrant_client = QdrantClient(url=qdrant_url)

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
