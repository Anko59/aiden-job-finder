import json
import re
from typing import Any
from aiden_recommender.scrapers.utils import cache
from chompjs import parse_js_object
from datetime import timedelta
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.indeed.parser import IndeedParser


class IndeedScraper(AbstractScraper):
    base_url = "https://fr.indeed.com"
    zyte_api_automap = {
        "browserHtml": True,
    }
    parser = IndeedParser()

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

    def _fetch_results(self, search_query: str, location: str, start=0) -> list[dict[str, Any]]:
        url = f"{self.base_url}/jobs?q={search_query}&l={location}&from=searchOnHP&vjk=fa2409e45b11ca41&start={start}"

        soup = self.get(url)

        script = soup.find("script", {"id": "mosaic-data"}).string

        results = self._extract_results(script)  # type: ignore
        descriptions = self._extract_job_descriptions(results)
        for i, result in enumerate(results):
            result["jobDescription"] = descriptions[i]
        return results

    def _extract_job_descriptions(self, results: list[dict[str, Any]]) -> list[str]:
        urls = [f"{self.base_url}{result['link']}" for result in results]
        return [self._extract_description(url) for url in urls]

    @cache(retention_period=timedelta(days=1), source="indeed")
    def _extract_description(self, url) -> str:
        soup = self.get(url)
        if soup is not None:
            return ""
        script = soup.find("script", {"type": "application/ld+json"})
        if script is None:
            return ""
        job_data = json.loads(script.string)
        description = job_data["description"]
        return description
