import json
from typing import List, Optional
from urllib import parse
import requests
from pydantic import BaseModel

from .chrome_driver import ChromeDriver
from selenium.webdriver.common.by import By
from chompjs import parse_js_object


class Coordinates(BaseModel):
    lat: float
    lng: float


class Office(BaseModel):
    country: str
    local_city: Optional[str]
    local_state: Optional[str]


class Profession(BaseModel):
    category_name: str
    sub_category_name: str
    sub_category_reference: str


class Organization(BaseModel):
    name: str
    description: Optional[str]
    nb_employees: Optional[int]


class JobOffer(BaseModel):
    remote: Optional[str]
    salary_period: Optional[str | dict]
    salary_yearly_minimum: Optional[int]
    has_contract_duration: Optional[bool]
    contract_duration_maximum: Optional[int]
    published_at: str
    reference: str
    name: str
    _geoloc: List[Coordinates]
    has_experience_level_minimum: bool
    offices: List[Office]
    new_profession: Profession
    has_education_level: Optional[bool]
    sectors: List[dict]
    language: str
    education_level: Optional[str]
    has_salary_yearly_minimum: Optional[bool]
    benefits: List[str]
    profile: Optional[str]
    has_remote: Optional[bool]
    organization: Organization
    salary_currency: Optional[str]
    contract_duration_minimum: Optional[int]
    salary_minimum: Optional[int]
    experience_level_minimum: Optional[float]
    contract_type: str
    salary_maximum: Optional[int]
    slug: str

    def to_url(self) -> str:
        return f"https://www.welcometothejungle.com/fr/companies/{self.organization.name.lower()}/jobs/{self.slug}?&o={self.reference}"


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

    def _get_algolia_params(self, search_query: str, latlng: str):
        params = {"hitsPerPage": 300, "query": search_query, "aroundLatLng": latlng, "aroundRadius": 2000000}
        return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": parse.urlencode(params)}]})

    def _fetch_results(self, search_query: str, location: str):
        self.autocomplete_params["q"] = location
        response = requests.get("https://autocomplete.search.hereapi.com/v1/autocomplete", params=self.autocomplete_params)
        self.lookup_params["id"] = response.json()["items"][0]["id"]
        response = requests.get("https://lookup.search.hereapi.com/v1/lookup", params=self.lookup_params)
        latlng = ",".join([str(x) for x in response.json()["position"].values()])
        params = self._get_algolia_params(search_query, latlng)
        response = requests.post(
            "https://csekhvms53-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            headers=self.headers,
            data=params,
        )

        job_offers = [JobOffer(**offer) for offer in response.json()["results"][0]["hits"]]
        return [job_offer.model_dump(exclude_none=True) for job_offer in job_offers]

    def search_jobs(self, search_query: str, location: str, num_results: int = 15, *args, **kwargs):
        return self._fetch_results(search_query, location)[:num_results]
