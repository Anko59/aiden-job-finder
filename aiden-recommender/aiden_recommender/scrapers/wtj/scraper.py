import json
from datetime import timedelta
from urllib.parse import quote_plus, urlencode

from chompjs import parse_js_object
from loguru import logger

from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.wtj.parser import WtjParser
from aiden_recommender.scrapers.utils import cache
from pydantic import BaseModel


class StartParams(BaseModel):
    algolia_app_id: str
    algolia_api_key: str
    here_api_key: str


class WelcomeToTheJungleScraper(AbstractScraper):
    base_url = "https://www.welcometothejungle.com"
    geocode_url = "https://geocode.search.hereapi.com/v1/geocode"
    parser = WtjParser()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        start_params = self._get_start_params()
        self.algolia_app_id = start_params.algolia_app_id
        self.headers = {
            "Referer": "https://www.welcometothejungle.com/",
            "x-algolia-api-key": start_params.algolia_api_key,
            "x-algolia-application-id": self.algolia_app_id,
            "content-type": "application/x-www-form-urlencoded",
        }
        self.geocode_params = {
            "apiKey": start_params.here_api_key,
            "lang": "fr",
        }
        logger.info("succesfully initialized WTJ scraper")

    def _get_algolia_params(self, search_query: str, pos: dict) -> str:
        latlng = f"{pos['lat']},{pos['lng']}"
        params = {"hitsPerPage": 1000, "query": search_query, "aroundLatLng": latlng, "aroundRadius": 2000000}
        return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": urlencode(params)}]})

    @cache(retention_period=timedelta(hours=12), model=StartParams, source="wtj_start_params")
    def _get_start_params(self) -> StartParams:
        # We want to cache the start parmas because the browserHtml request is a bit expensive
        soup = self.get(self.base_url, {"browserHtml": True})
        script = soup.find("script", {"type": "text/javascript"}).get_text()
        script_dict = parse_js_object(script)
        return StartParams(
            algolia_app_id=script_dict["ALGOLIA_APPLICATION_ID"],
            algolia_api_key=script_dict["ALGOLIA_API_KEY_CLIENT"],
            here_api_key=script_dict["HERE_API_KEY"],
        )

    def _fetch_results(self, search_query: str, location: str) -> list[dict]:
        address = quote_plus(location)
        self.geocode_params["q"] = address
        url = f"{self.geocode_url}?{urlencode(self.geocode_params)}"
        geocode = self.get(url).json()
        if not geocode["items"]:
            return []
        pos = geocode["items"][0]["position"]
        # Query algolia
        params = self._get_algolia_params(search_query, pos)
        response = self.get(
            f"https://{self.algolia_app_id.lower()}-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            additional_zyte_params={"httpRequestBody": params, "httpRequestMethod": "POST", "customHttpRequestHeaders": self.headers},
        )
        result = response.json()["results"][0]["hits"]
        return result
