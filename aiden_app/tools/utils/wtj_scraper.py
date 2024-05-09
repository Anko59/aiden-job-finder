import json
from datetime import datetime
from typing import Optional
from urllib import parse

import requests
from chompjs import parse_js_object
from loguru import logger
from pydantic import BaseModel
from selenium.webdriver.common.by import By

from .chrome_driver import ChromeDriver


class Coordinates(BaseModel):
    lat: float
    lng: float


class Office(BaseModel):
    country: str
    local_city: Optional[str] = None
    local_state: Optional[str] = None


class Profession(BaseModel):
    category_name: str
    sub_category_name: str
    sub_category_reference: str


class Organization(BaseModel):
    name: str
    description: Optional[str] = None
    nb_employees: Optional[int] = None


class JobOffer(BaseModel):
    remote: Optional[str] = None
    salary_period: Optional[str | dict] = None
    salary_yearly_minimum: Optional[int] = None
    has_contract_duration: Optional[bool] = None
    contract_duration_maximum: Optional[int] = None
    published_at: str
    _reference: str
    name: str
    _geoloc: list[Coordinates]
    has_experience_level_minimum: bool
    offices: list[Office]
    new_profession: Optional[Profession] = None
    has_education_level: Optional[bool] = None
    sectors: list[dict]
    language: str
    education_level: Optional[str] = None
    has_salary_yearly_minimum: Optional[bool] = None
    benefits: list[str]
    profile: Optional[str] = None
    has_remote: Optional[bool] = None
    organization: Organization
    salary_currency: Optional[str] = None
    contract_duration_minimum: Optional[int] = None
    salary_minimum: Optional[int] = None
    experience_level_minimum: Optional[float] = None
    contract_type: str
    salary_maximum: Optional[int] = None
    _slug: str

    def to_url(self) -> str:
        return f"https://www.welcometothejungle.com/fr/companies/{self.organization.name.lower()}/jobs/{self._slug}?&o={self._reference}"

    def metadata_repr(self) -> str:
        """Returns a language representation of the offer metadata (location, company, profile sought for etc...)."""
        published_date = datetime.strptime(self.published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")
        metadata = f"This job offer named '{self.name}' was published on {published_date}."
        if self.organization and self.organization.name:
            metadata += f" It is from '{self.organization.name}'."
        if self.offices:
            locations = ", ".join([f"{office.local_city}, {office.country}" for office in self.offices if office.local_city])
            if locations:
                metadata += f" It is located in {locations}."
        if self.sectors:
            sectors = ", ".join([sector["name"] for sector in self.sectors])
            metadata += f" Sectors: {sectors}."
        if self.salary_period:
            metadata += f" Salary period: {self.salary_period}."
        if self.salary_currency:
            metadata += f" Salary currency: {self.salary_currency}."
        if self.salary_minimum is not None and self.salary_maximum is not None:
            metadata += f" Salary range: {self.salary_minimum}-{self.salary_maximum} per {self.salary_period}."
        return metadata

    def company_repr(self) -> str:
        """Return a language representation of the company posting the offer."""
        company_representation = f"The company '{self.organization.name}'"
        if self.organization.description:
            company_representation += f" is described as '{self.organization.description}'."
        else:
            company_representation += " has no description."
        if self.organization.nb_employees:
            company_representation += f" It has {self.organization.nb_employees} employees"
        return company_representation

    def requirements_repr(self) -> str:
        """Returns a string representation of the profile sought for the position."""
        if self.profile:
            return f"The profile sought for this position is: '{self.profile}'."
        else:
            return "No specific profile requirements mentioned."


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

    def _get_algolia_params(self, search_query: str, latlng: str, page: int):
        params = {"hitsPerPage": 1000, "query": search_query, "aroundLatLng": latlng, "aroundRadius": 200000000000000, "page": page}
        return json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": parse.urlencode(params)}]})

    def _fetch_results(self, search_query: str, location: str, page=0):
        # Query hereapi for location coordinates
        self.autocomplete_params["q"] = location
        response = requests.get("https://autocomplete.search.hereapi.com/v1/autocomplete", params=self.autocomplete_params)
        self.lookup_params["id"] = response.json()["items"][0]["id"]
        response = requests.get("https://lookup.search.hereapi.com/v1/lookup", params=self.lookup_params)
        latlng = ",".join([str(x) for x in response.json()["position"].values()])

        # Query algolia
        params = self._get_algolia_params(search_query, latlng, page=page)
        response = requests.post(
            "https://csekhvms53-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",  # noqa
            headers=self.headers,
            data=params,
        )

        response.raise_for_status()
        job_offers = [JobOffer(**offer) for offer in response.json()["results"][0]["hits"]]
        return [job_offer.model_dump(exclude_none=True) for job_offer in job_offers]

    def search_jobs(self, search_query: str, location: str, num_results: int = 15, *args, **kwargs):
        return self._fetch_results(search_query, location)[:num_results]
