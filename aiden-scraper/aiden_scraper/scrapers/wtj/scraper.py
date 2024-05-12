from urllib.parse import urlencode
import json

import requests
from chompjs import parse_js_object
from loguru import logger
from selenium.webdriver.common.by import By

from aiden_scraper.scrapers.wtj.schemas import JobOffer
from aiden_scraper.scrapers.utils import ChromeDriver


class WelcomeToTheJungleScraper:
    def __init__(self):
        self.driver = ChromeDriver()
        self.driver.start()
        self.driver.driver.get("https://www.welcometothejungle.com/")  # type: ignore
        script = self.driver.driver.find_element(By.XPATH, '//script[@type="text/javascript"]').get_attribute("innerHTML")  # type: ignore
        self.driver.quit()
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

    def _fetch_results(self, search_query: str, location: str) -> list[JobOffer]:
        # Query hereapi for location coordinates
        self.autocomplete_params["q"] = location
        response = requests.get("https://autocomplete.search.hereapi.com/v1/autocomplete", params=self.autocomplete_params)
        response.raise_for_status()
        print(response.json())
        self.lookup_params["id"] = response.json()["items"][0]["id"]
        response = requests.get("https://lookup.search.hereapi.com/v1/lookup", params=self.lookup_params)
        response.raise_for_status()
        print(response.json())
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

    def search_jobs(self, search_query: str, location: str, num_results: int = 15) -> list[JobOffer]:
        return self._fetch_results(search_query, location)[:num_results]
