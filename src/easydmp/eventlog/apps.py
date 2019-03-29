from django.apps import AppConfig


class EventLogConfig(AppConfig):
    name = 'easydmp.eventlog'

    def ready(self):
        import easydmp.eventlog.signals
