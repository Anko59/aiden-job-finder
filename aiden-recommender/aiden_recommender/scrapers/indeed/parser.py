from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.models import Coordinates, Office, Organization, CoverImage
from datetime import datetime
from aiden_recommender.scrapers.field_extractors import (
    FieldExtractorBase as feb,
    NestedFieldExtractor as nfe,
    FieldExtractorConstant as fce,
    ListFieldExtractor as lfe,
)


def parse_benefits(benefits):
    return [item for sublist in benefits for item in sublist]


def parse_published_at(published_at):
    return datetime.fromtimestamp(published_at / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")


class IndeedParser(AbstractParser):
    source = "indeed"
    organization = nfe(
        model=Organization,
        nested_fields={
            "name": feb(query="truncatedCompany"),
            "logo": feb(query="companyBrandingAttributes.logoUrl"),
            "cover_image": nfe(
                model=CoverImage,
                nested_fields={
                    "medium": feb(query="companyBrandingAttributes.headerImageUrl"),
                },
            ),
        },
    )
    offices = lfe(
        query=None,
        field_extractor=nfe(
            model=Office,
            nested_fields={
                "country": fce("France"),
                "local_city": feb("jobLocationCity"),
                "local_state": feb("jobLocationState"),
            },
        ),
    )
    benefits = feb(query="taxonomyAttributes.3.attributes.label", transform_func=parse_benefits)
    experience_level_minimum = feb(query="rankingScoresModel.bid")
    language = fce("French")
    name = feb(query="displayTitle")
    published_at = feb(query="pubDate", transform_func=parse_published_at)
    reference = feb(query="jobkey")
    slug = feb(query="jobkey")
    geoloc = nfe(
        model=Coordinates,
        nested_fields={
            "lat": feb(query="_geoloc.lat"),
            "lng": feb(query="_geoloc.lng"),
        },
    )
    profile = feb(query="jobDescription")
    url = feb(query="jobkey", transform_func=lambda x: f"https://www.indeed.fr/viewjob?jk={x}")
    contract_type = feb(query="jobTypes.0")
    salary_minimum = feb(query="extractedSalary.min")
    salary_maximum = feb(query="extractedSalary.max")
    salary_period = feb(query="extractedSalary.type")
