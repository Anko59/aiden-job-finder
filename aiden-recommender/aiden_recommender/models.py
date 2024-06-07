from __future__ import annotations
from datetime import datetime, timedelta
import json
from typing import AsyncGenerator, Callable, Optional, Any

from pydantic import BaseModel
from abc import ABC, abstractmethod
from mistralai.models.embeddings import EmbeddingObject
from qdrant_client.models import PointStruct
from aiden_recommender.constants import JOB_COLLECTION
from aiden_recommender.tools import async_zyte_client, async_redis_client, async_mistral_client, async_qdrant_client
import hashlib
import uuid


def reference_to_uuid(reference: str) -> uuid.UUID:
    return uuid.UUID(hashlib.md5(reference.encode()).hexdigest()).hex


class Request(BaseModel, ABC):
    @abstractmethod
    async def send(self) -> AsyncGenerator[JobOffer | Request]:
        pass


class CachableRequest(Request, ABC):
    callback: Optional[Callable] = None
    retention_period: timedelta = timedelta(hours=12)

    async def _send(self):
        response = await self.get_coroutine()
        if response:
            if self.callback:
                for next_item in self.callback(response):
                    yield next_item

    @abstractmethod
    def _generate_cache_keys(self) -> list[str]:
        pass

    @abstractmethod
    def get_coroutine(self):
        pass

    async def send(self):
        yield GetCacheRequest(original_request=self)


class GetCacheRequest(Request):
    original_request: CachableRequest

    async def send(self):
        responses = [await async_redis_client.get(key) for key in self.original_request._generate_cache_keys()]
        if None in responses:
            yield CacheCheckedRequest(original_request=self.original_request)
        else:
            yield None


class SetCacheRequest(Request):
    original_request: CachableRequest

    async def send(self):
        for key in self.original_request._generate_cache_keys():
            await async_redis_client.setex(key, self.original_request.retention_period, 1)
        yield None


class CacheCheckedRequest(Request):
    original_request: CachableRequest

    async def send(self):
        async for item in self.original_request._send():
            yield item
        yield SetCacheRequest(original_request=self.original_request)


class ZyteRequest(CachableRequest):
    query: dict[str, Any]

    def get_coroutine(self):
        return async_zyte_client.get(query=self.query)

    def _generate_cache_keys(self) -> str:
        return [f"zyte-request-{json.dumps(self.query)}"]


class MistralEmbeddingRequest(CachableRequest):
    input: list["JobOffer"]

    def get_coroutine(self):
        return async_mistral_client.embeddings(model="mistral-embed", input=[item.metadata_repr() for item in self.input])

    def _generate_cache_keys(self) -> str:
        return [f"mistal-embed-{item.reference}" for item in self.input]


class QdrantRequest(CachableRequest):
    embeddings: list[EmbeddingObject]
    job_offers: list["JobOffer"]

    def get_coroutine(self):
        return async_qdrant_client.upload_points(
            collection_name=JOB_COLLECTION,
            points=[
                PointStruct(id=reference_to_uuid(job_offer.reference), vector=embedding.embedding, payload=job_offer.model_dump())
                for job_offer, embedding in zip(self.job_offers, self.embeddings)
            ],
        )

    def _generate_cache_keys(self) -> list[str]:
        return [f"qdrant-embed-{job_offer.reference}" for job_offer in self.job_offers]


class ScraperItem(BaseModel):
    raw_data: list[dict]


class Coordinates(BaseModel):
    lat: float
    lng: float


class Office(BaseModel):
    country: str
    local_city: Optional[str] = None
    local_state: Optional[str] = None


class Profession(BaseModel):
    category_name: str
    sub_category_name: str
    sub_category_reference: str


class Logo(BaseModel):
    url: str


class CoverImage(BaseModel):
    medium: Logo


class Organization(BaseModel):
    description: Optional[str] = None
    name: str
    nb_employees: Optional[int] = None
    logo: Optional[Logo] = None
    cover_image: Optional[CoverImage] = None


class JobOffer(BaseModel):
    benefits: list[str]
    contract_duration_maximum: Optional[int] = None
    contract_duration_minimum: Optional[int] = None
    contract_type: Optional[str] = None
    education_level: Optional[str] = None
    experience_level_minimum: Optional[float | str] = None
    has_contract_duration: Optional[bool] = None
    has_education_level: Optional[bool] = None
    has_experience_level_minimum: Optional[bool] = None
    has_remote: Optional[bool] = None
    has_salary_yearly_minimum: Optional[bool] = None
    language: str
    name: str
    new_profession: Optional[Profession] = None
    offices: list[Office]
    organization: Organization
    profile: Optional[str] = None
    published_at: str
    remote: Optional[str] = None
    salary_currency: Optional[str] = None
    salary_maximum: Optional[int] = None
    salary_minimum: Optional[int] = None
    salary_period: Optional[str | dict] = None
    salary_yearly_minimum: Optional[int] = None
    sectors: Optional[list[dict]] = None
    url: Optional[str] = None

    source: str
    reference: str
    geoloc: Optional[Coordinates] = None

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        data["metadata_repr"] = self.metadata_repr()
        return data

    def metadata_repr(self) -> str:
        """Returns a language representation of the offer metadata (location, company, profile sought for etc...)."""
        published_date = datetime.strptime(self.published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")

        metadata = f"This job offer named '{self.name}' was published on {published_date}."
        if self.organization and self.organization.name:
            metadata += f" It is from the company '{self.organization.name}'."
        if self.offices:
            locations = ", ".join([f"{office.local_city}, {office.country}" for office in self.offices if office.local_city])
            if locations:
                metadata += f" It is located in {locations}."
        if self.sectors:
            _sectors = [sector for sector in self.sectors if sector.get("name")]
            sectors = ", ".join([sector["name"] for sector in _sectors])
            metadata += f" Sectors: {sectors}."
        if self.salary_period:
            metadata += f" Salary period: {self.salary_period}."
        if self.salary_currency:
            metadata += f" Salary currency: {self.salary_currency}."
        if self.salary_minimum is not None and self.salary_maximum is not None:
            metadata += f" Salary range: {self.salary_minimum}-{self.salary_maximum} per {self.salary_period}."
        metadata += f" It has the following benefits {', '.join(self.benefits)}" if self.benefits else ""
        return metadata

    def company_repr(self) -> str:
        """Return a language representation of the company posting the offer."""
        company_representation = f"The company '{self.organization.name}'"
        if self.organization.description:
            company_representation += f" is described as '{self.organization.description}'."
        else:
            company_representation += " has no description."
        if self.organization.nb_employees:
            company_representation += f" It has {self.organization.nb_employees} employees"
        return company_representation

    def requirements_repr(self) -> str:
        """Returns a string representation of the profile sought for the position."""
        if self.profile:
            return f"The profile sought for this position is: '{self.profile}'."
        else:
            return "No specific profile requirements mentioned."
