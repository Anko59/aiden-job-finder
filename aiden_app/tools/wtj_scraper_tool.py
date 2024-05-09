from .tool import Tool
from .utils.wtj_scraper import WelcomeToTheJungleScraper


class WelcomeToTheJungleScraperTool(Tool):
    def __init__(self):
        self.scraper = WelcomeToTheJungleScraper()
        super().__init__("WelcomeToTheJungleScraper")
        self.add_tool("search_jobs", self.search_jobs_wrapper)

    @Tool.tool_function
    def search_jobs_wrapper(self, search_query: str, location: str, num_results: int = 15, start: int = 0):
        results = self.scraper.search_jobs(search_query, location, int(num_results), int(start))
        return results
