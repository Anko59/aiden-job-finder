import os
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from abc import ABC, abstractmethod
from uuid import uuid4

from mistralai.client import MistralClient
from qdrant_client.models import PointStruct
from base64 import b64decode

from aiden_recommender.constants import JOB_COLLECTION
from aiden_recommender.models import JobOffer
from aiden_recommender.tools import qdrant_client, redis_client
from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.scrapers.utils import cache
from datetime import timedelta


def chunk_list(lst, n):
    return [lst[i : i + n] for i in range(0, len(lst), n)]


class AbstractScraper(ABC):
    zyte_url = "https://api.zyte.com/v1/extract"
    settings = {}
    parser: AbstractParser = None
    zyte_api_automap = {"httpResponseBody": True}
    mistral_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
    zyte_api_key = os.environ.get("ZYTE_API_KEY")

    @property
    def source(self) -> str:
        return self.parser.source.default

    def __init__(self):
        session = requests.Session()
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
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.auth = (self.zyte_api_key, "")
        self.session = session
        self.fetch_results = self._get_fetch_results_func()

    def get(self, url: str, additional_zyte_params: dict = {}) -> BeautifulSoup | dict:
        json = {"url": url}
        json.update(self.zyte_api_automap)
        json.update(additional_zyte_params)
        data = self.session.post(self.zyte_url, json=json)
        if data.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}. Status code: {data.status_code}")
        else:
            if json.get("browserHtml"):
                return BeautifulSoup(data.json()["browserHtml"], "html.parser")
            elif json.get("httpResponseBody"):
                return b64decode(data.json()["httpResponseBody"]).decode("utf-8")
            else:
                return BeautifulSoup(data.text, "html.parser")

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
    def _fetch_results(self, search_query: str, location: str) -> list[dict]:
        pass

    def _get_fetch_results_func(self):
        @cache(retention_period=timedelta(hours=12), model=JobOffer, source=self.source)
        def fetch_results(search_query: str, location: str) -> list[JobOffer]:
            results = self._fetch_results(search_query, location)
            return self.parser.parse(results)

        return fetch_results

    def search_jobs(self, search_query: str, location: str, num_results: int = 15) -> list[str]:
        jobs = self.fetch_results(search_query, location)[:num_results]
        return self._embed_offers(jobs)
