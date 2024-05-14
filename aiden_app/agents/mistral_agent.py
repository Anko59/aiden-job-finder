import json
import os
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage, FunctionCall
from ..tools.talk_tool import TalkTool
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

    def _message_model(self, **kwargs) -> ChatMessage:
        kwargs.setdefault("model", self.model)
        kwargs.setdefault("messages", self.messages)
        kwargs.setdefault("tools", self.tool_aggregator.get_tools())
        kwargs.setdefault("tool_choice", self.tool_choice)
        kwargs.setdefault("temperature", 0.4)
        response = self.client.chat(**kwargs)
        message = response.choices[0].message
        message = ChatMessage(**message.model_dump())
        try:
            calls = json.loads(message.content[message.content.index("[") : message.content.rindex("]") + 1])
            message.tool_calls = [FunctionCall(**call) for call in calls]
        except Exception:
            pass
        self.messages.append(message)
        self.tokens_used += response.usage.total_tokens

        return message

    def chat(self, user_input: str):
        self.messages.append(ChatMessage(role="user", content=user_input))
        message = self._message_model()
        tool_calls = 0

        def is_waiting_for_user_message() -> bool:
            return not (bool(hasattr(message, "tool_calls") and message.tool_calls is not None) and tool_calls <= self.max_tool_calls)

        yield message.model_dump(), is_waiting_for_user_message()
        while not is_waiting_for_user_message() and len(message.tool_calls) > 0:
            for tool_call in message.tool_calls:
                function_result, agent_speaks_next = self.tool_aggregator.names_to_functions()[tool_call.function.name](
                    args_json=tool_call.function.arguments
                )
                tool_message = ChatMessage(role="tool", name=tool_call.function.name, content=function_result)
                self.messages.append(tool_message)
                tool_calls += 1
                if not agent_speaks_next:
                    yield tool_message.model_dump(), True
                    return
                yield tool_message.model_dump(), False
            message = self._message_model()
            yield message.model_dump(), is_waiting_for_user_message()
