import json
import os
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID, uuid4

import requests
from aiden_recommender import JOB_COLLECTION, qdrant_client, redis_client
from aiden_recommender.scrapers.utils import ChromeDriver, cache
from aiden_recommender.scrapers.wtj.schemas import JobOffer
from chompjs import parse_js_object
from loguru import logger
from mistralai.client import MistralClient
from qdrant_client.models import PointStruct
from selenium.webdriver.common.by import By


def chunk_list(lst, n):
    return [lst[i : i + n] for i in range(0, len(lst), n)]


class WelcomeToTheJungleScraper:
    def __init__(self):
        self.driver = ChromeDriver()
        self.driver.start()
        self.driver.driver.get("https://www.welcometothejungle.com/")  # type: ignore
        script = self.driver.driver.find_element(By.XPATH, '//script[@type="text/javascript"]').get_attribute("innerHTML")  # type: ignore
        self.driver.quit()
        self.mistral_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
        script_dict = parse_js_object(script)
        self.headers = {
            "Referer": "https://www.welcometothejungle.com/",
            "x-algolia-api-key": script_dict["ALGOLIA_API_KEY_CLIENT"],
            "x-algolia-application-id": script_dict["ALGOLIA_APPLICATION_ID"],
            "content-type": "application/x-www-form-urlencoded",
        }
        self.autocomplete_params = {
            "apiKey": script_dict["HERE_API_KEY"],
            "lang": "fr",
            "limit": "10",
        }
        self.lookup_params = {
            "apiKey": script_dict["HERE_API_KEY"],
            "lang": "fr",
        }
        logger.info("succesfully initialized WTJ scraper")

    def _get_algolia_params(self, search_query: str, latlng: str) -> str:
        params = {"hitsPerPage": 1000, "query": search_query, "aroundLatLng": latlng, "aroundRadius": 2000000}
        return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": urlencode(params)}]})

    @cache(retention_period=timedelta(hours=12), model=JobOffer)
    def _fetch_results(self, search_query: str, location: str) -> list[JobOffer]:
        # Query hereapi for location id
        self.autocomplete_params["q"] = location
        response = requests.get("https://autocomplete.search.hereapi.com/v1/autocomplete", params=self.autocomplete_params)
        response.raise_for_status()

        # Query hereapi for location coordinates
        if not response.json()["items"]:
            return []
        self.lookup_params["id"] = response.json()["items"][0]["id"]
        response = requests.get("https://lookup.search.hereapi.com/v1/lookup", params=self.lookup_params)
        response.raise_for_status()
        latlng = ",".join([str(x) for x in response.json()["position"].values()])

        # Query algolia
        params = self._get_algolia_params(search_query, latlng)
        response = requests.post(
            "https://csekhvms53-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            headers=self.headers,
            data=params,
        )

        response.raise_for_status()
        return [JobOffer(**offer) for offer in response.json()["results"][0]["hits"]]

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

    def search_jobs(self, search_query: str, location: str, num_results: int, profile_embedding_id: UUID) -> list[str]:
        jobs = self._fetch_results(search_query, location)
        self._embed_offers(jobs)
        user_profile = qdrant_client.rest.points_api.get_point(collection_name="user_profile", id=str(profile_embedding_id)).result
        if not user_profile:
            raise RuntimeError("User not present found in vector DB")
        if (vector := user_profile.vector) is None:
            raise RuntimeError("User has no vector embedding.")
        search_result = qdrant_client.search(
            collection_name=JOB_COLLECTION,
            query_vector=vector,  # type: ignore
            with_vectors=False,
            with_payload=True,
            limit=num_results,
        )
        return [JobOffer(**result.payload).metadata_repr() for result in search_result]  # type: ignore
