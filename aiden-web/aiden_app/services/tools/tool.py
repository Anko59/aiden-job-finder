import abc


class Tool(abc.ABC):
    def __init__(self, name: str):
        self.name = name
        self.names_to_functions = {}

    def add_tool(self, name, function):
        self.names_to_functions[name] = function
