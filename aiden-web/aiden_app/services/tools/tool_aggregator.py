import json
import os

from aiden_app.services.tools.tool import Tool

with open(os.path.join(os.path.dirname(__file__), "tools.json")) as f:
    tools = json.load(f)


class ToolAggregator:
    def __init__(self, tools: list[Tool]):
        self.tools = tools

    def get_tools(self):
        _tools = []
        for func in tools:
            if func["function"]["name"] in self.names_to_functions():
                _tools.append(func)
        return _tools

    def get_tool(self, tool_name: str):
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None

    def names_to_functions(self):
        names_to_functions = {}
        for tool in self.tools:
            names_to_functions.update(tool.names_to_functions)
        return names_to_functions

    def serialize_tools_data(self):
        return {tool.name: tool.serialize_data() for tool in self.tools}

    def unserialize_tools_data(self, data: dict):
        for tool in self.tools:
            tool.unserialize_data(data[tool.name])
