FROM python:3.11.9-bullseye
RUN pip install poetry==1.8.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./

# install dependencies, not the project (no root)
RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

# Install necessary packages for selenium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY aiden_app ./
COPY aiden_project ./
COPY manage.py ./

EXPOSE 8000
CMD poetry run python manage.py runserver 0.0.0.0:8000
