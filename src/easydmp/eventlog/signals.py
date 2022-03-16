from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType

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
    # drf.authtoken does some really messy stuff with model proxies in order to
    # make things look prettier in the admin. The behavior has changed since
    # 2021
    if content_type.app_label == 'authtoken' and content_type.name == 'token':
        # If this isn't done, the try:/except: that follows can never succeed
        instance.object_id = instance.object_repr
        content_type = ContentType.objects.get_by_natural_key('authtoken', 'token')
        instance.content_type = content_type
    try:
        target = instance.get_edited_object()
    except content_type.model_class().DoesNotExist:
        # Serialized gfk, for deleted objects
        target = {
            'ct': content_type,
            'pk': instance.object_id,
            'value': instance.object_repr,
        }

    log_event(instance.user, verb, target=target, template=template)
