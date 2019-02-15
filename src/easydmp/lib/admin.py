from django.contrib import admin


class FakeBooleanFilter(admin.SimpleListFilter):

    def lookups(self, request, _model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        lookup = '{}__isnull'.format(self.parameter_name)
        if self.value() == 'yes':
            return queryset.filter(**{lookup: False})
        if self.value() == 'no':
            return queryset.filter(**{lookup: True})


class PublishedFilter(FakeBooleanFilter):
    title = 'public'
    parameter_name = 'published'


class RetiredFilter(FakeBooleanFilter):
    title = 'retired'
    parameter_name = 'retired'
