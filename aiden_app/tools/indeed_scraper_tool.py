from .tool import Tool
from .utils.indeed_scraper import IndeedScraper


class IndeedScraperTool(Tool):
    def __init__(self):
        self.scraper = IndeedScraper()
        super().__init__("IndeedScraper")
        self.add_tool("search_jobs", self.search_jobs_wrapper)
        self.add_tool("get_job_details", self.get_job_details_wrapper)
        self.add_tool("list_job_titles", self.list_job_titles_wrapper)

    def _format_job_info(self, results: list) -> str:
        formatted_jobs = []
        for row in results:
            job = {}
            job["title"] = row["title"]
            job["company"] = row["company"]
            job["location"] = row["formattedLocation"]
            job["salary"] = row["salarySnippet"].get("text", "")
            job["job_types"] = ", ".join(row["jobTypes"]) if isinstance(row["jobTypes"], list) else ""
            job["remote_work"] = bool(
                "remoteWorkModel" in row.keys() and isinstance(row["remoteWorkModel"], dict) and row["remoteWorkModel"].get("inlineText")
            )
            # job['link'] = row['link']
            formatted_jobs.append(job)
        return formatted_jobs

    @Tool.tool_function
    def search_jobs_wrapper(self, search_query: str, location: str, num_results: int = 15, start: int = 0):
        results = self.scraper.search_jobs(search_query, location, int(num_results), int(start))
        results = self._format_job_info(results)
        return results

    @Tool.tool_function
    def get_job_details_wrapper(self, job_title: str):
        results = self.scraper.get_job_details(job_title)
        return results

    @Tool.tool_function
    def list_job_titles_wrapper(self):
        return self.scraper.list_job_titles()
