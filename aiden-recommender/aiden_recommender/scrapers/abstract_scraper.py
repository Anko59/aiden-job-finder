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
from aiden_recommender.tools import async_mistral_client, async_qdrant_client, async_zyte_client, async_redis_client, zyte_session


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

    def parse_zyte_response(self, response: dict, parser_func: Callable, meta: dict[str, str] = {}):
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

    def inline_get_zyte(self, url, additional_zyte_params: dict = {}):
        query = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        data = zyte_session.post(self.zyte_url, json=query)
        try:
            return self._extract_zyte_data(data.json())
        except Exception:
            return BeautifulSoup(data.text, "html.parser")

    def get_zyte_request(self, url: str, callback: Callable, additional_zyte_params: dict = {}, meta: dict[str, str] = {}):
        print("get_zyte")
        query: dict[str, Any] = {"url": url}
        query.update(self.zyte_api_automap)
        query.update(additional_zyte_params)
        _callback = partial(self.parse_zyte_response, parser_func=callback, meta=meta)
        return Request(async_zyte_client.get(query=query), _callback)

    def _parse_qdrant_response(self, qdrand_response, job_offer, _id):
        coroutine = async_redis_client.set(name=job_offer.reference, value=_id)
        yield Request(coroutine, None)

    def _parse_embedding_response(self, embedding, job_offer) -> Request:
        print("got embed")
        _id = uuid4().hex
        coroutine = async_qdrant_client.upload_points(
            collection_name=JOB_COLLECTION, points=[PointStruct(id=_id, vector=embedding.data[0].embedding, payload=job_offer.model_dump())]
        )
        callback = partial(self._parse_qdrant_response, job_offer=job_offer, _id=_id)
        yield Request(coroutine, callback)

    def _get_embedding_request(self, job_offer: JobOffer) -> Request:
        print("get embed")
        coroutine = async_mistral_client.embeddings(model="mistral-embed", input=[job_offer.metadata_repr()])
        callback = partial(self._parse_embedding_response, job_offer=job_offer)
        return Request(coroutine, callback)

    @abstractmethod
    def get_start_requests(self, search_query: str, location: str):
        return []
