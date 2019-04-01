from .models import EventLog


def log_event(actor, verb, target=None, object=None, template='',
              timestamp=None, extra=None, using=None):
    EventLog.objects.log_event(actor, verb, target, object, template,
              timestamp, extra, using)
