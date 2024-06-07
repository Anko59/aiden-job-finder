import re
import aiohttp

from aiden_recommender.france_travail_clients.abstract_france_travail_client import AbstractFranceTravailClient, OFFRES_DEMPLOI_V2_BASE

SEARCH_ENDPOINT = f"{OFFRES_DEMPLOI_V2_BASE}/offres/search"


class JobSearchClient(AbstractFranceTravailClient):
    async def search(self, params=None, silent_http_errors=False):
        if self.verbose:
            print(f"Making request with params {params}")

        headers = await self.get_headers()

        async with self.session.get(
            url=SEARCH_ENDPOINT,
            params=params,
            headers=headers,
            timeout=self.timeout,
            proxy=self.proxies,
        ) as r:
            try:
                r.raise_for_status()
            except aiohttp.ClientResponseError as error:
                if r.status == 400:
                    complete_message = f"{error}\n{await r.json()['message']}"
                    if silent_http_errors:
                        print(complete_message)
                    else:
                        raise aiohttp.ClientResponseError(
                            request_info=r.request_info,
                            history=r.history,
                            status=r.status,
                            message=complete_message,
                            headers=r.headers,
                        )
                else:
                    if silent_http_errors:
                        print(str(error))
                    else:
                        raise error
            else:
                found_range = re.search(
                    pattern=r"offres (?P<first_index>\d+)-(?P<last_index>\d+)/(?P<max_results>\d+)",
                    string=r.headers["Content-Range"],
                ).groupdict()
                out = await r.json()
                out.update({"Content-Range": found_range})
                return out
