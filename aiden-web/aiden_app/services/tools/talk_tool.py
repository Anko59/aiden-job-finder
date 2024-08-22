from typing import Iterable
from aiden_app.models import ToolMessage
from aiden_app.services.tools.tool import Tool


class TalkTool(Tool):
    def __init__(self):
        super().__init__("TalkTool")
        self.add_tool("talk", self.talk)

    def talk(self, message) -> Iterable[ToolMessage]:
        # Talk tool calls are parsed in the agent class
        return []
