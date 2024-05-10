import json
import os
from typing import Any, Dict, List, Tuple
from abc import ABC, abstractmethod

from ..tools.cv_editor_tool import CVEditorTool
from ..tools.indeed_scraper_tool import IndeedScraperTool
from ..tools.tool_aggregator import ToolAggregator
from ..tools.utils.cv_editor import CVEditor
from .prompts import START_CHAT_PROMPT, SYSTEM_PROMPT, PROFILE_CREATION_SYSTEM_PROMPT


class Agent(ABC):
    def __init__(self, message_class: Any):
        self.tool_aggregator = ToolAggregator([])
        self.message_class = message_class
        self.messages: List[Dict[str, Any]] = []
        self.profile: Dict[str, str] = {}
        self.tokens_used = 0
        self.max_tool_calls = 5
        self.client = None

    @abstractmethod
    def chat(self, user_input: str) -> Tuple[Dict[str, str], bool]:
        pass

    @abstractmethod
    def _message_model(self) -> Any:
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
        return json.dumps(state)

    @classmethod
    def from_json(cls, state: str) -> "Agent":
        state = json.loads(state)
        self = cls.from_profile(state["profile"])
        self.unserialize_messages(state["messages"])
        del state["messages"]
        self.__dict__.update(state)
        return self

    @classmethod
    def from_profile(cls, profile: dict[str, str], *args, **kwargs) -> "Agent":
        self = cls(*args, **kwargs)
        self.profile = profile
        self.tool_aggregator.tools.append(CVEditorTool(first_name=profile["first_name"], last_name=profile["last_name"]))
        self.tool_aggregator.tools.append(IndeedScraperTool())
        start_messages = [
            self.message_class(role="system", content=SYSTEM_PROMPT),
            self.message_class(role="system", content=json.dumps(profile)),
            self.message_class(role="assistant", content=START_CHAT_PROMPT),
        ]
        self.messages = start_messages
        return self

    def create_profile(self, profile_info: dict[str, str]):
        user_data_dir = os.path.join(os.path.dirname(__file__), "../user_data/")
        profile_schema_path = os.path.join(user_data_dir, "cv_schema.json")
        profile_schema = json.load(open(profile_schema_path))
        example_profile_path = os.path.join(user_data_dir, "john_doe/default_profile.json")
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
        cv_editor = CVEditor(first_name=profile_info["first_name"], last_name=profile_info["last_name"])
        cv_editor._create_user_directory()
        with open(
            os.path.join(user_data_dir, f'{profile_info["first_name"].lower()}_{profile_info["last_name"].lower()}/default_profile.json'),
            "w",
        ) as f:
            json.dump(profile_info, f)

        cv_editor.generate_cv("default_profile")

        return profile_info
