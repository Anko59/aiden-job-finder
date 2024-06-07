from abc import ABC
import aiohttp
from datetime import datetime, timedelta


ENDPOINT_ACCESS_TOKEN = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token"
OFFRES_DEMPLOI_V2_BASE = "https://api.emploi-store.fr/partenaire/offresdemploi/v2"
REFERENTIEL_ENDPOINT = f"{OFFRES_DEMPLOI_V2_BASE}/referentiel"


class AbstractFranceTravailClient(ABC):
    """
    Base class to authenticate and use the methods of France Travail API.
    """

    def __init__(self, client_id, client_secret, verbose=False, proxies=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.verbose = verbose
        self.proxies = proxies
        self.timeout = 60
        self.session = aiohttp.ClientSession()
        self.token = None

    async def get_token(self):
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": f"api_offresdemploiv2 o2dsoffre application_{self.client_id}",
        }
        headers = {"content-type": "application/x-www-form-urlencoded"}
        params = {"realm": "/partenaire"}
        current_time = datetime.now()

        async with self.session.post(
            url=ENDPOINT_ACCESS_TOKEN,
            headers=headers,
            data=data,
            params=params,
            timeout=self.timeout,
            proxy=self.proxies,
        ) as r:
            r.raise_for_status()
            token = await r.json()
            token["expires_at"] = current_time + timedelta(seconds=token["expires_in"])
            self.token = token
            return token

    def is_expired(self):
        return datetime.now() >= self.token["expires_at"]

    async def get_headers(self):
        if not self.token or self.is_expired():
            if self.verbose:
                print("Requesting new token" if self.token else "Token has not been requested yet. Requesting token")
            await self.get_token()
        return {"Authorization": f"Bearer {self.token['access_token']}"}

    async def close_session(self):
        await self.session.close()
