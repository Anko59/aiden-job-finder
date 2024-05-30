import os
import re
from datetime import datetime, timedelta
from typing import Optional

from offres_emploi import Api

from aiden_recommender.constants import ISO_8601
from aiden_recommender.scrapers.models import Coordinates, CoverImage, JobOffer, Logo, Office, Organization, Profession
from aiden_recommender.scrapers.scraper_base import ScraperBase
from aiden_recommender.scrapers.utils import cache


class FranceTravailScraper(ScraperBase):
    def __init__(self):
        self.client = Api(
            client_id=os.environ.get("FRANCE_TRAVAIL_CLIENT_ID"), client_secret=os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET")
        )
        super().__init__()

    @staticmethod
    def parse_salary(salary_str: str) -> tuple[Optional[int], Optional[int], str]:
        # Extract numeric values using regex
        salary_values = re.findall(r"\d+(?:[.,]\d+)?", salary_str)
        salary_values = [float(value.replace(",", ".")) for value in salary_values]

        # Determine the period multiplier (default is yearly)
        if "Horaire" in salary_str:
            salary_period = "hour"
        elif "Mensuel" in salary_str:
            salary_period = "month"
        elif "Annuel" in salary_str:
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

    def transform_data(self, data: dict) -> JobOffer:
        if "latitude" in data["lieuTravail"].keys():
            coordinates = [Coordinates(lat=data["lieuTravail"]["latitude"], lng=data["lieuTravail"]["longitude"])]
        else:
            coordinates = None
        local_city = data["lieuTravail"]["libelle"].split(" - ")
        if len(local_city) > 1:
            local_city = local_city[1]
        else:
            local_city = None
        offices = [Office(country="France", local_city=local_city, local_state="Île-de-France")]

        organization = Organization(name=data["entreprise"].get("nom", ""), logo=Logo(url=""), cover_image=CoverImage(medium=Logo(url="")))

        profession = Profession(
            category_name=data["romeLibelle"], sub_category_name=data["appellationlibelle"], sub_category_reference=data["romeCode"]
        )

        benefits = []
        if data.get("salaire"):
            benefits.append(data["salaire"].get("libelle", ""))
            if data["salaire"].get("complement1"):
                benefits.append(data["salaire"].get("complement1"))
            if data["salaire"].get("complement2"):
                benefits.append(data["salaire"].get("complement2"))

        if (salaire_libelle := data["salaire"].get("libelle")) is not None:
            salary_minimum, salary_maximum, salary_period = self.parse_salary(salaire_libelle)
        else:
            salary_minimum = salary_maximum = salary_period = None
        # Handle date parsing
        published_at = datetime.strptime(data["dateCreation"], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            experience_level_minimum = float(data["experienceLibelle"].split()[0])
            has_experience_level_minimum = True
        except Exception:
            experience_level_minimum = None
            has_experience_level_minimum = False
        job_offer = JobOffer(
            benefits=benefits,
            contract_type=data["typeContratLibelle"],
            education_level=data["experienceLibelle"],
            experience_level_minimum=experience_level_minimum,
            has_experience_level_minimum=has_experience_level_minimum,
            language="fr",
            name=data["intitule"],
            new_profession=profession,
            offices=offices,
            organization=organization,
            profile=data["description"],
            published_at=published_at,
            salary_maximum=salary_maximum,
            salary_minimum=salary_minimum,
            salary_period=salary_period,
            salary_currency="EUR",
            sectors=[{"name": data.get("secteurActiviteLibelle", "unkown")}],
            geoloc=coordinates,
            reference=data["id"],
            slug=data["origineOffre"]["urlOrigine"].split("/")[-1],
        )

        return job_offer

    @cache(retention_period=timedelta(hours=12), model=JobOffer, source="france_travail")
    def _fetch_results(self, search_query: str, location: str) -> list[JobOffer]:
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
        job_offers = [self.transform_data(data) for data in search_results["resultats"]]
        return job_offers
