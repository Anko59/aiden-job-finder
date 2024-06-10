import json
import logging
from base64 import b64decode
from datetime import timedelta
from typing import Any
from urllib.parse import quote_plus, urlencode
from uuid import uuid4

from bs4 import BeautifulSoup
from chompjs import parse_js_object
from mistralai.models.embeddings import EmbeddingResponse
from prefect import flow, task
from prefect.serializers import JSONSerializer
from prefect.task_runners import ConcurrentTaskRunner
from prefect.tasks import task_input_hash
from pydantic import BaseModel
from qdrant_client.models import PointStruct

from aiden_recommender.constants import JOB_COLLECTION
from aiden_recommender.models import JobOffer, ScraperItem
from aiden_recommender.scrapers.wtj.parser import WtjParser
from aiden_recommender.tools import mistral_client, qdrant_client, zyte_client, zyte_session

base_url = "https://www.welcometothejungle.com"
geocode_url = "https://geocode.search.hereapi.com/v1/geocode"
zyte_api_automap = {"httpResponseBody": True}
zyte_url = "https://api.zyte.com/v1/extract"
parser = WtjParser()
logger = logging.getLogger(__name__)


class StartParams(BaseModel):
    headers: dict[str, Any]
    geocode_params: dict[str, Any]
    algolia_app_id: str


def parse_algolia_resuts(algolia_results: str):
    result = json.loads(algolia_results)
    return ScraperItem(raw_data=result["results"][0]["hits"])


# @func_cache(retention_period=timedelta(hours=12), model=StartParams, source="wtj_start_params")
def _get_start_params() -> StartParams:
    # We want to cache the start parmas because the browserHtml request is a bit expensive
    soup = inline_get_zyte(base_url, {"browserHtml": True, "httpResponseBody": False})
    script = soup.find("script", {"type": "text/javascript"}).get_text()  # type: ignore
    script_dict = parse_js_object(script)
    return StartParams(
        algolia_app_id=script_dict["ALGOLIA_APPLICATION_ID"],
        headers={
            "Referer": "https://www.welcometothejungle.com/",
            "x-algolia-api-key": script_dict["ALGOLIA_API_KEY_CLIENT"],
            "x-algolia-application-id": script_dict["ALGOLIA_APPLICATION_ID"],
            "content-type": "application/x-www-form-urlencoded",
        },
        geocode_params={
            "apiKey": script_dict["HERE_API_KEY"],
            "lang": "fr",
        },
    )


def _extract_zyte_data(response: dict) -> BeautifulSoup | str:
    if response.get("browserHtml"):
        return BeautifulSoup(response["browserHtml"], "html.parser")
    elif response.get("httpResponseBody"):
        return b64decode(response["httpResponseBody"]).decode("utf-8")
    else:
        raise Exception


@task(result_serializer=JSONSerializer(jsonlib="json"))
def get_scraper_item(algolia_results: str) -> ScraperItem:
    result = json.loads(algolia_results)
    return ScraperItem(raw_data=result["results"][0]["hits"])


def get_algolia_params(search_query: str, pos: str, num_results: int) -> str:
    params = {"hitsPerPage": num_results, "query": search_query, "aroundLatLng": pos, "aroundRadius": 2000000}
    return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": urlencode(params)}]})


@task(cache_key_fn=task_input_hash)
def get_pos(location: str) -> str:
    start_params = _get_start_params()
    address = quote_plus(location)
    start_params.geocode_params.update({"q": address})
    results = json.loads(get_zyte_request(url=f"{geocode_url}?{urlencode(start_params.geocode_params)}"))  # type: ignore
    pos = results["items"][0]["position"]
    latlng = f"{pos['lat']},{pos['lng']}"
    return latlng


@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=12))
def search_wtj(search_query: str, location: str, num_results: int, pos: str) -> list[JobOffer]:
    start_params = _get_start_params()
    address = quote_plus(location)
    start_params.geocode_params["q"] = address
    params = get_algolia_params(search_query=search_query, pos=pos, num_results=num_results)
    result = get_zyte_request(
        f"https://{start_params.algolia_app_id.lower()}-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",
        additional_zyte_params={
            "httpRequestText": params,
            "httpRequestMethod": "POST",
            "customHttpRequestHeaders": [{"name": k, "value": v} for k, v in start_params.headers.items()],
        },
    )
    scraped_item = parse_algolia_resuts(_extract_zyte_data(result))
    return parser.parse(scraped_item.raw_data)


def get_zyte_request(url: str, additional_zyte_params: dict = {}):
    logger.warning("Sending request to Zyte")
    query: dict[str, Any] = {"url": url}
    query.update(zyte_api_automap)
    query.update(additional_zyte_params)
    return zyte_client.get(query)


def inline_get_zyte(url, additional_zyte_params: dict = {}) -> BeautifulSoup | str:
    query = {"url": url}
    query.update(zyte_api_automap)
    query.update(additional_zyte_params)
    data = zyte_session.post(zyte_url, json=query)
    try:
        return _extract_zyte_data(data.json())
    except Exception:
        return BeautifulSoup(data.text, "html.parser")


@task(cache_key_fn=task_input_hash)
def get_embeddings(job_offer: JobOffer) -> EmbeddingResponse:
    return mistral_client.embeddings(model="mistral-embed", input=[job_offer.metadata_repr()])


@task(cache_key_fn=task_input_hash)
def save_embeddings(embeddings: EmbeddingResponse, job_offer: JobOffer) -> str:
    offer_id = str(uuid4())
    embeddings_vector = embeddings.data[0].embedding
    qdrant_client.upload_points(
        collection_name=JOB_COLLECTION,
        points=[PointStruct(id=offer_id, vector=embeddings_vector, payload=job_offer.model_dump())],
    )
    return offer_id


@flow(task_runner=ConcurrentTaskRunner())
def scrape_wtj(search_query: str, location: str, num_results: int) -> list[JobOffer]:
    position_geocoded = get_pos.submit(location=location)
    search_results = search_wtj.submit(
        search_query=search_query, location=location, num_results=num_results, pos=position_geocoded.result()
    )
    for result in search_results.result():
        embeddings = get_embeddings.submit(result)
        save_embeddings.submit(embeddings=embeddings.result(), job_offer=result)
    return search_results.result()


if __name__ == "__main__":
    scrape_wtj(search_query="Machine learning engineer", location="Paris", num_results=10)  # type: ignore
