from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_shared.models import Coordinates, Office, Organization, CoverImage, Logo
from datetime import datetime
from aiden_recommender.scrapers.field_extractors import FieldExtractor
from aiden_shared.constants import ISO_8601


def parse_benefits(benefits):
    return [item for sublist in benefits for item in sublist]


def parse_published_at(published_at):
    return datetime.fromtimestamp(published_at / 1000).strftime(ISO_8601)


class IndeedParser(AbstractParser):
    source = FieldExtractor("source", default="indeed")
    organization = FieldExtractor(
        "organization",
        model=Organization,
        nested_fields=[
            FieldExtractor("name", query="truncatedCompany"),
            FieldExtractor("logo", model=Logo, nested_fields=[FieldExtractor("url", query="companyBrandingAttributes.logoUrl")]),
            FieldExtractor(
                "cover_image",
                model=CoverImage,
                nested_fields=[
                    FieldExtractor(
                        "medium", model=Logo, nested_fields=[FieldExtractor("url", query="companyBrandingAttributes.headerImageUrl")]
                    ),
                ],
            ),
        ],
    )
    offices = FieldExtractor(
        "offices",
        model=Office,
        nested_fields=[
            FieldExtractor("country", "jobCountry"),
            FieldExtractor("local_city", "jobLocationCity"),
            FieldExtractor("local_state", "jobLocationState"),
        ],
        transform_func=lambda x: [x],
        default=[],
    )
    benefits = FieldExtractor("benefits", query="taxonomyAttributes[*].attributes[*].label", aggregate_func=parse_benefits, default=[])
    experience_level_minimum = FieldExtractor("experience_level_minimum", query="rankingScoresModel.bid")
    language = FieldExtractor("language", default="French")
    name = FieldExtractor("name", query="displayTitle")
    published_at = FieldExtractor("published_at", query="pubDate", transform_func=parse_published_at)
    reference = FieldExtractor("reference", query="jobkey")
    geoloc = FieldExtractor(
        "geoloc",
        model=Coordinates,
        nested_fields=[
            FieldExtractor("lat", query="hostQueryExecutionResult.data.jobData.results[0].job.location.latitude"),
            FieldExtractor("lng", query="hostQueryExecutionResult.data.jobData.results[0].job.location.longitude"),
        ],
    )
    profile = FieldExtractor("profile", query="hostQueryExecutionResult.data.jobData.results[0].job.description.text")
    url = FieldExtractor("url", query="jobkey", transform_func=lambda x: f"https://www.indeed.fr/viewjob?jk={x}")
    contract_type = FieldExtractor("contract_type", query="jobTypes[0]")
    salary_minimum = FieldExtractor("salary_minimum", query="extractedSalary.min", transform_func=lambda x: int(x))
    salary_maximum = FieldExtractor("salary_maximum", query="extractedSalary.max", transform_func=lambda x: int(x))
    salary_period = FieldExtractor("salary_period", query="extractedSalary.type")
