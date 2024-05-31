import json
import re
from typing import Any
from aiden_recommender.scrapers.utils import chrome_driver, cache
from aiden_recommender.scrapers.models import JobOffer, Coordinates, Logo, CoverImage, Organization, Office
from aiden_recommender.scrapers.scraper_base import ScraperBase
from chompjs import parse_js_object
from datetime import datetime, timedelta


class IndeedScraper(ScraperBase):
    base_url = "https://fr.indeed.com"

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
        try:
            return data["mosaic-provider-jobcards"]["metaData"]["mosaicProviderJobCardsModel"]["results"]
        except KeyError:
            return []

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
            "benefits": [x["label"] for x in data["taxonomyAttributes"][3]["attributes"]],
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
        if (salary_info := data.get("extractedSalary")) is not None:
            args.update(
                {
                    "salary_minimum": salary_info.get("min"),
                    "salary_maximum": salary_info.get("max"),
                    "salary_period": salary_info.get("type"),
                }
            )

        if len(data["jobTypes"]) > 0:
            args["contract_type"] = data["jobTypes"][0]

        job_offer = JobOffer(**args)
        return job_offer

    @cache(retention_period=timedelta(days=1), model=JobOffer, source="indeed")
    def _fetch_results(self, search_query: str, location: str, start=0) -> list[dict[str, Any]]:
        url = f"{self.base_url}/jobs?q={search_query}&l={location}&from=searchOnHP&vjk=fa2409e45b11ca41&start={start}"

        soup = chrome_driver.fetch_page(url)

        script = soup.find("script", {"id": "mosaic-data"}).string

        results = self._extract_results(script)  # type: ignore
        descriptions = self._extract_job_descriptions(results)
        for i, result in enumerate(results):
            result["jobDescription"] = descriptions[i]
        return [self.transform_to_job_offer(result) for result in results]

    def _extract_job_descriptions(self, results: list[dict[str, Any]]) -> list[str]:
        urls = [f"{self.base_url}{result['link']}" for result in results]
        soups = chrome_driver.fetch_pages(urls)
        return [self._extract_description(soup) for soup in soups]

    @staticmethod
    def _extract_description(soup) -> str:
        if soup is not None:
            return ""
        script = soup.find("script", {"type": "application/ld+json"})
        if script is None:
            return ""
        job_data = json.loads(script.string)
        description = job_data["description"]
        return description
