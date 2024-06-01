import hashlib
import json
from datetime import timedelta
from functools import wraps
from typing import Type, TypeVar, Optional

from aiden_recommender.tools import redis_client
from loguru import logger
from pydantic import BaseModel
from pydantic_core import from_json

T = TypeVar("T", bound="BaseModel")


def cache(retention_period: timedelta, model: Optional[Type[T]] = None, source: Optional[str] = "default"):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generate a unique cache key based on function name and arguments
            key = _generate_cache_key(func, source, *args, **kwargs)

            # Try to get the cached result
            cached_result: str | None = redis_client.get(key)  # type: ignore
            if cached_result is not None:
                logger.info("Cache HIT")
                if isinstance(results := json.loads(cached_result), list):
                    return [model.model_validate(from_json(r)) for r in results]
                else:
                    return model.model_validate(results)

            # Call the function and cache the result
            result: model | list[model] = func(self, *args, **kwargs)
            if isinstance(result, list):
                redis_client.setex(
                    key, retention_period, json.dumps([model.model_dump_json() for model in result])
                ) if model else json.dumps(result)
            else:
                redis_client.setex(key, retention_period, result.model_dump_json() if model else json.dumps(result))  # type: ignore

            return result

        return wrapper

    return decorator


def _generate_cache_key(func, source, *args, **kwargs):
    # Create a string representation of the function name and arguments
    key_data = {"function": func.__name__, "args": args, "kwargs": kwargs, "source": source}
    key_string = json.dumps(key_data, sort_keys=True)

    # Use a hash to ensure the key length is suitable for Redis
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()
