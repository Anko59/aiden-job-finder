from __future__ import annotations
from enum import Enum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel


class ScrapeStatus(Enum):
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    NOT_FOUND = "not_found"


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
    slug: Optional[str] = None


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
    slug: Optional[str] = None

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
