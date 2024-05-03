import json
import os

with open(os.path.join(os.path.dirname(__file__), 'tools.json')) as f:
    tools = json.load(f)


class ToolAggregator:
    def __init__(self, tools):
        self.tools = tools

    def get_tools(self):
        _tools = []
        for func in tools:
            if func['function']['name'] in self.names_to_functions():
                _tools.append(func)
        return _tools

    def get_tool(self, tool_name):
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None

    def names_to_functions(self):
        names_to_functions = {}
        for tool in self.tools:
            names_to_functions.update(tool.names_to_functions)
        return names_to_functions
