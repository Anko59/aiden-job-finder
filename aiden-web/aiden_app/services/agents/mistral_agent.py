from typing import Iterable
from chompjs import parse_js_object
import json
import os
from uuid import uuid4

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage, FunctionCall, ToolCall
from mistralai.models.embeddings import EmbeddingResponse
from django.template.loader import render_to_string

from aiden_app.services.tools.talk_tool import TalkTool
from aiden_app.models import ToolMessage

from .agent import Agent


class MistralAgent(Agent):
    def __init__(self, model: str = "mistral-large-latest", tool_only: bool = True):
        self.model = model
        super().__init__(ChatMessage)
        self.client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
        self.tool_choice = "auto"
        if tool_only:
            self.tool_aggregator.tools.append(TalkTool())
            self.tool_choice = "any"

    def serialize_messages(self) -> list[dict[str, str]]:
        return [message.model_dump() for message in self.messages]

    def unserialize_messages(self, messages: list[dict[str, str]]) -> None:
        self.messages = [ChatMessage(**message) for message in messages]

    def _additional_message_parsing(self, message: ChatMessage) -> ChatMessage:
        if "```" in message.content:
            message.content = message.content[message.content.index("```") + 3 : message.content.rindex("```")]
            message.content = message.content.strip()
        try:
            # Sometimes the tool calls are not properly parsed by the API
            # This is a workaround to parse the tool calls from the message content
            calls = parse_js_object(message.content.replace("\n", "\\n"))
            message.tool_calls = [
                ToolCall(
                    id=uuid4().hex[0:9],
                    function=FunctionCall(name=call["name"], arguments=json.dumps(call["arguments"])),
                )
                for call in calls
            ]
            message.content = ""
        except Exception:
            pass
        if not hasattr(message, "tool_calls") or message.tool_calls is None:
            message.tool_calls = []
        return message

    def _parse_talk_tool_call(self, message: ChatMessage) -> ChatMessage:
        if not message.tool_calls or len(message.tool_calls) == 0:
            return message
        if message.tool_calls[0].function.name == "talk":
            content = json.loads(message.tool_calls[0].function.arguments)["message"]
            return ChatMessage(role="assistant", content=content, tool_calls=[])
        return message

    def _message_model(self, **kwargs) -> ChatMessage:
        kwargs.setdefault("model", self.model)
        kwargs.setdefault("messages", self.messages)
        kwargs.setdefault("tools", self.tool_aggregator.get_tools())
        kwargs.setdefault("tool_choice", self.tool_choice)
        kwargs.setdefault("temperature", 0.4)
        response = self.client.chat(**kwargs)
        message = response.choices[0].message
        message = ChatMessage(**message.model_dump())
        message = self._additional_message_parsing(message)
        message = self._parse_talk_tool_call(message)
        self.messages.append(message)
        self.tokens_used += response.usage.total_tokens

        return message

    def embed(self, message: str) -> EmbeddingResponse:
        return self.client.embeddings(model="mistral-embed", input=message)

    def format_no_tool_call_message(self, message: ChatMessage) -> ToolMessage:
        return ToolMessage(
            function_nane="talk",
            agent_message=message.model_dump(),
            user_message=render_to_string("langui/message.html", message.model_dump()),
        )

    def chat(self, user_input: str) -> Iterable[ToolMessage]:
        self.messages.append(ChatMessage(role="user", content=user_input))
        message = self._message_model()
        if len(message.tool_calls) == 0:
            yield self.format_no_tool_call_message(message)

        for tool_call in message.tool_calls:
            func = self.tool_aggregator.names_to_functions()[tool_call.function.name]
            args = json.loads(tool_call.function.arguments)
            for tool_message in func(**args):
                tool_message: ToolMessage = tool_message
                if tool_message.agent_message is not None:
                    self.messages.append(ChatMessage(**tool_message.agent_message))
                if tool_message.user_message is not None:
                    yield tool_message
        if self.messages[-1].role == "tool":
            # Dirty fix for "Unexpected role 'user' after role 'tool'" error
            self.messages.append(ChatMessage(role="assistant", content="I performed the tool call."))
