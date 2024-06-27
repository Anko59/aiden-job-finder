import os

from zyte_api import AsyncZyteAPI
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from aiden_recommender.france_travail_clients.job_search_client import JobSearchClient


async_zyte_client = AsyncZyteAPI(api_key=os.getenv("ZYTE_API_KEY"))


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
