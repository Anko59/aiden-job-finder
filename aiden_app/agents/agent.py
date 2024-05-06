import json
from typing import Any, Dict, List, Tuple
from abc import ABC, abstractmethod

from ..tools.cv_editor_tool import CVEditorTool
from ..tools.indeed_scraper_tool import IndeedScraperTool
from ..tools.tool_aggregator import ToolAggregator
from .prompts import START_CHAT_PROMPT, SYSTEM_PROMPT


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
    def serialize_messages(self) -> list[Dict[str, str]]:
        pass

    @abstractmethod
    def unserialize_messages(self, messages: str) -> None:
        pass

    def to_json(self) -> str:
        state = self.__dict__.copy()
        del state["client"]
        del state["tool_aggregator"]
        del state["message_class"]
        state["messages"] = self.serialize_messages()
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

    @classmethod
    def for_profile_creation(cls, profile_info: dict[str, str], *args, **kwargs) -> "Agent":
        self = cls(*args, **kwargs)
        start_messages = [
            self.message_class(role="system", content=SYSTEM_PROMPT),
            self.message_class(role="assistant", content=START_CHAT_PROMPT),
        ]
        self.messages = start_messages
        return self
