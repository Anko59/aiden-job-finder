import os
from datetime import datetime

from offres_emploi import Api

from aiden_recommender.constants import ISO_8601
from aiden_recommender.scrapers.abstract_scraper import AbstractScraper
from aiden_recommender.scrapers.france_travail.parser import FranceTravailParser


class FranceTravailScraper(AbstractScraper):
    client = Api(client_id=os.environ.get("FRANCE_TRAVAIL_CLIENT_ID"), client_secret=os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET"))

    parser = FranceTravailParser()

    def _fetch_results(self, search_query: str, location: str) -> list[dict]:
        params = {
            "motsCles": search_query,
            "lieux": location,
            "minCreationDate": datetime(2023, 3, 1, 12, 30).strftime(ISO_8601),
            "maxCreationDate": datetime.today().strftime(ISO_8601),
            "etatPublication": "Active",
            "range": "0-149",
        }

        # Perform the seatrch
        search_results = self.client.search(params=params)
        return search_results["resultats"]
