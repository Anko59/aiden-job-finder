import json
import os

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage, FunctionCall

from ..tools.cv_editor_tool import CVEditorTool
from ..tools.indeed_scraper_tool import IndeedScraperTool
from ..tools.talk_tool import TalkTool
from ..tools.tool_aggregator import ToolAggregator
from .prompts import START_CHAT_PROMPT, SYSTEM_PROMPT


class MistralAgent:
    def __init__(self, profile: dict):
        self.model = 'open-mixtral-8x22b'
        self.client = MistralClient(api_key=os.environ.get('MISTRAL_API_KEY'))
        self.tool_aggregator = ToolAggregator(
            [
                CVEditorTool(first_name=profile['first_name'], last_name=profile['last_name']),
                IndeedScraperTool(),
            ]
        )
        self.messages = [
            ChatMessage(role='system', content=SYSTEM_PROMPT),
            ChatMessage(role='system', content=json.dumps(profile)),
            ChatMessage(role='assistant', content=START_CHAT_PROMPT),
        ]
        self.tokens_used = 0
        self.max_tool_calls = 5
        self.profile = profile

    def _message_model(self):
        response = self.client.chat(
            model=self.model,
            messages=self.messages,
            tools=self.tool_aggregator.get_tools(),
            tool_choice='auto',
            temperature=0,
        )
        message = response.choices[0].message
        try:
            calls = json.loads(message.content[message.content.index('[') : message.content.rindex(']') + 1])
            message.tool_calls = [FunctionCall(**call) for call in calls]
        except Exception:
            pass
        print(message)
        self.messages.append(message)
        self.tokens_used += response.usage.total_tokens
        return message

    def chat(self, user_input):
        self.messages.append(ChatMessage(role='user', content=user_input))
        message = self._message_model()
        tool_calls = 0

        def is_waiting_for_user_message():
            return not (bool(hasattr(message, 'tool_calls') and message.tool_calls is not None) and tool_calls <= self.max_tool_calls)

        yield message, is_waiting_for_user_message()
        while not is_waiting_for_user_message() and len(message.tool_calls) > 0:
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_params = json.loads(tool_call.function.arguments)
                function_result = self.tool_aggregator.names_to_functions()[function_name](**function_params)
                function_result = json.loads(function_result)
                function_result = {
                    'name': function_name,
                    'arguments': str(function_params),
                    'result': function_result,
                }
                function_result = json.dumps(function_result)
                tool_message = ChatMessage(role='tool', name=function_name, content=function_result)
                self.messages.append(tool_message)
                tool_calls += 1
                yield tool_message, False
            message = self._message_model()
            yield message, is_waiting_for_user_message()


class MistralAgentToolOnly(MistralAgent):
    def __init__(self, profile):
        super().__init__(profile)
        self.tool_aggregator.tools.append(TalkTool())
        breakpoint()

    def _message_model(self):
        response = self.client.chat(
            model=self.model,
            messages=self.messages,
            tools=self.tool_aggregator.get_tools(),
            tool_choice='any',
            temperature=0.4,
        )
        message = response.choices[0].message
        if message.tool_calls is not None:
            not_talk_calls = [tool_call for tool_call in message.tool_calls if tool_call.function.name != 'talk']
            if not len(not_talk_calls):
                talk_calls = [tool_call for tool_call in message.tool_calls if tool_call.function.name == 'talk']
                message_content = '\n'.join([json.loads(tool_call.function.arguments)['message'] for tool_call in talk_calls])
                message = ChatMessage(role='assistant', content=message_content)
            else:
                message.tool_calls = not_talk_calls
        self.messages.append(message)
        self.tokens_used += response.usage.total_tokens
        print(message)
        return message
