import os
from uuid import UUID

import httpx

from .tool import Tool


class ScraperTool(Tool):
    def __init__(self, profile_embedding_id: UUID) -> None:
        super().__init__("ScraperTool")
        self.add_tool("search_jobs", self.search_jobs_wrapper)
        self.profile_embedding_id: UUID = profile_embedding_id

    @Tool.tool_function  # type: ignore
    def search_jobs_wrapper(self, search_query: str, location: str, num_results: int = 15, *args, **kwargs) -> list[str]:
        url = f"{os.environ.get('RECOMMENDER_API_URL')}/joboffers"
        payload = {
            "location": location,
            "query": search_query,
            "limit": num_results,
            "profile_id": str(self.profile_embedding_id),
        }
        response = httpx.post(url=url, json=payload, timeout=60)
        response.raise_for_status()

        results = response.json()

        return results
