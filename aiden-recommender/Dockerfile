FROM python:3.11.9-bullseye
RUN pip install poetry==1.8.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY aiden-recommender/pyproject.toml aiden-recommender/poetry.lock ./
COPY aiden-recommender/aiden_recommender ./aiden_recommender
COPY aiden-shared/aiden_shared /aiden_shared
RUN --mount=type=bind,source=./aiden-shared,target=/aiden-shared poetry install --no-root
