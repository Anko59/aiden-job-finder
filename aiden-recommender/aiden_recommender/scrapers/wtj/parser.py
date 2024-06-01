from aiden_recommender.scrapers.abstract_parser import AbstractParser
from aiden_recommender.scrapers.field_extractors import FieldExtractorBase as feb


def parse_url(data):
    return (
        f"https://www.welcometothejungle.com/fr/companies/{data['organization']['name'].lower()}/jobs/{data['slug']}?&o={data['reference']}"  # noqa
    )


class WtjParser(AbstractParser):
    source = "wtj"
    url = feb(query=None, transform_func=parse_url)
    geoloc = feb(query="_geloc", transform_func=lambda x: x[0])
