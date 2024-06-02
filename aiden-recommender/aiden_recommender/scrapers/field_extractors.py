from pydantic import BaseModel
import jmespath
from pydantic_core import ValidationError
from loguru import logger


class FieldExtractor:
    def __init__(
        self,
        field: str | list,
        query: str | list[str] = None,
        default: any = None,
        transform_func: callable = None,
        model: BaseModel = None,
        nested_fields: list["FieldExtractor"] = [],
        aggregate_func: callable = None,
    ) -> None:
        self.field = field
        self.query = query
        self.default = default
        self.transform_func = transform_func if transform_func else lambda x: x
        self.model = model
        self.nested_fields = nested_fields
        self.aggregate_func = aggregate_func if aggregate_func else lambda x: x

    @staticmethod
    def select(data: dict, query: str) -> any:
        if not query:
            return data
        return jmespath.search(query, data)

    def extract(self, data: dict) -> dict:
        if isinstance(self.query, list):
            result = [self.select(data, q) for q in self.query]
        elif isinstance(self.query, str):
            result = self.select(data, self.query)
        elif self.query is None:
            result = data
        else:
            raise ValueError("Query should be string or list of strings")

        if self.model:
            try:
                if isinstance(result, list):
                    new_result = []
                    for item in result:
                        model_args = {}
                        for extractor in self.nested_fields:
                            model_args.update(extractor.extract(item))
                        new_result.append(self.model(**model_args))
                    result = new_result
                else:
                    model_args = {}
                    for extractor in self.nested_fields:
                        model_args.update(extractor.extract(result))
                    result = self.model(**model_args)
            except ValidationError as e:
                logger.warning(f"Error while extracting nested fields: {e}")
                result = None

        if isinstance(result, list):
            result = [self.transform_func(item) for item in result]
            result = self.aggregate_func(result)
        elif result is not None:
            result = self.transform_func(result)

        if result is None or result == "" or result == [] or result == {} or result == data:
            result = self.default

        if isinstance(self.field, list):
            return {field: value for field, value in zip(self.field, result)}

        return {self.field: result}
