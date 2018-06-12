from django.contrib import admin

from .models import EventLog


def false(*args, **kwargs):
    return False


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ['actor', 'verb', 'target', 'action_object', 'timestamp']
    search_fields = ['actor', 'target', 'action_object']
    list_filter = [
        'verb',
        ('actor_content_type', admin.RelatedOnlyFieldListFilter),
        ('target_content_type', admin.RelatedOnlyFieldListFilter),
        ('action_object_content_type', admin.RelatedOnlyFieldListFilter),
    ]
    date_hierarchy = 'timestamp'
    actions = None

    def get_readonly_fields(self, request, obj=None):
        fields = obj._meta.get_fields()
        fieldnames = [field.name for field in fields]
        return fieldnames

    # noop methods
    delete_model = false
    has_add_permission = false
    has_delete_permission = false
    log_change = false
    message_user = false
    save_model = false
    save_related = false
