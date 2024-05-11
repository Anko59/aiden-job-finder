import json
from urllib.parse import urlencode

import requests
from aiden_scraper.utils import ChromeDriver
from aiden_scraper.wtj.schemas import JobOffer
from chompjs import parse_js_object
from loguru import logger
from selenium.webdriver.common.by import By


class WelcomeToTheJungleScraper:
    def __init__(self):
        self.driver = ChromeDriver()
        self.driver.start()
        self.driver.driver.get("https://www.welcometothejungle.com/")
        script = self.driver.driver.find_element(By.XPATH, '//script[@type="text/javascript"]').get_attribute("innerHTML")
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

    def _format_algolia_params(self, params: dict) -> str:
        return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": urlencode(params)}]})

    def fetch_results(self, params: dict) -> list[JobOffer]:
        # Query algolia
        _params = self._format_algolia_params(params)
        response = requests.post(
            "https://csekhvms53-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            headers=self.headers,
            data=_params,
        )

        response.raise_for_status()
        return [JobOffer(**offer) for offer in response.json()["results"][0]["hits"]]
