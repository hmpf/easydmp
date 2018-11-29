class DefaultErrorMixin:
    def __init__(self, *args):
        try:
            message = args[0]
        except IndexError:
            message = self.default_msg
        super().__init__(message)

class FSAError(Exception):
    pass


class FSANoStartnodeError(DefaultErrorMixin, FSAError):
    default_msg = 'The FSA has no start-node'


class FSANoDataError(DefaultErrorMixin, FSAError):
    default_msg = '`data` is empty, cannot calculate'
