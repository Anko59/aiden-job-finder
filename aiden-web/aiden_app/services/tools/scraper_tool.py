import os
from typing import Iterable
from uuid import UUID, uuid4

import markdown2
import httpx
import time

from aiden_app.models import ToolMessage
from aiden_app.services.tools.tool import Tool
from aiden_shared.models import ScrapeStatus, JobOffer
from aiden_shared.tools import qdrant_client, mistral_client, JOB_COLLECTION
from mistralai.models.embeddings import EmbeddingObject
from django.template.loader import render_to_string


class ScraperTool(Tool):
    base_url = os.environ.get("RECOMMENDER_API_URL")

    scrape_url = f"{base_url}/scrape"
    scrape_status_url = f"{base_url}/scrape_status/{{scrape_id}}"

    job_response_interval = 1

    def __init__(self, profile_embedding_id: UUID) -> None:
        super().__init__("ScraperTool")
        self.add_tool("search_jobs", self.search_jobs)
        self.user_profile = qdrant_client.rest.points_api.get_point(collection_name="user_profile", id=str(profile_embedding_id)).result
        self.returned_offers: dict[UUID, list[str]] = {}

    def _get_search_query_vector(self, search_query: str) -> list[EmbeddingObject]:
        return mistral_client.embeddings(model="mistral-embed", input=[search_query]).data

    def get_scrape_status(self, scrape_id: UUID) -> ScrapeStatus:
        response = httpx.get(url=self.scrape_status_url.format(scrape_id=scrape_id), timeout=3)
        response.raise_for_status()
        return response.json()["status"]

    def get_next_job_recommendation(self, scrape_id: UUID, search_query: str, location: str) -> str:
        user_profile_vector = self.user_profile.vector
        search_query_vector = self._get_search_query_vector(search_query + " " + location)[0].embedding
        search_vector = [a + (b * 0.5) for a, b in zip(search_query_vector, user_profile_vector)]

        filter_condition = {"must_not": [{"key": "reference", "match": {"any": self.returned_offers.get(scrape_id, [])}}]}

        response = qdrant_client.search(
            collection_name=JOB_COLLECTION,
            query_vector=search_vector,
            query_filter=filter_condition,
            limit=1,
            with_vectors=False,
            with_payload=True,
        )

        if not response:
            return None  # No more unique job offers available

        job_offer = JobOffer(**response[0].payload)

        if scrape_id not in self.returned_offers:
            self.returned_offers[scrape_id] = []
        self.returned_offers[scrape_id].append(job_offer.reference)

        return job_offer

    def format_user_message(self, job_offer: JobOffer) -> str:
        if job_offer.profile is not None:
            job_offer.profile = markdown2.markdown(job_offer.profile)
        if job_offer.organization.description is not None:
            job_offer.organization.description = markdown2.markdown(job_offer.organization.description)
        return render_to_string("langui/job-offer.html", {"job_offer": job_offer.model_dump()})

    def pack_message(self, job_offer: JobOffer, container_id: str) -> ToolMessage:
        return ToolMessage(
            function_nane="search_jobs",
            agent_message={
                "role": "tool",
                "content": job_offer.metadata_repr(),
            },
            user_message=self.format_user_message(job_offer),
            container_id=container_id,
        )

    def get_container_message(self, container_id: str) -> ToolMessage:
        return ToolMessage(
            function_nane="search_jobs",
            agent_message=None,
            user_message=render_to_string("langui/job-offer-grid.html", {"container_id": container_id}),
        )

    def search_jobs(self, search_query: str, location: str, num_results: int = 15, start_index: int = 0) -> Iterable[ToolMessage]:
        # As num_results and start_index come from the model, they can be strings
        num_results = int(num_results)
        start_index = int(start_index)
        payload = {"location": location, "query": search_query, "limit": num_results, "start_index": start_index}
        response = httpx.post(url=self.scrape_url, json=payload, timeout=3)
        response.raise_for_status()
        container_id = uuid4().hex
        yield self.get_container_message(container_id)
        results = response.json()
        scrape_id = results["scrape_id"]
        for i in range(num_results):
            status = self.get_scrape_status(scrape_id)
            if status != ScrapeStatus.FINISHED:
                next_job = self.get_next_job_recommendation(scrape_id, search_query, location)
                if next_job is None:
                    break
                yield self.pack_message(next_job, container_id)
                time.sleep(self.job_response_interval)
            else:
                for r in range(i, num_results):
                    next_job = self.get_next_job_recommendation(scrape_id, search_query, location)
                    if next_job is None:
                        break
                    yield self.pack_message(next_job, container_id)
                break
