import json
import re
from typing import Any
from aiden_recommender.scrapers.utils import ChromeDriver, cache
from aiden_recommender.scrapers.models import JobOffer, Coordinates, Logo, CoverImage, Organization, Office
from aiden_recommender.scrapers.scraper_base import ScraperBase
from chompjs import parse_js_object
from unidecode import unidecode
from datetime import datetime, timedelta


class IndeedScraper(ScraperBase):
    def __init__(self):
        self.base_url = "https://fr.indeed.com"
        super().__init__()

    def _extract_results(self, script: str) -> list[dict[str, Any]]:
        data = {}
        for line in script.split("\n"):
            line = line.strip()
            if line.startswith("window.mosaic.providerData"):
                key = line.split("=")[0]
                value = "=".join(line.split("=")[1:])
                key = re.findall(r'"(.*?)"', key)
                if len(key):
                    data[key[0]] = parse_js_object(value)
        return data["mosaic-provider-jobcards"]["metaData"]["mosaicProviderJobCardsModel"]["results"]

    @staticmethod
    def parse_salary(salary_str: str):
        # Extract numeric values using regex
        salary_values = re.findall(r"\d+(?:\s\d+)*", salary_str)
        salary_values = [float(unidecode(value).replace(",", ".").replace(" ", "")) for value in salary_values]

        # Determine the period multiplier (default is yearly)
        if "heure" in salary_str:
            salary_period = "hour"
        elif "mois" in salary_str:
            salary_period = "month"
        elif "an" in salary_str:
            salary_period = "year"
        else:
            salary_period = "year"

        # Parse the minimum and maximum salary values
        if len(salary_values) == 1:
            min_salary = max_salary = int(salary_values[0])
        elif len(salary_values) >= 2:
            min_salary = int(salary_values[0])
            max_salary = int(salary_values[1])
        else:
            min_salary = max_salary = None

        return min_salary, max_salary, salary_period

    @classmethod
    def transform_to_job_offer(cls, data: dict) -> JobOffer:
        coordinates = [Coordinates(lat=loc["lat"], lng=loc["lng"]) for loc in data.get("_geoloc", [])]
        logo = Logo(url=data["companyBrandingAttributes"].get("logoUrl", ""))
        cover_image = CoverImage(medium=Logo(url=data["companyBrandingAttributes"].get("headerImageUrl", "")))
        organization = Organization(
            name=data["truncatedCompany"],
            logo=logo,
            cover_image=cover_image,
        )
        office = Office(country=data["jobLocationCity"], local_state=data["jobLocationState"])
        args = {
            "benefits": data["taxonomyAttributes"][3]["attributes"],
            "contract_type": data["jobTypes"][0],
            "experience_level_minimum": data.get("rankingScoresModel", {}).get("bid"),
            "has_experience_level_minimum": True,
            "language": "French",
            "name": data["displayTitle"],
            "offices": [office],
            "organization": organization,
            "published_at": datetime.fromtimestamp(data["pubDate"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reference": data["jobkey"],
            "slug": data["jobkey"],
            "geoloc": coordinates,
            "profile": data.get("jobDescription"),
            "url": f"{cls.base_url}/viewjob?jk={data['jobkey']}",
        }
        if (salary_text := data["salarySnippet"].get("text")) is not None:
            min_salary, max_salary, salary_period = cls.parse_salary(salary_text)
            args.update({"salary_minimum": min_salary, "salary_maximum": max_salary, "salary_period": salary_period})
        job_offer = JobOffer(**args)
        return job_offer

    @cache(retention_period=timedelta(hours=12), model=JobOffer, source="indeed")
    def _fetch_results(self, search_query: str, location: str, start=0) -> list[dict[str, Any]]:
        url = f"{self.base_url}/jobs?q={search_query}&l={location}&from=searchOnHP&vjk=fa2409e45b11ca41&start={start}"

        soup = ChromeDriver.fetch_page(url)

        script = soup.find("script", {"id": "mosaic-data"}).string

        results = self._extract_results(script)  # type: ignore
        descriptions = self._extract_job_descriptions(results)
        for i, result in enumerate(results):
            result["jobDescription"] = descriptions[i]
        return [self.transform_to_job_offer(result) for result in results]

    def _extract_job_descriptions(self, results: list[dict[str, Any]]) -> list[str]:
        urls = [f"{self.base_url}{result['jobCardUrl']}" for result in results]
        soups = ChromeDriver.fetch_pages(urls)
        return [self._extract_description(soup) for soup in soups]

    @staticmethod
    def _extract_description(soup) -> str:
        script = soup.find("script", {"type": "application/ld+json"})
        if script is not None:
            job_data = json.loads(script.string)
            description = job_data["description"]
            return description
        return ""
