import json
from datetime import datetime
from typing import Any, Iterable
from loguru import logger
from functools import partial
from copy import deepcopy


from aiden_recommender.constants import ISO_8601
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.france_travail.parser import FranceTravailParser
from aiden_recommender.tools import async_job_search_client
from aiden_recommender.models import Request, ScraperItem


class JobSearchRequest(Request):
    params: dict[str, str]

    def get_coroutine(self, is_cached):
        return async_job_search_client.search(params=self.params)

    def _generate_cache_keys(self):
        params = deepcopy(self.params)
        # Convert the dates to days, so that the cache key is the same for the same days
        params["minCreationDate"] = datetime.strptime(params["minCreationDate"], ISO_8601).strftime("%Y-%m-%d")
        params["maxCreationDate"] = datetime.strptime(params["maxCreationDate"], ISO_8601).strftime("%Y-%m-%d")
        return ["france-travail-job-search-" + json.dumps(params)]


class FranceTravailScraper(AbstractScraper):
    parser = FranceTravailParser()

    def _parse_results(self, response: dict[str, Any], meta: dict) -> Iterable[ScraperItem]:
        logger.warning("Received response from FranceTravail")
        yield ScraperItem(raw_data=response["resultats"])

    def get_start_requests(self, search_query: str, location: str, num_results: int) -> Iterable[JobSearchRequest]:
        params = {
            "motsCles": search_query,
            "lieux": location,
            "minCreationDate": datetime(2023, 3, 1, 12, 30).strftime(ISO_8601),
            "maxCreationDate": datetime.today().strftime(ISO_8601),
            "etatPublication": "Active",
            "range": f"0-{min(num_results, 149)}",
        }
        callback = partial(self.parse_response, parser_func=self._parse_results)
        logger.warning("Sending request to FranceTravail")
        yield JobSearchRequest(params=params, callback=callback)
