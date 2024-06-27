from typing import Annotated
from uuid import UUID

from fastapi import FastAPI
from fastapi.params import Body
from pydantic import BaseModel
from redis.exceptions import ConnectionError

from aiden_recommender.scrapers.scraper_aggregator import scraper_aggregator
from aiden_recommender.form_finder.form_finder import get_form_cached, Form
from aiden_shared.tools import redis_client
from aiden_shared.models import JobOffer

app = FastAPI()


class JobOfferRequest(BaseModel):
    location: str
    query: str
    limit: int
    profile_id: UUID


class FormRequest(BaseModel):
    job_reference: str


@app.get("/health", status_code=200)
def healthcheck() -> dict[str, str]:
    try:
        redis_client.ping()
    except ConnectionError as e:
        raise RuntimeError("Failed to connect to Redis") from e
    return {"status": "healthy"}


@app.post("/joboffers", response_model=list[JobOffer])
async def recommend(job_offer_request: Annotated[JobOfferRequest, Body()]) -> list[JobOffer]:
    results = await scraper_aggregator.search_jobs(
        search_query=job_offer_request.query,
        location=job_offer_request.location,
        num_results=job_offer_request.limit,
        profile_embedding_id=job_offer_request.profile_id,
    )
    return results


@app.on_event("startup")
async def on_startup():
    await scraper_aggregator.start_workers()


@app.post("/get_form", response_model=Form)
async def get_form_schema(form_request: Annotated[FormRequest, Body()]) -> Form:
    print(type(form_request))
    form = get_form_cached(form_request.job_reference)
    return form
