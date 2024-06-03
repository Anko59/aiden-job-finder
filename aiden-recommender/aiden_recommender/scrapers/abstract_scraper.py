from abc import ABC, abstractmethod
from base64 import b64decode
from functools import partial
from typing import Any, Callable
from uuid import uuid4

# import requests
from bs4 import BeautifulSoup
from qdrant_client.models import PointStruct

# from urllib3.util.retry import Retry
from aiden_recommender.constants import JOB_COLLECTION
from aiden_recommender.models import JobOffer, Request, ScraperItem
from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.tools import async_mistral_client, async_qdrant_client, async_zyte_client, redis_client, zyte_client


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

    def __init__(self):
        self._start_requests = self._get_start_requests_func()

    def inline_get(self, url: str, additional_zyte_params: dict = {}) -> BeautifulSoup | str:
        query: dict[str, Any] = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        data = zyte_client.get(query=query)

        if data.get("browserHtml"):
            return BeautifulSoup(data["browserHtml"], "html.parser")
        elif data.get("httpResponseBody"):
            return b64decode(data["httpResponseBody"]).decode("utf-8")
        else:
            raise Exception

    async def parse_zyte_response(self, response: dict, parser_func: Callable, meta: dict[str, str] = {}):
        if response.get("browserHtml"):
            data = BeautifulSoup(response["browserHtml"], "html.parser")
        elif response.get("httpResponseBody"):
            data = b64decode(response["httpResponseBody"]).decode("utf-8")
        else:
            raise Exception
        for parsed_result in parser_func(data, **meta):
            if isinstance(parsed_result, ScraperItem):
                yield self.parser.transform_to_job_offer(ScraperItem.raw_data)
            else:
                yield parsed_result

    async def get(self, url: str, callback: Callable, additional_zyte_params: dict = {}, meta: dict[str, str] = {}):
        query: dict[str, Any] = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        _callback = partial(self.parse_zyte_response, parser_func=callback, meta=meta)
        yield Request(async_zyte_client.get(query=query), _callback)

    async def _embed_offer(self, job_offer: JobOffer) -> str:
        if _id := redis_client.get(name=job_offer.reference):
            return str(_id)
        embedding = await async_mistral_client.embeddings(model="mistral-embed", input=[job_offer.metadata_repr()])
        _id = uuid4().hex
        await async_qdrant_client.upload_points(
            collection_name=JOB_COLLECTION,
            points=[PointStruct(id=_id, vector=embedding.data[0].embedding, payload=job_offer.model_dump())],
        )

        redis_client.set(name=job_offer.reference, value=_id)

        return _id

    @abstractmethod
    def get_start_requests(self, search_query: str, location: str):
        return []

    def _get_start_requests_func(self):
        # @cache(retention_period=timedelta(hours=12), model=JobOffer, source=self.source)
        def get_start_requests(search_query: str, location: str):
            yield from self.get_start_requests(search_query, location)

        return get_start_requests

    async def _parse_scraper_output(self, item: JobOffer | Request):
        if isinstance(item, Request):
            response = await item.coroutine
            result = await item.callback(response)
            yield self._parse_scraper_output(result)
        elif isinstance(item, JobOffer):
            item_id = await self._embed_offer(item)
            yield item_id

    async def search_jobs(self, search_query: str, location: str, num_results: int = 15) -> list[str]:
        results = []
        async for item in self._start_requests(search_query, location):
            async for parsed_item in self._parse_scraper_output(item):
                results.append(parsed_item)
        return results
