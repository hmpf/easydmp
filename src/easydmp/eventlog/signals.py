from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION

from .utils import log_event


@receiver(post_save, sender='admin.LogEntry')
def add_admin_log_entry_to_eventlog(sender, instance, **kwargs):
    verb_choice = {
        ADDITION: {
            'verb': 'create in admin',
            'template': '{timestamp} {actor} created {target} in the admin'
        },
        CHANGE: {
            'verb': 'update in admin',
            'template': '{timestamp} {actor} updated {target} in the admin'
        },
        DELETION: {
            'verb': 'delete in admin',
            'template': '{timestamp} {actor} deleted {target} in the admin'
        },
    }
    flag = instance.action_flag
    verb = verb_choice[flag]['verb']
    template = verb_choice[flag]['template']
    content_type = instance.content_type
    try:
        target = instance.get_edited_object()
    except content_type.model_class().DoesNotExist:
        target = {'ct': content_type, 'pk': instance.object_id, 'value':
                  instance.object_repr}

    log_event(instance.user, verb, target=target, template=template)
