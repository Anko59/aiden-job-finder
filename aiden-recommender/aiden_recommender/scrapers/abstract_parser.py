from abc import ABC
from typing import Iterable

from aiden_shared.models import JobOffer
from aiden_recommender.scrapers.field_extractors import FieldExtractor


class AbstractParser(ABC):
    source: FieldExtractor

    def transform_to_job_offer(self, data) -> JobOffer:
        for field in dir(self):
            extractor = getattr(self, field)
            if isinstance(extractor, FieldExtractor):
                data.update(extractor.extract(data))
        return JobOffer(**data)

    def parse(self, data) -> Iterable[JobOffer]:
        for job_offer in data:
            yield self.transform_to_job_offer(job_offer)
