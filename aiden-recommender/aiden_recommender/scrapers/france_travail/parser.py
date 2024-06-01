from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.scrapers.field_extractors import (
    FieldExtractorBase as feb,
    MultipleFieldsExtractor as mfe,
    NestedFieldExtractor as nfe,
    FromMultipleFieldExtractor as fme,
    FieldExtractorConstant as fce,
    DateFieldExtractor as dfe,
    ListFieldExtractor as lfe,
)
from aiden_recommender.models import Coordinates, Office, Organization, Profession
import jmespath
import re


def parse_local_city(local_city):
    local_city = local_city.split(" - ")
    if len(local_city) > 1:
        return local_city[1]
    return None


def parse_salary(data):
    salary_str = jmespath.search("salaire.libelle", data)
    if not salary_str:
        return None, None, None
    salary_values = re.findall(r"\d+(?:[.,]\d+)?", salary_str)
    salary_values = [float(value.replace(",", ".")) for value in salary_values]

    if "Horaire" in salary_str:
        salary_period = "hour"
    elif "Mensuel" in salary_str:
        salary_period = "month"
    elif "Annuel" in salary_str:
        salary_period = "year"
    else:
        salary_period = "year"

    if len(salary_values) == 1:
        min_salary = max_salary = int(salary_values[0])
    elif len(salary_values) >= 2:
        min_salary = int(salary_values[0])
        max_salary = int(salary_values[1])
    else:
        min_salary = max_salary = None

    return min_salary, max_salary, salary_period


def parse_experience_level(experience_level):
    try:
        return float(experience_level.split()[0])
    except Exception:
        return experience_level


class FranceTravailParser(AbstractParser):
    source = fce("france_travail")
    geoloc = nfe(
        model=Coordinates,
        nested_fields={
            "lat": feb("lieuTravail.latitude"),
            "lng": feb("lieuTravail.longitude"),
        },
    )
    offices = lfe(
        query="lieuTravail",
        field_extractor=nfe(
            model=Office,
            nested_fields={
                "country": fce("France"),
                "local_city": feb("libelle", transform_func=parse_local_city),
            },
        ),
    )
    organization = nfe(
        model=Organization,
        nested_fields={
            "name": feb("entreprise.nom", default="unknown"),
        },
    )
    new_profession = nfe(
        model=Profession,
        nested_fields={
            "category_name": feb("romeLibelle"),
            "sub_category_name": feb("appellationlibelle"),
            "sub_category_reference": feb("romeCode"),
        },
    )
    benefits = fme(["salaire.libelle", "salaire.complement1", "salaire.complement2"])
    salary = mfe(
        fields=["salary_minimum", "salary_maximum", "salary_period"],
        extract_func=parse_salary,
    )
    published_at = dfe("dateCreation", format="%Y-%m-%dT%H:%M:%S.%fZ")
    experience_level_minimum = feb("experienceLibelle", transform_func=parse_experience_level)
    contract_type = feb("typeContratLibelle")
    education_level = feb("experienceLibelle")
    language = feb("langue", default="fr")
    name = feb("intitule")
    profile = feb("description")
    sectors = feb("secteurActiviteLibelle", transform_func=lambda x: [{"name": x}])
    reference = feb("id")
    slug = feb("origineOffre.urlOrigine", transform_func=lambda x: x.split("/")[-1])
    url = feb("origineOffre.urlOrigine")
