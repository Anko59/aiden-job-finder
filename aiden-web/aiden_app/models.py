from typing import Optional
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from loguru import logger
from django.utils.encoding import force_str
from aiden_project.settings import MEDIA_ROOT

import os
import uuid


from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.encoding import force_str
from loguru import logger
from pydantic import BaseModel as PydanticBaseModel
from aiden_app.storage import UUIDS3Boto3Storage


def remove_special_characters(value):
    regex_validator = RegexValidator(r"^[a-zA-Z0-9\s]+$", "Special characters are not allowed.")
    try:
        regex_validator(value)
    except ValidationError:
        # Remove special characters
        return "".join(char for char in force_str(value) if char.isalnum() or char.isspace())
    return value


class AssistantMesssage(PydanticBaseModel):
    title: str
    content: str
    container_id: Optional[str] = None


class ToolMessage(PydanticBaseModel):
    function_nane: str
    agent_message: Optional[dict] = None
    user_message: Optional[str] = None
    container_id: Optional[str] = None


class QuestionRequest(PydanticBaseModel):
    question: str


class StartChatRequest(PydanticBaseModel):
    first_name: str
    last_name: str


class UserProfileResponse(PydanticBaseModel):
    first_name: str
    last_name: str
    photo_url: str


class DocumentResponse(PydanticBaseModel):
    name: str
    path: str


class CreateProfileResponse(PydanticBaseModel):
    success: str


class ErrorResponse(PydanticBaseModel):
    error: str


class BaseModel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    @classmethod
    def from_json(cls, json_data: dict, user: User, *args, **kwargs) -> "BaseModel":
        # Handle ManyToManyField and OneToOneField
        m2m_fields = [
            field
            for field in cls._meta.get_fields()
            if isinstance(field, models.ManyToManyField) or isinstance(field, models.OneToOneField)
        ]
        related_objects = {}
        for field in m2m_fields:
            data = json_data.get(field.name, [])
            if isinstance(field, models.OneToOneField):
                related_objects[field.name] = field.related_model.from_json(data, user=user)
            else:
                related_objects[field.name] = [field.related_model.from_json(obj, user=user) for obj in data]
            if field.name in json_data:
                del json_data[field.name]

        # Remove unusable fields and clean up data
        for key, value in list(json_data.items()):
            if key not in [field.name for field in cls._meta.get_fields()]:
                del json_data[key]
            else:
                field_object = cls._meta.get_field(key)
                for validator in field_object.validators:
                    try:
                        validation = validator(value)
                    except ValidationError as e:
                        logger.error(f"Validation error: {e}")
                        value = None
                        break
                    if validation is not None:
                        value = validation
                json_data[key] = value

        # Create the instance
        json_data["user"] = user
        instance = cls.objects.create(**json_data)

        # Save ManyToManyField relationships
        for field, objs in related_objects.items():
            instance.__getattribute__(field).set(objs)

        return instance

    def to_json(self) -> dict:
        json_data = {}
        for field in self._meta.get_fields():
            if isinstance(field, models.ManyToManyField):
                json_data[field.name] = [obj.to_json() for obj in getattr(self, field.name).all()]
            elif isinstance(field, models.OneToOneField):
                json_data[field.name] = getattr(self, field.name).to_json()
            elif isinstance(field, models.UUIDField):
                json_data[field.name] = str(getattr(self, field.name))
            elif field.name == "user":
                json_data[field.name] = self.user.username if self.user else None
            elif not isinstance(field, models.ImageField) and not field.is_relation and field.name != "id":
                json_data[field.name] = getattr(self, field.name)
        return json_data


class SocialLink(BaseModel):
    icon = models.CharField(
        max_length=50, help_text="The name or icon representing the social media platform, from font-awesome, without the 'fa-' prefix"
    )
    url = models.URLField(help_text="The URL of the individual's profile on the social media platform", blank=True, null=True)
    text = models.CharField(max_length=100, help_text="A shortened or display version of the URL")


class Interest(BaseModel):
    icon = models.CharField(max_length=50, help_text="An icon representing the interest, from font-awesome, without the 'fa-' prefix")
    text = models.CharField(max_length=100, help_text="A description of the interest")


class ExperienceDetail(BaseModel):
    description = models.TextField(help_text="A responsibility or achievement during the experience")


class Experience(BaseModel):
    title = models.CharField(max_length=100, help_text="The job title for the experience")
    company = models.CharField(
        max_length=100, help_text="The name and location of the company, in the formant Company Name (City, Country Code)"
    )
    duration = models.CharField(max_length=50, help_text="The duration of the experience in the format YYYY.MM--YYYY.MM")
    details = models.ManyToManyField(
        ExperienceDetail, related_name="experience", help_text="A list of responsibilities or achievements during the experience"
    )


class Education(BaseModel):
    degree = models.CharField(max_length=100, help_text="The degree obtained")
    specialization = models.CharField(max_length=100, help_text="The specialization or major of the degree")
    school = models.CharField(
        max_length=100, help_text="The name and location of the school, in the format School Name (City, Country Code)"
    )
    duration = models.CharField(max_length=50, help_text="The duration of the education in the format YYYY--YYYY")


class Project(BaseModel):
    name = models.CharField(max_length=100, help_text="The name of the project")
    description = models.TextField(help_text="A description of the project")
    url = models.URLField(help_text="The URL of the project repository or website", blank=True, null=True)


class Skill(BaseModel):
    name = models.CharField(max_length=100, help_text="The name of the skill")
    color = models.CharField(max_length=20, help_text="A color code associated with the skill")
    level = models.CharField(max_length=50, help_text="The proficiency level in the skill")
    details = models.TextField(help_text="Additional details or sub-skills related to the main skill, example cyan!48!black")


class ProfileInfo(BaseModel):
    first_name = models.CharField(max_length=100, help_text="The first name of the individual")
    last_name = models.CharField(max_length=100, help_text="The last name of the individual")
    cv_title = models.CharField(
        max_length=255, help_text="The professional title or headline for the CV", validators=[remove_special_characters]
    )
    profile_description = models.TextField(help_text="A summary of the individual's professional background and objectives")
    email = models.EmailField(help_text="The email address for contacting the individual")
    phone_number = models.CharField(max_length=20, help_text="The phone number for contacting the individual")
    address = models.CharField(max_length=255, help_text="The address of the individual's residence")
    social_links = models.ManyToManyField(
        SocialLink, related_name="profiles", help_text="A list of social media linked with the individual"
    )
    interests = models.ManyToManyField(Interest, related_name="profiles", help_text="A list of the individual's interests or hobbies")
    experiences = models.ManyToManyField(
        Experience, related_name="profiles", help_text="A list of the individual's professional experiences"
    )
    educations = models.ManyToManyField(Education, related_name="profiles", help_text="A list of the individual's educational background")
    projects = models.ManyToManyField(Project, related_name="profiles", help_text="A list of projects the individual has worked on")
    skills = models.ManyToManyField(Skill, related_name="profiles", help_text="A list of the individual's skills")
    embeddings_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)


class Document(BaseModel):
    name = models.CharField(max_length=255)
    file = models.FileField(storage=UUIDS3Boto3Storage(object_folder="documents"))
    profile = models.ForeignKey(ProfileInfo, on_delete=models.CASCADE)


class UserProfile(BaseModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    profile_title = models.CharField(max_length=255)
    photo = models.ImageField(storage=UUIDS3Boto3Storage(object_folder="photos"))

    profile_info = models.OneToOneField(
        ProfileInfo, related_name="profile", on_delete=models.CASCADE, help_text="A detailed schema for a profile JSON object"
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        unique_together = [["first_name", "last_name", "profile_title"]]
