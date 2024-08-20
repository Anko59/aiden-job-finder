from typing import Iterable
from aiden_app.models import ToolMessage
from django.template.loader import render_to_string
from aiden_app.services.tools.tool import Tool


class TalkTool(Tool):
    def __init__(self):
        super().__init__("TalkTool")
        self.add_tool("talk", self.talk)

    def talk(self, message) -> Iterable[ToolMessage]:
        message = {"role": "assistant", "content": message}
        yield ToolMessage(
            function_nane="talk",
            agent_message=message,
            user_message=render_to_string("langui/message.html", message),
        )
