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

    num_offers_per_search = 15

    def __init__(self, profile_embedding_id: UUID) -> None:
        super().__init__("ScraperTool")
        self.add_tool("search_jobs", self.search_jobs_agent_wrapper)
        self.user_profile = qdrant_client.rest.points_api.get_point(collection_name="user_profile", id=str(profile_embedding_id)).result

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

        filter_condition = {"must_not": [{"key": "reference", "match": {"any": self.data.get("returned_offers", [])}}]}

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

        if "returned_offers" not in self.data.keys():
            self.data["returned_offers"] = []
        self.data["returned_offers"].append(job_offer.reference)

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

    def get_container_message(self, container_id: str, search_query: str, location: str) -> ToolMessage:
        return ToolMessage(
            function_nane="search_jobs",
            agent_message=None,
            user_message=render_to_string(
                "langui/job-offer-grid-container.html",
                {"job_offers_container_id": container_id, "search_query": search_query, "location": location},
            ),
        )

    def get_grid_message(self, grid_id: str, page_number: int, container_id: str) -> ToolMessage:
        return ToolMessage(
            function_nane="search_jobs",
            agent_message=None,
            user_message=render_to_string("langui/job-offer-grid.html", {"job_offers_grid_id": grid_id, "page_number": page_number}),
            container_id=container_id,
        )

    def add_to_memory(self, search_query: str, location: str, container_id: str, num_results: int) -> None:
        if container_id in self.data.keys():
            self.data[container_id]["offers_seen"] += num_results
        else:
            self.data[container_id] = {"search_query": search_query, "location": location, "offers_seen": num_results}

    def search_jobs(self, search_query: str, location: str, container_id: str, page_number: int) -> Iterable[ToolMessage]:
        if container_id in self.data.keys():
            start_index = self.data[container_id]["offers_seen"]
        else:
            start_index = 0
        paylaod = {"location": location, "query": search_query, "limit": self.num_offers_per_search, "start_index": start_index}
        response = httpx.post(url=self.scrape_url, json=paylaod, timeout=3)
        response.raise_for_status()
        scrape_id = response.json()["scrape_id"]
        grid_id = uuid4().hex
        yield self.get_grid_message(grid_id, page_number, container_id)
        for i in range(self.num_offers_per_search):
            status = self.get_scrape_status(scrape_id)
            if status != ScrapeStatus.FINISHED:
                next_job = self.get_next_job_recommendation(scrape_id, search_query, location)
                if next_job is None:
                    break
                yield self.pack_message(next_job, grid_id)
                time.sleep(self.job_response_interval)
            else:
                for _ in range(i, self.num_offers_per_search):
                    next_job = self.get_next_job_recommendation(scrape_id, search_query, location)
                    if next_job is None:
                        break
                    yield self.pack_message(next_job, grid_id)
                break
        self.add_to_memory(search_query, location, container_id, self.num_offers_per_search)

    def search_jobs_agent_wrapper(self, search_query: str, location: str) -> Iterable[ToolMessage]:
        container_id = uuid4().hex
        # This function is called when a new search is started, so we need to yield a new message container
        yield self.get_container_message(container_id, search_query, location)
        yield from self.search_jobs(search_query, location, container_id, 1)

    def get_next_page_jobs(self, container_id: str, page_number: int) -> Iterable[ToolMessage]:
        # This function is called when a new page is requested, so we don't need to yield a new message container
        yield from self.search_jobs(self.data[container_id]["search_query"], self.data[container_id]["location"], container_id, page_number)
