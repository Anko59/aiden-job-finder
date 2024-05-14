from .tool import Tool


class TalkTool(Tool):
    def __init__(self):
        super().__init__("TalkTool")
        self.add_tool("talk", self.talk, agent_speaks_next=False)

    @Tool.tool_function
    def talk(self, message):
        return message
