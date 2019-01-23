import logging


class SQLFilter(logging.Filter):

    def __init__(self, keywords=None):
        self.keywords = keywords

    def filter(self, record):
        if self.keywords and record.name == 'django.db.backends':
            msg = record.getMessage().split()[1]
            if msg in self.keywords:
                return False
        return True
