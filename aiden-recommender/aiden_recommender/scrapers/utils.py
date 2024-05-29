import hashlib
import json
from datetime import timedelta
from functools import wraps
from typing import Type, TypeVar

from aiden_recommender import redis_client
from loguru import logger
from pydantic import BaseModel
from pydantic_core import from_json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

T = TypeVar("T", bound="BaseModel")


class ChromeDriver:
    def setup_chrome_options(self) -> Options:
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--headless")
        options.add_argument("--disable-dev-shm-usage")

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        options.add_argument(f"user-agent={user_agent}")

        options.add_argument("--start-maximized")
        options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values.cookies": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.popups": 2,
                "profile.default_content_setting_values.geolocation": 2,
                "profile.default_content_setting_values.automatic_downloads": 1,
                "download.default_directory": r"C:\temp",
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False,
            },
        )
        return options

    def __init__(self):
        self.options = self.setup_chrome_options()
        self.driver = None

    def start(self):
        if self.driver is None or not self.driver.session_id:
            self.driver = webdriver.Chrome(options=self.options)
        try:
            self.driver.current_url
        except Exception:
            self.driver = webdriver.Chrome(options=self.options)
        return self.driver

    def quit(self):
        if self.driver:
            self.driver.quit()


def cache(retention_period: timedelta, model: Type[T], source: str):
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
                redis_client.setex(key, retention_period, model.model_dump_json() if model else json.dumps(result))  # type: ignore

            return result

        return wrapper

    return decorator


def _generate_cache_key(func, source, *args, **kwargs):
    # Create a string representation of the function name and arguments
    key_data = {"function": func.__name__, "args": args, "kwargs": kwargs, "source": source}
    key_string = json.dumps(key_data, sort_keys=True)

    # Use a hash to ensure the key length is suitable for Redis
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()
