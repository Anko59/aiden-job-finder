import json
from aiden_shared.tools import qdrant_client, JOB_COLLECTION
from aiden_shared.models import JobOffer
from aiden_shared.utils import reference_to_uuid
from aiden_recommender.scrapers import france_travail_scraper, indeed_scraper, wtj_scraper
from aiden_recommender.scrapers.utils import cache
from datetime import timedelta
from pydantic import BaseModel


class Form(BaseModel):
    json_content: str


@cache(model=Form, retention_period=timedelta(days=4))
def get_form_cached(reference: str) -> Form:
    response = qdrant_client.retrieve(collection_name=JOB_COLLECTION, ids=[str(reference_to_uuid(reference).hex)], with_payload=True)
    point = response[0]
    job_offer = JobOffer(**point.payload)
    if job_offer.source == "wtj":
        form = wtj_scraper.get_form(job_offer)
    elif job_offer.source == "indeed":
        form = indeed_scraper.get_form(job_offer)
    elif job_offer.source == "france_travail":
        form = france_travail_scraper.get_form(job_offer)
    else:
        raise ValueError(f"Unknown source {job_offer.source}")
    return Form(json_content=json.dumps(form))
