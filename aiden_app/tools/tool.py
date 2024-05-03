import abc


class Tool(abc.ABC):
    @property
    @abc.abstractmethod
    def names_to_functions(self):
        pass
