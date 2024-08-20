FROM python:3.11.9-bullseye
RUN pip install poetry==1.8.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=0 \
    POETRY_VIRTUALENVS_CREATE=0 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Install necessary packages for pdflatex
RUN apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

COPY ./aiden-web/pyproject.toml ./aiden-web/poetry.lock ./
COPY ./aiden-web/aiden_app ./
COPY ./aiden-web/aiden_project ./
COPY ./aiden-web/manage.py ./
COPY ./aiden-shared/aiden_shared /aiden_shared
RUN --mount=type=bind,source=./aiden-shared,target=/aiden-shared poetry install --no-root

EXPOSE 8000
CMD poetry run python manage.py makemigrations && \
    poetry run python manage.py migrate && \
    poetry run python manage.py runserver 0.0.0.0:8000
