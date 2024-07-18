from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, BackgroundTasks
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
    start_index: int


class FormRequest(BaseModel):
    job_reference: str


class ScrapeResponse(BaseModel):
    status: str
    scrape_id: UUID


class ScrapeStatusResponse(BaseModel):
    status: str


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


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(job_offer_request: Annotated[JobOfferRequest, Body()], background_tasks: BackgroundTasks):
    scrape_id = uuid4()
    background_tasks.add_task(
        scraper_aggregator.scrape,
        scrape_id,
        job_offer_request.query,
        job_offer_request.location,
        job_offer_request.limit,
        job_offer_request.start_index,
    )
    return ScrapeResponse(status="Scraping started", scrape_id=scrape_id)


@app.get("/scrape_status/{scrape_id}", response_model=ScrapeStatusResponse)
async def scrape_status(scrape_id: UUID):
    status = scraper_aggregator.get_scrape_status(scrape_id)
    return ScrapeStatusResponse(status=status)


@app.on_event("startup")
async def on_startup():
    await scraper_aggregator.start_workers()


@app.post("/get_form", response_model=Form)
async def get_form_schema(form_request: Annotated[FormRequest, Body()]) -> Form:
    print(type(form_request))
    form = get_form_cached(form_request.job_reference)
    return form
