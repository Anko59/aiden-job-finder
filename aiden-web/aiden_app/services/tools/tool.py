import abc


class Tool(abc.ABC):
    def __init__(self, name: str):
        self.name = name
        self.names_to_functions = {}
        self.data = {}

    def add_tool(self, name, function):
        self.names_to_functions[name] = function

    def serialize_data(self):
        return self.data

    def unserialize_data(self, data):
        self.data = data
