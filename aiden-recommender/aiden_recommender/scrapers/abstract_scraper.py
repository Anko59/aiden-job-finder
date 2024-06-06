from abc import ABC, abstractmethod
from base64 import b64decode
from functools import partial
from typing import Any, Callable, Iterable

# import requests
from bs4 import BeautifulSoup

# from urllib3.util.retry import Retry
from aiden_recommender.models import JobOffer, ScraperItem, ZyteRequest, MistralEmbeddingRequest, QdrantRequest, Request
from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.tools import async_redis_client, zyte_session


def chunk_list(lst, n):
    return [lst[i : i + n] for i in range(0, len(lst), n)]


class AbstractScraper(ABC):
    zyte_url = "https://api.zyte.com/v1/extract"
    settings = {}
    parser: AbstractParser
    zyte_api_automap = {"httpResponseBody": True}

    @property
    def source(self) -> str:
        return self.parser.source.default  # type: ignore

    def _extract_zyte_data(self, response: dict) -> BeautifulSoup | str:
        if response.get("browserHtml"):
            return BeautifulSoup(response["browserHtml"], "html.parser")
        elif response.get("httpResponseBody"):
            return b64decode(response["httpResponseBody"]).decode("utf-8")
        else:
            raise Exception

    def parse_zyte_response(self, response: dict, parser_func: Callable, meta: dict[str, str] = {}) -> Iterable[JobOffer | Request]:
        print("got zyte")
        data = self._extract_zyte_data(response)
        for next_item in parser_func(data, meta):
            if isinstance(next_item, ScraperItem):
                job_offers = list(self.parser.parse(next_item.raw_data))
                for job_offer in job_offers:
                    yield self._get_embedding_request(job_offer)
                    yield job_offer
            else:
                yield next_item

    def inline_get_zyte(self, url, additional_zyte_params: dict = {}) -> BeautifulSoup | str:
        query = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        data = zyte_session.post(self.zyte_url, json=query)
        try:
            return self._extract_zyte_data(data.json())
        except Exception:
            return BeautifulSoup(data.text, "html.parser")

    def get_zyte_request(self, url: str, callback: Callable, additional_zyte_params: dict = {}, meta: dict[str, str] = {}) -> ZyteRequest:
        print("get_zyte")
        query: dict[str, Any] = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        _callback = partial(self.parse_zyte_response, parser_func=callback, meta=meta)
        return ZyteRequest(query=query, callback=_callback)

    def _get_qdrant_request(self, embeddings, job_offer) -> Iterable[QdrantRequest]:
        print("got embed")
        yield QdrantRequest(embeddings=embeddings.data, job_offers=[job_offer])

    def _get_embedding_request(self, job_offer: JobOffer) -> MistralEmbeddingRequest:
        print("get embed")
        callback = partial(self._get_qdrant_request, job_offer=job_offer)
        return MistralEmbeddingRequest(input=[job_offer], callback=callback)

    @abstractmethod
    def get_start_requests(self, search_query: str, location: str, num_results: int) -> Iterable[Request]:
        return []

    async def get_cached_start_requests(self, search_query: str, location: str, num_results: int):
        offer_seen = await async_redis_client.exists(f"{self.source}-{search_query}-{location}")
        if offer_seen >= num_results:
            return
        for request in self.get_start_requests(search_query, location, num_results):
            yield request

    async def set_cache(self, search_query: str, location: str, num_results: int):
        await async_redis_client.set(f"{self.source}-{search_query}-{location}", num_results)
