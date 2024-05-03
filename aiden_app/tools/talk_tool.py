import functools

from .tool import Tool


class TalkTool(Tool):

    name = 'talkTool'

    @property
    def names_to_functions(self):
        return {'talk': functools.partial(self.talk)}

    def talk(self, message):
        return message
