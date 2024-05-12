from fastapi import FastAPI
from fastapi.params import Body
from pydantic import BaseModel
from aiden_scraper.scrapers.wtj.schemas import JobOffer
from aiden_scraper.scrapers.wtj import scraper as wtj_scraper
from typing import Annotated

app = FastAPI()


class JobOfferRequest(BaseModel):
    location: str
    query: str
    limit: int


@app.get("/health", status_code=200)
def healthcheck():
    return {"status": "healthy"}


@app.post("/scrape", response_model=list[JobOffer])
def scrape(job_offer_request: Annotated[JobOfferRequest, Body()]) -> list[JobOffer]:
    return wtj_scraper.search_jobs(
        search_query=job_offer_request.query, location=job_offer_request.location, num_results=job_offer_request.limit
    )
