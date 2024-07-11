import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from aiden_project.settings import MEDIA_ROOT
from django.core.serializers.json import DjangoJSONEncoder

from aiden_app.models import UserProfile
from aiden_app.services.tools.cv_editor_tool import CVEditorTool
from aiden_app.services.tools.scraper_tool import ScraperTool
from aiden_app.services.tools.tool_aggregator import ToolAggregator

from .prompts import (
    PROFILE_CREATION_SYSTEM_PROMPT,
    START_CHAT_PROMPT,
    SYSTEM_PROMPT,
    PROFILE_EDIT_SYSTEM_PROMPT,
    GENERATE_COVER_LETTER_SYSTEM_PROMPT,
    FILL_APPLICATION_FIELDS_SYSTEM_PROMPT,
)


class Agent(ABC):
    def __init__(self, message_class: Any):
        self.tool_aggregator = ToolAggregator([])
        self.message_class = message_class
        self.messages: List[Dict[str, Any]] = []
        self.profile: UserProfile = None
        self.tokens_used = 0
        self.max_tool_calls = 5
        self.client = None

    @abstractmethod
    def chat(self, user_input: str) -> Tuple[Dict[str, str], bool]:
        pass

    @abstractmethod
    def _message_model(self, **kwargs) -> Any:
        pass

    @abstractmethod
    def unserialize_messages(self, messages: List[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def serialize_messages(self) -> List[Dict[str, Any]]:
        pass

    def to_json(self) -> str:
        state = self.__dict__.copy()
        state["messages"] = self.serialize_messages()
        del state["client"]
        del state["tool_aggregator"]
        del state["message_class"]
        state["profile_id"] = self.profile.id
        del state["profile"]
        return json.dumps(state)

    @classmethod
    def from_json(cls, state: str) -> "Agent":
        state = json.loads(state)
        profile = UserProfile.objects.get(id=state["profile_id"])
        del state["profile_id"]
        self = cls.from_profile(profile)
        self.unserialize_messages(state["messages"])
        del state["messages"]
        self.__dict__.update(state)
        return self

    @classmethod
    def from_profile(cls, user_profile: UserProfile, *args, **kwargs) -> "Agent":
        self = cls(*args, **kwargs)
        self.profile = user_profile
        self.tool_aggregator.tools.append(CVEditorTool(profile=user_profile))
        self.tool_aggregator.tools.append(ScraperTool(profile_embedding_id=user_profile.profile_info.embeddings_id))
        profile_dict = user_profile.profile_info.to_json()
        start_messages = [
            self.message_class(role="system", content=SYSTEM_PROMPT),
            self.message_class(role="system", content=json.dumps(profile_dict, cls=DjangoJSONEncoder)),
            self.message_class(role="assistant", content=START_CHAT_PROMPT),
        ]
        self.messages = start_messages
        return self

    def create_profile(self, profile_info: dict[str, str]):
        profile_schema_path = os.path.join(MEDIA_ROOT, "cv", "cv_schema.json")
        profile_schema = json.load(open(profile_schema_path))
        example_profile_path = os.path.join(MEDIA_ROOT, "cv", "example_profile.json")
        example_profile = json.load(open(example_profile_path))
        base_first_name = profile_info["first_name"]
        base_last_name = profile_info["last_name"]
        base_photo_url = profile_info["photo_url"]
        start_messages = [
            self.message_class(role="system", content=PROFILE_CREATION_SYSTEM_PROMPT),
            self.message_class(role="system", content=json.dumps(profile_schema)),
            self.message_class(role="system", content=json.dumps(example_profile)),
            self.message_class(role="user", content=json.dumps(profile_info)),
        ]
        self.messages = start_messages
        message = self._message_model(response_format={"type": "json_object"}, tools=[])
        profile_info = json.loads(message.content)
        profile_info["first_name"] = base_first_name
        profile_info["last_name"] = base_last_name
        profile_info["photo_url"] = base_photo_url
        return profile_info

    def edit_profile(self, profile_info: dict[str, str], job_offer: dict[str, str]):
        profile_schema_path = os.path.join(MEDIA_ROOT, "cv", "cv_schema.json")
        profile_schema = json.load(open(profile_schema_path))
        base_first_name = profile_info["first_name"]
        base_last_name = profile_info["last_name"]
        base_photo_url = profile_info["photo_url"]
        messages = [
            self.message_class(role="system", content=PROFILE_EDIT_SYSTEM_PROMPT),
            self.message_class(role="system", content=json.dumps(profile_schema)),
            self.message_class(role="system", content=json.dumps(job_offer)),
            self.message_class(role="user", content=json.dumps(profile_info)),
        ]
        message = self._message_model(response_format={"type": "json_object"}, tools=[], messages=messages)
        self.messages.append(message)
        profile_info = json.loads(message.content)
        profile_info["first_name"] = base_first_name
        profile_info["last_name"] = base_last_name
        profile_info["photo_url"] = base_photo_url
        return profile_info

    def generate_cover_letter(self, job_offer: dict[str, str], profile_info: dict[str, str]):
        messages = [
            self.message_class(role="system", content=GENERATE_COVER_LETTER_SYSTEM_PROMPT),
            self.message_class(role="system", content=json.dumps(job_offer)),
            self.message_class(role="user", content=json.dumps(profile_info)),
        ]
        message = self._message_model(tools=[], messages=messages)
        self.messages.append(message)
        return message.content

    def fill_form(self, fields: dict[str, str], job_offer: dict[str, str], profile_info: dict[str, str]):
        messages = [
            self.message_class(role="system", content=FILL_APPLICATION_FIELDS_SYSTEM_PROMPT),
            self.message_class(role="system", content=json.dumps(job_offer)),
            self.message_class(role="system", content=json.dumps(profile_info)),
            self.message_class(role="user", content=json.dumps(fields)),
        ]
        message = self._message_model(tools=[], messages=messages, response_format={"type": "json_object"})
        self.messages.append(message)
        return json.loads(message.content)
