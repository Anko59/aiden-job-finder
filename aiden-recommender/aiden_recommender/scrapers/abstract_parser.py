from aiden_recommender.models import JobOffer
from aiden_recommender.scrapers.field_extractors import AbstractFieldExtractor
from abc import ABC


class AbstractParser(ABC):
    def transform_to_job_offer(self, data) -> JobOffer:
        for field in dir(self):
            extractor = getattr(self, field)
            if isinstance(extractor, AbstractFieldExtractor):
                data = extractor.extract(data, field)
        return JobOffer(**data)

    def parse(self, data: list) -> list[JobOffer]:
        return [self.transform_to_job_offer(item) for item in data]
