import os

import redis

if (redis_url := os.getenv("REDIS_URL")) is None:
    raise Exception("REDIS_URL is not set")
redis_client = redis.Redis.from_url(redis_url)
