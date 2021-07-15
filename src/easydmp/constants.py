# NO IMPORTS EVER in this module, must be safe to import


__all__ = [
    'Falsey',
    'NotSet',
]


class Falsey():

    def __bool__(self):
        return False


NotSet = Falsey()  # In addition to None
