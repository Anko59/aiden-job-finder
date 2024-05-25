import os

import httpx

from .tool import Tool


class ScraperTool(Tool):
    def __init__(self) -> None:
        super().__init__("ScraperTool")
        self.add_tool("search_jobs", self.search_jobs_wrapper)

    @Tool.tool_function  # type: ignore
    def search_jobs_wrapper(self, search_query: str, location: str, num_results: int = 15, *args, **kwargs) -> list[str]:
        url = f"{os.environ.get('SCRAPER_API_URL')}/scrape"
        payload = {"location": location, "query": search_query, "limit": num_results}
        response = httpx.post(url=url, json=payload)
        response.raise_for_status()

        results = response.json()
        return results
