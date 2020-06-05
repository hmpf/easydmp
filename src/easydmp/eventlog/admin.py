from django.contrib import admin

from django.contrib.auth import get_user_model

from .models import EventLog


def false(*args, **kwargs):
    return False


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ['actor', 'verb', 'target', 'action_object', 'timestamp']
    # search_fields cannot contain generic foreign keys, and cannot be empty
    # for search to work
    search_fields = ['verb']
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

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if '@' in search_term or search_term.startswith('user:'):  # user
            user_ids = [str(uid) for uid in (get_user_model().objects
                        .filter(username__contains=search_term)
                        .values_list('id', flat=True))]
            if not user_ids:
                return queryset, use_distinct
            content_type_id = 4
            all = self.model.objects.all()
            queryset |= all.filter(actor_object_id__in=user_ids,
                                   actor_content_type_id=content_type_id)
            queryset |= all.filter(target_object_id__in=user_ids,
                                   target_content_type_id=content_type_id)
            queryset |= all.filter(action_object_object_id__in=user_ids,
                                   action_object_content_type_id=content_type_id)
            use_distinct = True
        return queryset, use_distinct

    # noop methods
    delete_model = false
    has_add_permission = false
    has_delete_permission = false
    log_change = false
    message_user = false
    save_model = false
    save_related = false
