from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.scrapers.field_extractors import FieldExtractor
from aiden_shared.models import Coordinates, Office, Organization, Profession
from aiden_shared.constants import ISO_8601
from datetime import datetime
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


def parse_published_at(published_at):
    return datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%S.%fZ").strftime(ISO_8601)


class FranceTravailParser(AbstractParser):
    source = FieldExtractor("source", default="france_travail")
    geoloc = FieldExtractor(
        "geoloc",
        model=Coordinates,
        nested_fields=[
            FieldExtractor("lat", query="lieuTravail.latitude"),
            FieldExtractor("lng", query="lieuTravail.longitude"),
        ],
    )
    offices = FieldExtractor(
        "offices",
        query="lieuTravail",
        model=Office,
        nested_fields=[
            FieldExtractor("country", default="France"),
            FieldExtractor("local_city", query="libelle", transform_func=parse_local_city),
        ],
        transform_func=lambda x: [x],
    )
    organization = FieldExtractor(
        "organization",
        model=Organization,
        nested_fields=[
            FieldExtractor("name", query="entreprise.nom", default="unknown"),
        ],
    )
    new_profession = FieldExtractor(
        "new_profession",
        model=Profession,
        nested_fields=[
            FieldExtractor("category_name", query="romeLibelle"),
            FieldExtractor("sub_category_name", query="appellationlibelle"),
            FieldExtractor("sub_category_reference", query="romeCode"),
        ],
    )
    benefits = FieldExtractor("benefits", query=["salaire.libelle", "salaire.complement1", "salaire.complement2"], default=[])
    salary = FieldExtractor(
        ["salary_minimum", "salary_maximum", "salary_period"],
        transform_func=parse_salary,
    )
    published_at = FieldExtractor("published_at", query="dateCreation", transform_func=parse_published_at)
    experience_level_minimum = FieldExtractor("experience_level_minimum", query="experienceLibelle", transform_func=parse_experience_level)
    contract_type = FieldExtractor("contract_type", query="typeContratLibelle")
    education_level = FieldExtractor("education_level", query="experienceLibelle")
    language = FieldExtractor("language", query="langue", default="fr")
    name = FieldExtractor("name", query="intitule")
    profile = FieldExtractor("profile", query="description")
    sectors = FieldExtractor("sectors", query="secteurActiviteLibelle", transform_func=lambda x: [{"name": x}])
    reference = FieldExtractor("reference", query="id")
    url = FieldExtractor("url", query="origineOffre.urlOrigine")
