import json
import re
from typing import Any, Dict, List, Optional

from chompjs import parse_js_object
from loguru import logger
from selenium.webdriver.common.by import By

from aiden_recommender.scrapers.utils import ChromeDriver
from aiden_recommender.tools import redis_client


class IndeedScraper:
    def __init__(self):
        self.driver = ChromeDriver()
        logger.info("succesfully initialized Indeed scraper")

    def _extract_results(self, script: str) -> List[Dict[str, Any]]:
        data = {}
        for line in script.split("\n"):
            line = line.strip()
            if line.startswith("window.mosaic.providerData"):
                key = line.split("=")[0]
                value = "=".join(line.split("=")[1:])
                key = re.findall(r'"(.*?)"', key)
                if len(key):
                    data[key[0]] = parse_js_object(value)
        return data["mosaic-provider-jobcards"]["metaData"]["mosaicProviderJobCardsModel"]["results"]

    def _fetch_results(self, search_query: str, location: str, start: int) -> List[Dict[str, Any]]:
        driver = self.driver.start()

        url = f"https://fr.indeed.com/jobs?q={search_query}&l={location}&from=searchOnHP&vjk=fa2409e45b11ca41&start={start}"

        driver.get(url)

        script = driver.find_element(By.XPATH, "//script[@id='mosaic-data']").get_attribute("textContent")
        results = self._extract_results(script)  # type: ignore

        driver.quit()

        return results

    def _extract_job_description(self, job_link: str) -> str | Exception:
        driver = self.driver.start()

        driver.get(job_link)

        try:
            script = driver.find_element(By.XPATH, "//script[@type='application/ld+json']").get_attribute("innerHTML")
            job_data = json.loads(script)  # type: ignore
            description = job_data["description"]
            driver.quit()
            return description
        except Exception as e:
            print(f"Error extracting job description: {e}")
            driver.quit()
            return e

    def _get_job_details(self, job_title: str) -> Optional[Dict[str, Any]]:
        job_link = str(redis_client.get(job_title))
        description = self._extract_job_description(job_link)
        if description is Exception:
            return {
                "error": "Exception: Error extracting job description.",
                "description": str(description),
            }

        job_details = {"title": job_title, "description": description, "link": job_link}

        return job_details

    def search_jobs(self, search_query: str, location: str, num_results: int = 15, start: int = 0) -> List[Dict[str, Any]]:
        all_results = []
        while len(all_results) < num_results:
            results = self._fetch_results(search_query, location, start)
            all_results.extend(results)
            start += 15
            if len(results) < 15:
                break
        for result in all_results[:num_results]:
            redis_client.set(result["title"], result["link"])
        return all_results[:num_results]
