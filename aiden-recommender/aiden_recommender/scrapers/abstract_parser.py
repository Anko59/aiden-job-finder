from abc import ABC

from aiden_recommender.models import JobOffer
from aiden_recommender.scrapers.field_extractors import FieldExtractor


class AbstractParser(ABC):
    source: FieldExtractor

    def transform_to_job_offer(self, data) -> JobOffer:
        for field in dir(self):
            extractor = getattr(self, field)
            if isinstance(extractor, FieldExtractor):
                data.update(extractor.extract(data))
        return JobOffer(**data)
