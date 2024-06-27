import hashlib
import json
from datetime import timedelta
from functools import wraps
from typing import Any, Optional, Type, TypeVar

from loguru import logger
from pydantic import BaseModel
from pydantic_core import from_json
from bs4 import BeautifulSoup

from aiden_shared.tools import redis_client
from aiden_recommender.tools import zyte_session

T = TypeVar("T", bound="BaseModel")


def cache(retention_period: timedelta, model: Type[T], source: Optional[str] = "default"):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generate a unique cache key based on function name and arguments
            key = _generate_cache_key(func, source, *args, **kwargs)

            # Try to get the cached result
            cached_result: str | None = redis_client.get(key)  # type: ignore
            if cached_result is not None:
                logger.warning("Cache HIT")
                if isinstance(results := json.loads(cached_result), list):
                    return [model.model_validate(from_json(r)) for r in results]
                else:
                    return model.model_validate(results)

            # Call the function and cache the result
            result: model | list[model] = func(self, *args, **kwargs)
            if isinstance(result, list):
                redis_client.setex(key, retention_period, json.dumps([model.model_dump_json() for model in result]))
            else:
                redis_client.setex(key, retention_period, result.model_dump_json() if model else json.dumps(result))

            return result

        return wrapper

    return decorator


def _generate_cache_key(func, source, *args, **kwargs):
    # Create a string representation of the function name and arguments
    key_data = {"function": func.__name__, "args": args, "kwargs": kwargs, "source": source}
    key_string = json.dumps(key_data, sort_keys=True)

    # Use a hash to ensure the key length is suitable for Redis
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


base_fields = {
    "type": "object",
    "properties": {
        "resume": {"type": "application/pdf"},
        "cover_letter": {"type": "string", "description": "Cover letter for the job application. Must be detailed."},
    },
}


def extract_form_fields(apply_url: str) -> dict[str, Any]:
    try:
        response = zyte_session.post("https://api.zyte.com/v1/extract", {"url": apply_url, "browserHtml": True, "httpResponseBody": False})
        soup = BeautifulSoup(response["browserHtml"], "html.parser")
    except Exception as e:
        print(f"Error fetching the form: {e}")
        return base_fields
    form = soup.find("form")
    if not form:
        print("No form found on the page")
        return base_fields

    fields = []

    for label in form.find_all("label"):
        field_info = {}

        # Find the related input, select, or textarea field
        input_field = None

        # Check if the label has a 'for' attribute linking to an input field
        if label.has_attr("for"):
            input_id = label["for"]
            input_field = form.find(id=input_id)
        else:
            # If no 'for' attribute, look for input/select/textarea directly inside label
            input_field = label.find(["input", "select", "textarea"])

        if input_field and input_field.get("type") != "hidden":
            field_info["question"] = label.get_text(strip=True)
            field_info["field_name"] = input_field.get("name")
            field_info["data_type"] = input_field.get("type")
            fields.append(field_info)

    properties = {}
    for field in fields:
        field_name = field["field_name"]
        if field_name in properties:
            properties[field_name]["description"].append(field["question"])
        else:
            properties[field_name] = {
                "type": "string" if field["data_type"] in ["text", "email", "password"] else field["data_type"],
                "description": [field["question"]],
            }

    # Flatten the descriptions list into a single string
    for field_name, field_info in properties.items():
        field_info["description"] = " / ".join(field_info["description"])

    if not properties:
        return base_fields

    json_schema = {"type": "object", "properties": properties}

    return json_schema
