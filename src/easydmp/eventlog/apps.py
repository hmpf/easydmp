from django.apps import AppConfig


class EasyDMPEventLogConfig(AppConfig):
    name = 'easydmp.eventlog'

    def ready(self):
        import easydmp.eventlog.signals
