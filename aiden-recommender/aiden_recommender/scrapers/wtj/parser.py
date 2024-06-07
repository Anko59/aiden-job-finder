from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.scrapers.field_extractors import FieldExtractor


def parse_url(data):
    return (
        f"https://www.welcometothejungle.com/fr/companies/{data['organization']['name'].lower()}/jobs/{data['slug']}?&o={data['reference']}"  # noqa
    )


class WtjParser(AbstractParser):
    source = FieldExtractor("source", default="wtj")
    url = FieldExtractor("url", transform_func=parse_url)
    geoloc = FieldExtractor("geoloc", query="_geoloc", aggregate_func=lambda x: x[0])
