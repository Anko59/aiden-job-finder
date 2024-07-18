from aiden_recommender.models import ScraperItem
import re
from typing import Any
from chompjs import parse_js_object
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.indeed.parser import IndeedParser
from aiden_recommender.scrapers.utils import extract_form_fields
from copy import deepcopy

from aiden_shared.models import JobOffer


class IndeedScraper(AbstractScraper):
    base_url = "https://fr.indeed.com"
    zyte_api_automap = {
        "browserHtml": True,
    }
    parser = IndeedParser()
    results_per_page = 15
    search_url = base_url + "/jobs?q={search_query}&l={location}&from=searchOnHP&vjk=fa2409e45b11ca41&start={start}"

    def get_start_requests(self, search_query: str, location: str, num_results: int, start_index: int):
        meta = {
            "search_query": search_query,
            "location": location,
            "num_results": num_results,
            "current_results": 0,
            "start_index": start_index,
        }
        url = self.search_url.format(start=start_index, **meta)
        yield self.get_zyte_request(url, meta=meta, callback=self.parse_overview)

    def parse_overview(self, soup, meta):
        if (script := soup.find("script", {"id": "mosaic-data"})) is not None:
            script = script.string
        else:
            return []
        results = self._extract_results(script)
        current_results = meta["current_results"] + len(results)
        meta["current_results"] = current_results
        for result in results:
            url = f"{self.base_url}{result['link']}"
            next_meta = deepcopy(meta)
            next_meta["ov_item"] = result
            yield self.get_zyte_request(url, meta=next_meta, callback=self.parse_detail)
        if len(results) == 15 and current_results < meta["num_results"]:
            yield self.get_zyte_request(
                url=self.search_url.format(start=meta["start_index"] + current_results, **meta), meta=meta, callback=self.parse_overview
            )

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

    def parse_detail(self, soup, meta):
        job_offer = meta["ov_item"]
        if soup is None:
            return [ScraperItem(raw_data=[job_offer])]
        script = soup.find("script", string=lambda text: text and "window._initialData=" in text)
        if script is None:
            return [ScraperItem(raw_data=[job_offer])]
        job_data = parse_js_object(str(script)[str(script).index("window._initialData=") :])
        job_offer = {**job_offer, **job_data}
        return [ScraperItem(raw_data=[job_offer])]

    def get_form(self, job_offer: JobOffer) -> dict[str, Any]:
        url = f"https://fr.indeed.com/applystart?jk={job_offer.reference}"
        return extract_form_fields(url)
