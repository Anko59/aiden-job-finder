import json
from datetime import timedelta
from urllib.parse import quote_plus, urlencode

import requests
from chompjs import parse_js_object
from loguru import logger

from aiden_recommender.scrapers.models import JobOffer
from aiden_recommender.scrapers.scraper_base import ScraperBase
from aiden_recommender.scrapers.utils import chrome_driver, cache


class WelcomeToTheJungleScraper(ScraperBase):
    def __init__(self):
        soup = chrome_driver.get("https://www.welcometothejungle.com/")
        script = soup.find("script", {"type": "text/javascript"}).get_text()
        script_dict = parse_js_object(script)
        self.algolia_app_id = script_dict["ALGOLIA_APPLICATION_ID"]
        self.headers = {
            "Referer": "https://www.welcometothejungle.com/",
            "x-algolia-api-key": script_dict["ALGOLIA_API_KEY_CLIENT"],
            "x-algolia-application-id": self.algolia_app_id,
            "content-type": "application/x-www-form-urlencoded",
        }
        self.geocode_params = {
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
        address = quote_plus(location)
        self.geocode_params["q"] = address
        url = f"{base_url}?{urlencode(self.geocode_params)}"
        geocode = json.loads(requests.get(url, headers=self.headers).text)
        if not geocode["items"]:
            return []
        pos = geocode["items"][0]["position"]
        # Query algolia
        params = self._get_algolia_params(search_query, f"{pos['lat']},{pos['lng']}")
        response = requests.post(
            f"https://{self.algolia_app_id.lower()}-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            headers=self.headers,
            data=params,
        )

        response.raise_for_status()
        result = response.json()["results"][0]["hits"]
        for offer in result:
            try:
                offer["url"] = (
                    f"https://www.welcometothejungle.com/fr/companies/{offer['organization']['name'].lower()}/jobs/{offer['slug']}?&o={offer['reference']}"
                )
            except Exception:
                continue
        return [JobOffer(**offer) for offer in result]
