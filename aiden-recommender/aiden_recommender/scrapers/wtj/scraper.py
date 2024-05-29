import json
from datetime import timedelta
from urllib.parse import urlencode

import requests
from aiden_recommender.scrapers.scraper_base import ScraperBase
from aiden_recommender.scrapers.utils import ChromeDriver, cache
from aiden_recommender.scrapers.models import JobOffer
from chompjs import parse_js_object
from loguru import logger
from selenium.webdriver.common.by import By
import urllib


class WelcomeToTheJungleScraper(ScraperBase):
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
        super().__init__()

    def _get_algolia_params(self, search_query: str, latlng: str) -> str:
        params = {"hitsPerPage": 1000, "query": search_query, "aroundLatLng": latlng, "aroundRadius": 2000000}
        return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": urlencode(params)}]})

    @cache(retention_period=timedelta(hours=12), model=JobOffer, source="wtj")
    def _fetch_results(self, search_query: str, location: str) -> list[JobOffer]:
        base_url = "https://geocode.search.hereapi.com/v1/geocode"
        address = urllib.parse.quote_plus(location)
        url = base_url + "?apiKey=3YHjVgEYjuwUatQAtD-wTX8lmNXEsULPzC8m59VMGDw&q=" + address
        geocode = json.loads(requests.get(url, headers=self.headers).text)
        if not geocode["items"]:
            return []
        pos = geocode["items"][0]["position"]
        # Query algolia
        params = self._get_algolia_params(search_query, f"{pos['lat']},{pos['lng']}")
        response = requests.post(
            "https://csekhvms53-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            headers=self.headers,
            data=params,
        )

        response.raise_for_status()
        return [JobOffer(**offer) for offer in response.json()["results"][0]["hits"]]
