from pydantic import BaseModel
from abc import ABC, abstractmethod
import jmespath
from datetime import datetime
from pydantic_core import ValidationError
from loguru import logger


class AbstractFieldExtractor(ABC):
    @staticmethod
    def select(data: dict, query: str) -> any:
        if not query:
            return data
        return jmespath.search(query, data)

    @abstractmethod
    def _extract(self, data: dict) -> any:
        pass

    @abstractmethod
    def extract(self, data: dict, field: str) -> dict:
        pass


class FieldExtractorBase(AbstractFieldExtractor):
    def __init__(self, query: str, default: any = None, transform_func: callable = None) -> None:
        self.query = query
        self.default = default
        self.transform_func = transform_func if transform_func else lambda x: x

    def _extract(self, data: dict, query=None) -> any:
        query = query if query is not None else self.query
        result = self.select(data, query)
        return self.transform_func(result) if result is not None else self.default

    def extract(self, data, field):
        result = self._extract(data)
        data[field] = result
        return data


class NestedFieldExtractor(AbstractFieldExtractor):
    def __init__(self, model: BaseModel, nested_fields: dict[str, AbstractFieldExtractor]) -> None:
        self.model = model
        self.nested_fields = nested_fields

    def _extract(self, data: dict) -> any:
        try:
            return self.model(**{field: extractor._extract(data) for field, extractor in self.nested_fields.items()})
        except ValidationError as e:
            logger.warning(f"Error while extracting nested fields: {e}")
            return None

    def extract(self, data, field):
        data[field] = self._extract(data)
        return data


class MultipleFieldsExtractor(AbstractFieldExtractor):
    def __init__(self, fields: list[str], extract_func, **kwargs) -> None:
        self.fields = fields
        self.extract_func = extract_func
        self.kwargs = kwargs

    def _extract(self, data: dict) -> any:
        result = self.extract_func(data, **self.kwargs)
        if len(result) != len(self.fields):
            raise ValueError("Length of fields and result should be the same")
        return {field: value for field, value in zip(self.fields, result)}

    def extract(self, data, field):
        result = self._extract(data)
        for field, value in zip(self.fields, result):
            data[field] = value
        return data


class FromMultipleFieldExtractor(FieldExtractorBase):
    def __init__(self, queries: list[str], **kwargs) -> None:
        self.queries = queries
        self.aggregate_func = kwargs.get("aggregate_func", lambda x: x)
        kwargs.setdefault("query", None)
        super().__init__(**kwargs)

    def _extract(self, data: dict) -> any:
        results = [super()._extract(data, query) for query in self.queries]
        results = [result for result in results if result is not None]
        return self.aggregate_func(results)


class FieldExtractorConstant(FieldExtractorBase):
    def __init__(self, value: any) -> None:
        self.value = value

    def _extract(self, data: dict) -> any:
        return self.value


class DateFieldExtractor(FieldExtractorBase):
    def __init__(self, query: str, format: str, **kwargs) -> None:
        self.format = format
        super().__init__(query, **kwargs)

    @staticmethod
    def parse_date(date: str, format: str) -> str:
        return datetime.strptime(date, format).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _extract(self, data: dict) -> any:
        result = super()._extract(data)
        return self.parse_date(result, self.format)


class ListFieldExtractor(AbstractFieldExtractor):
    def __init__(self, query: str, field_extractor: AbstractFieldExtractor) -> None:
        self.query = query
        self.field_extractor = field_extractor

    def _extract(self, data: dict) -> any:
        result = self.select(self.query, data)
        if not isinstance(result, list):
            result = [result]
        return [self.field_extractor._extract(item) for item in result]

    def extract(self, data, field):
        result = self._extract(data)
        data[field] = result
        return data
