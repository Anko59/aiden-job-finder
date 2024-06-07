import os

import redis
from mistralai.async_client import MistralAsyncClient
from mistralai.client import MistralClient
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from zyte_api import AsyncZyteAPI
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from redis.asyncio import Redis
from aiden_recommender.constants import COMPANY_COLLECTION, JOB_COLLECTION
from aiden_recommender.france_travail_clients.job_search_client import JobSearchClient


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

async_zyte_client = AsyncZyteAPI(api_key=os.getenv("ZYTE_API_KEY"))

async_mistral_client = MistralAsyncClient(api_key=os.getenv("MISTRAL_API_KEY"), timeout=5)
mistral_client = MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))
async_redis_client = Redis.from_url(redis_url)

zyte_session = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=(
        502,
        429,
    ),  # 429 for too many requests and 502 for bad gateway
    respect_retry_after_header=False,
)
adapter = HTTPAdapter(max_retries=retry)
zyte_session.mount("http://", adapter)
zyte_session.mount("https://", adapter)
zyte_session.auth = (os.getenv("ZYTE_API_KEY"), "")

async_job_search_client = JobSearchClient(
    client_id=os.getenv("FRANCE_TRAVAIL_CLIENT_ID"), client_secret=os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET")
)
