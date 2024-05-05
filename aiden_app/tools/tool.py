import abc
import functools
import json


class Tool(abc.ABC):
    def __init__(self, name: str):
        self.name = name
        self.names_to_functions = {}

    def add_tool(self, name, function, agent_speaks_next=True):
        self.names_to_functions[name] = functools.partial(function, func_name=name, agent_speaks_next=agent_speaks_next)

    def tool_function(func):
        @functools.wraps(func)
        def wrapper(self, func_name, agent_speaks_next, args_json):
            function_params = json.loads(args_json)
            response = {"name": func_name, "arguments": str(function_params)}
            try:
                result = func(self, **function_params)
                response["result"] = result
                return json.dumps(response), agent_speaks_next
            except Exception as e:
                response["result"] = {"error": str(e)}
                return json.dumps(response), agent_speaks_next

        return wrapper
