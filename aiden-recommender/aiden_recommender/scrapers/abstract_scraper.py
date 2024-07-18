from abc import ABC, abstractmethod
from base64 import b64decode
from functools import partial
from datetime import timedelta
from typing import Any, Callable, Iterable

from bs4 import BeautifulSoup
from loguru import logger

from aiden_shared.models import JobOffer
from aiden_recommender.models import MistralEmbeddingRequest, QdrantRequest, Request, ScraperItem, ZyteRequest
from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.tools import zyte_session
from aiden_shared.tools import async_redis_client


def chunk_list(lst, n):
    return [lst[i : i + n] for i in range(0, len(lst), n)]


class AbstractScraper(ABC):
    zyte_url = "https://api.zyte.com/v1/extract"
    settings = {}
    parser: AbstractParser
    zyte_api_automap = {"httpResponseBody": True}

    def __init__(self, results_multiplier: int = 1, retention_period=timedelta(days=1)):
        self.results_multiplier = results_multiplier
        self.job_offers_buffer = []
        self.retention_period = retention_period

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

    def parse_response(self, response: dict, parser_func: Callable, meta: dict[str, str] = {}) -> Iterable[JobOffer | Request]:
        for next_item in parser_func(response, meta):
            if isinstance(next_item, ScraperItem):
                job_offers = list(self.parser.parse(next_item.raw_data))
                for job_offer in job_offers:
                    yield self._get_embedding_request(job_offer)
                    yield job_offer
            else:
                yield next_item

    def parse_zyte_response(self, response: dict, parser_func: Callable, meta: dict[str, str] = {}) -> Iterable[JobOffer | Request]:
        logger.warning("Received response from Zyte")
        data = self._extract_zyte_data(response)
        yield from self.parse_response(data, parser_func, meta)

    def inline_get_zyte(self, url, additional_zyte_params: dict = {}) -> BeautifulSoup | str:
        query = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        data = zyte_session.post(self.zyte_url, json=query)
        try:
            return self._extract_zyte_data(data.json())
        except Exception:
            return BeautifulSoup(data.text, "html.parser")

    def get_zyte_request(self, url: str, callback: Callable, additional_zyte_params: dict = {}, meta: dict[str, Any] = {}) -> ZyteRequest:
        logger.warning("Sending request to Zyte")
        query: dict[str, Any] = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        _callback = partial(self.parse_zyte_response, parser_func=callback, meta=meta)
        return ZyteRequest(query=query, callback=_callback)

    def _get_qdrant_request(self, embeddings, job_offers) -> Iterable[QdrantRequest]:
        logger.warning("Sending request to Qdrant")
        yield QdrantRequest(embeddings=embeddings.data, job_offers=job_offers)

    def _get_embedding_request(self, job_offer: JobOffer) -> MistralEmbeddingRequest:
        logger.warning("Sending request to Mistral")
        callback = partial(self._get_qdrant_request, job_offers=[job_offer])
        return MistralEmbeddingRequest(input=[job_offer], callback=callback)

    @abstractmethod
    def get_start_requests(self, search_query: str, location: str, num_results: int, start_index: int) -> Iterable[Request]:
        return []

    async def get_cached_start_requests(self, search_query: str, location: str, num_results: int, start_index: int):
        offer_seen = await async_redis_client.exists(f"{self.source}-{search_query}-{location}")
        if offer_seen >= start_index + num_results:
            logger.info(f"{offer_seen} cache HIT: {search_query}, {location}, {num_results}")
            return
        for request in self.get_start_requests(search_query, location, num_results, offer_seen):
            yield request

    async def set_cache(self, search_query: str, location: str, num_results: int):
        cache_key = f"{self.source}-{search_query}-{location}"
        current_value = await async_redis_client.get(cache_key)

        if current_value is None:
            await async_redis_client.setex(cache_key, self.retention_period, num_results)
        else:
            new_value = int(current_value) + num_results
            await async_redis_client.setex(cache_key, self.retention_period, new_value)

    @abstractmethod
    def get_form(self, job_offer: JobOffer) -> dict[str, Any]:
        pass
