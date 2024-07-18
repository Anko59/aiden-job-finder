from base64 import b64decode
import json
from typing import Any
from urllib.parse import quote_plus, urlencode

from chompjs import parse_js_object

from aiden_shared.models import JobOffer
from aiden_recommender.tools import zyte_session
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.wtj.parser import WtjParser
from aiden_recommender.models import ScraperItem
from aiden_recommender.scrapers.utils import cache, extract_form_fields
from datetime import timedelta
from pydantic import BaseModel


class StartParams(BaseModel):
    algolia_app_id: str
    algolia_api_key: str
    here_api_key: str
    api_auth_cookies: list[dict[str, Any]]
    csrf_token: str


class WelcomeToTheJungleScraper(AbstractScraper):
    base_url = "https://www.welcometothejungle.com"
    geocode_url = "https://geocode.search.hereapi.com/v1/geocode"
    parser = WtjParser()

    def parse_algolia_resuts(self, algolia_results: str, meta: dict):
        result = json.loads(algolia_results)
        yield ScraperItem(raw_data=result["results"][0]["hits"])

    def parse_geocoding_results(self, api_results: str, meta: dict):
        geocode = json.loads(api_results)
        if not geocode["items"]:
            yield []
            return
        pos = geocode["items"][0]["position"]
        params = self._get_algolia_params(
            search_query=meta["search_query"], pos=pos, num_results=meta["num_results"], start_index=meta["start_index"]
        )
        yield self.get_zyte_request(
            f"https://{self.algolia_app_id.lower()}-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            callback=self.parse_algolia_resuts,
            additional_zyte_params={"httpRequestText": params, "httpRequestMethod": "POST", "customHttpRequestHeaders": self.headers},
            meta=meta,
        )

    def get_start_requests(self, search_query: str, location: str, num_results: int, start_index: int):
        address = quote_plus(location)
        self.geocode_params["q"] = address
        url = f"{self.geocode_url}?{urlencode(self.geocode_params)}"
        yield self.get_zyte_request(
            url=url,
            callback=self.parse_geocoding_results,
            meta={"search_query": search_query, "num_results": num_results, "start_index": start_index},
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        start_params = self._get_start_params()
        self.start_params = start_params
        self.algolia_app_id = start_params.algolia_app_id
        headers = {
            "Referer": "https://www.welcometothejungle.com/",
            "x-algolia-api-key": start_params.algolia_api_key,
            "x-algolia-application-id": self.algolia_app_id,
            "content-type": "application/x-www-form-urlencoded",
        }
        self.headers = [{"name": key, "value": value} for key, value in headers.items()]
        self.geocode_params = {
            "apiKey": start_params.here_api_key,
            "lang": "fr",
        }

    def _get_algolia_params(self, search_query: str, pos: dict, num_results: int, start_index: int) -> str:
        if start_index > 0:
            page = start_index // num_results
        else:
            page = 0
        latlng = f"{pos['lat']},{pos['lng']}"
        params = {"hitsPerPage": num_results, "query": search_query, "aroundLatLng": latlng, "aroundRadius": 2000000, "page": page}
        return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": urlencode(params)}]})

    @cache(retention_period=timedelta(hours=12), model=StartParams, source="wtj_start_params")
    def _get_start_params(self) -> StartParams:
        # We want to cache the start parmas because the browserHtml request is a bit expensive
        soup = self.inline_get_zyte(self.base_url, {"browserHtml": True, "httpResponseBody": False})
        script = soup.find("script", {"type": "text/javascript"}).get_text()  # type: ignore
        script_dict = parse_js_object(script)
        response = zyte_session.post(
            self.zyte_url,
            json={"url": "https://api.welcometothejungle.com/api/v1/search/job_filters", "httpResponseBody": True, "responseCookies": True},
        ).json()
        csrf_token = [x["value"] for x in response["responseCookies"] if x["name"] == "csrf-token"][0]
        return StartParams(
            algolia_app_id=script_dict["ALGOLIA_APPLICATION_ID"],
            algolia_api_key=script_dict["ALGOLIA_API_KEY_CLIENT"],
            here_api_key=script_dict["HERE_API_KEY"],
            api_auth_cookies=response["responseCookies"],
            csrf_token=csrf_token,
        )

    def get_job_details(self, job_offer: JobOffer) -> dict[str, Any]:
        url = f"https://api.welcometothejungle.com/api/v1/organizations/{job_offer.organization.slug}/jobs/{job_offer.slug}"
        headers = {
            "x-csrf-token": self.start_params.csrf_token,
        }
        headers = [{"name": key, "value": value} for key, value in headers.items()]
        response = zyte_session.post(
            self.zyte_url,
            json={
                "url": url,
                "httpResponseBody": True,
                "requestCookies": self.start_params.api_auth_cookies,
                "customHttpRequestHeaders": headers,
            },
        ).json()
        data = json.loads(b64decode(response["httpResponseBody"]).decode())
        return data["job"]

    def form_schema(self, job_details) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "subtitle": {"type": "string", "desciption": "Title of the job application"},
                "resume": {"type": "application/pdf"},
                "cover_letter": {"type": "string", "description": "Cover letter for the job application. Must be detailed."},
                "address": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}, "country_code": {"type": "string"}, "zip_code": {"type": "string"}},
                    "required": ["city", "country_code", "zip_code"],
                },
            },
        }
        required = ["subtitle", "resume", "cover_letter", "address"]
        if len(job_details["questions"]) > 0:
            questions = {}
            for question in job_details["questions"]:
                questions[question["question"]] = {"type": "string"}
                if question["mode"] == "mandatory":
                    required.append(question["question"])
            schema["properties"].update(questions)

        additional_fields = {}
        for field in job_details["application_fields"]:
            if field["mode"] != "disabled":
                additional_fields[field["name"]] = {"type": "string"}
                if field["mode"] == "mandatory":
                    required.append(field["name"])

        schema["properties"].update(additional_fields)
        schema["required"] = required
        return schema

    def get_form(self, job_offer: JobOffer) -> dict[str, Any]:
        details = self.get_job_details(job_offer)
        if details.get("apply_url"):
            return extract_form_fields(details["apply_url"])
        else:
            return self.form_schema(details)
