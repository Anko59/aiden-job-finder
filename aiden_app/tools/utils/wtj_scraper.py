import json
from typing import List, Optional

import requests
from pydantic import BaseModel

from .chrome_driver import ChromeDriver


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
    description: str
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

    def _fetch_results(self, search_query: str, location: str):
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.welcometothejungle.com/",
            "x-algolia-api-key": "4bd8f6215d0cc52b26430765769e65a0",
            "x-algolia-application-id": "CSEKHVMS53",
            "content-type": "application/x-www-form-urlencoded",
            "Origin": "https://www.welcometothejungle.com",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }

        response = requests.post(
            "https://csekhvms53-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser&search_origin=job_search_client",
            headers=headers,
            data=json.dumps({"requests": [{"indexName": "wttj_jobs_production_fr", "params": f"hitsPerPage=300&query={search_query}"}]}),
        )

        job_offers = [JobOffer(**offer) for offer in response.json()["results"][0]["hits"]]
        return [job_offer.model_dump() for job_offer in job_offers]

    def search_jobs(self, search_query: str, location: str, num_results: int = 15, *args, **kwargs):
        return self._fetch_results(search_query, location)[:num_results]
