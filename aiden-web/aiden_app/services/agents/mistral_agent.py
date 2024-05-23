from chompjs import parse_js_object
import json
import os
from uuid import uuid4

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage, FunctionCall, ToolCall
from mistralai.models.embeddings import EmbeddingResponse

from aiden_app.services.tools.talk_tool import TalkTool

from .agent import Agent


class MistralAgent(Agent):
    def __init__(self, model: str = "open-mixtral-8x22b", tool_only: bool = True):
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
            calls = parse_js_object(message.content)
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
        self.messages.append(message)
        self.tokens_used += response.usage.total_tokens

        return message

    def embed(self, message: str) -> EmbeddingResponse:
        return self.client.embeddings(model="mistral-embed", input=message)

    def _parse_tool_call(self, tool_call: ToolCall) -> tuple[ChatMessage, bool]:
        try:
            (
                function_result,
                agent_speaks_next,
            ) = self.tool_aggregator.names_to_functions()[tool_call.function.name](args_json=tool_call.function.arguments)
            if tool_call.function.name == "talk":
                message = ChatMessage(role="assistant", content=json.loads(function_result)["result"])
            else:
                message = ChatMessage(
                    role="tool",
                    name=tool_call.function.name,
                    content=function_result,
                )
        except Exception as e:
            message = ChatMessage(
                role="tool",
                name=tool_call.function.name,
                content=json.dumps({"error": str(e)}),
            )
            agent_speaks_next = False
        return message, agent_speaks_next

    def chat(self, user_input: str):
        self.messages.append(ChatMessage(role="user", content=user_input))
        message = self._message_model()
        tool_calls = 0

        while len(message.tool_calls) > 0 and tool_calls < self.max_tool_calls:
            for tool_call in message.tool_calls:
                tool_message, agent_speaks_next = self._parse_tool_call(tool_call)
                self.messages.append(tool_message)
                tool_calls += 1
                yield tool_message.model_dump()
            if agent_speaks_next:
                message = self._message_model()
            else:
                return
        yield message.model_dump()
