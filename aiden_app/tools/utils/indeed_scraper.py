import json
import re
import tempfile
from typing import Any, Dict, List, Optional

from chompjs import parse_js_object
from selenium.webdriver.common.by import By

from .cache import Cache
from .chrome_driver import ChromeDriver


class IndeedScraper:
    def __init__(self):
        self.driver = ChromeDriver()
        self.cache = Cache(tempfile.mkdtemp())
        self.job_details_cache = Cache(tempfile.mkdtemp())

    def extract_results(self, script: str) -> List[Dict[str, Any]]:
        data = {}
        for line in script.split('\n'):
            line = line.strip()
            if line.startswith('window.mosaic.providerData'):
                key = line.split('=')[0]
                value = '='.join(line.split('=')[1:])
                key = re.findall(r'"(.*?)"', key)
                if len(key):
                    data[key[0]] = parse_js_object(value)
        return data['mosaic-provider-jobcards']['metaData']['mosaicProviderJobCardsModel']['results']

    def fetch_results(self, search_query: str, location: str, start: int) -> List[Dict[str, Any]]:
        driver = self.driver.start()

        url = f'https://fr.indeed.com/jobs?q={search_query}&l={location}&from=searchOnHP&vjk=fa2409e45b11ca41&start={start}'

        driver.get(url)

        script = driver.find_element(By.XPATH, "//script[@id='mosaic-data']").get_attribute('textContent')
        results = self.extract_results(script)

        driver.quit()

        return results

    def search_jobs(self, search_query: str, location: str, num_results: int = 15, start: int = 0) -> List[Dict[str, Any]]:
        cached_results = self.cache.get_cache_entry(f'{search_query}_{location}_{start}')
        if cached_results:
            return cached_results['results'][:num_results]

        all_results = []
        while len(all_results) < num_results:
            results = self.fetch_results(search_query, location, start)
            all_results.extend(results)
            self.cache.add_cache_entry(
                f'{search_query}_{location}_{start}',
                [search_query, location, str(start)],
                results,
            )

            start += 15
            if len(results) < 15:
                break

        return all_results[:num_results]

    def get_job_link_from_title(self, job_title: str) -> Optional[str]:
        for query, cache_entry in self.cache.cache.items():
            for result in cache_entry['results']:
                if result['title'] == job_title:
                    return 'https://fr.indeed.com' + result['link']
        return None

    def extract_job_description(self, job_link: str) -> Optional[str]:
        driver = self.driver.start()

        driver.get(job_link)

        try:
            script = driver.find_element(By.XPATH, "//script[@type='application/ld+json']").get_attribute('innerHTML')
            job_data = json.loads(script)
            description = job_data['description']
            driver.quit()
            return description
        except Exception as e:
            print(f'Error extracting job description: {e}')
            driver.quit()
            return e

    def get_job_details(self, job_title: str) -> Optional[Dict[str, Any]]:
        """cached_job_details = self.job_details_cache.get_cache_entry(job_title)
        if cached_job_details:
            return cached_job_details"""

        job_link = self.get_job_link_from_title(job_title)
        if job_link is None:
            print('Job not found in cache.')
            return {
                'errror': 'KeyError: Job not found in cache.',
                'description': f'Job with title "{job_title}" not found in cache.' f'Available job titles: {self.list_job_titles()}',
            }

        description = self.extract_job_description(job_link)
        if description is Exception:
            return {
                'error': 'Exception: Error extracting job description.',
                'description': str(description),
            }

        job_details = {'title': job_title, 'description': description, 'link': job_link}

        """self.job_details_cache.add_cache_entry(
            job_title, [job_title], job_details)"""

        return job_details

    def list_job_titles(self):
        job_titles = []
        for query, cache_entry in self.cache.cache.items():
            for result in cache_entry['results']:
                job_titles.append(result['title'])
        return job_titles
