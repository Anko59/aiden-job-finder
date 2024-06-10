from typing import Annotated
from uuid import UUID

from fastapi import FastAPI
from fastapi.params import Body
from pydantic import BaseModel
from redis.exceptions import ConnectionError

from aiden_recommender.models import JobOffer
from aiden_recommender.scrapers.scraper_aggregator import scraper_aggregator
from aiden_recommender.scrapers.wtj.flow import scrape_wtj
from aiden_recommender.tools import redis_client

app = FastAPI()


class JobOfferRequest(BaseModel):
    location: str
    query: str
    limit: int
    profile_id: UUID


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


@app.post("/test", response_model=list[JobOffer])
def test() -> list[JobOffer]:
    results = scrape_wtj(search_query="ML engineer", location="Paris", num_results=100)
    return results


@app.on_event("startup")
async def on_startup():
    await scraper_aggregator.start_workers()
