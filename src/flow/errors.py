class FSAError(Exception):
    pass


class FSANoStartnodeError(FSAError):
    default_msg = 'The FSA has no start-node'

    def __init__(self, *args):
        try:
            message = args[0]
        except IndexError:
            message = default_msg
        super().__init__(message)

