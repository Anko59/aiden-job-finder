import functools
import json

import pandas as pd

from .tool import Tool
from .utils.indeed_scraper import IndeedScraper


class IndeedScraperTool(Tool):
    @property
    def names_to_functions(self):
        return {
            'search_jobs': functools.partial(self.search_jobs_wrapper),
            'get_job_details': functools.partial(self.get_job_details_wrapper),
            'list_job_titles': functools.partial(self.list_job_titles_wrapper),
        }

    def __init__(self):
        self.scraper = IndeedScraper()
        self.name = 'IndeedScraper'

    def _format_job_info(self, results: pd.DataFrame) -> str:
        formatted_jobs = []
        for _, row in results.iterrows():
            job = {}
            job['title'] = row['title']
            job['company'] = row['company']
            job['location'] = row['formattedLocation']
            job['salary'] = row['salarySnippet'].get('text', '')
            job['job_types'] = ', '.join(row['jobTypes']) if isinstance(row['jobTypes'], list) else ''
            job['remote_work'] = bool(
                'remoteWorkModel' in row.keys() and isinstance(row['remoteWorkModel'], dict) and row['remoteWorkModel'].get('inlineText')
            )
            # job['link'] = row['link']
            formatted_jobs.append(job)
        return formatted_jobs

    def search_jobs_wrapper(self, search_query: str, location: str, num_results: int = 15, start: int = 0):
        try:
            results = pd.DataFrame(self.scraper.search_jobs(search_query, location, int(num_results), int(start)))
            results = self._format_job_info(results)
            return json.dumps(results)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def get_job_details_wrapper(self, job_title: str):
        try:
            results = self.scraper.get_job_details(job_title)
            return json.dumps(results)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def list_job_titles_wrapper(self):
        try:
            return json.dumps(self.scraper.list_job_titles())
        except Exception as e:
            return json.dumps({'error': str(e)})
