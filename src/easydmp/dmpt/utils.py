from django.contrib.admin.utils import NestedObjects
from django.db import router
from django.db import transaction
from django.template import engines
from django.utils.encoding import force_text
from django.utils.html import format_html, escape


DJANGO_TEMPLATE_ENGINE = engines['django']

__all__ = (
    'render_from_string',
    'force_items_to_str',
    'print_url',
    'DeletionMixin',
    'RenumberMixin',
)


def render_from_string(template_string, context=None):
    if context is None:
        context = {}
    template = DJANGO_TEMPLATE_ENGINE.from_string(template_string)
    return template.render(context)


def force_items_to_str(dict_):
    return {force_text(k): force_text(v) for k, v in dict_.items()}


def print_url(urldict):
    url = urldict['url']
    name = urldict.get('name', '')
    name = name if name else url
    format = '<a href="{}">{}</a>'
    return format_html(format, url, escape(name))


class DeletionMixin:
    """Extend django's model deletion functionality"""

    def collect(self, **kwargs):
        """Collect objects related to self

        Designed to be extended. Get the collector for self with super()::

            collector = super().collect(**kwargs)

        Add a queryset with::

            collector.collect(queryset)

        Add an instance with::

            collector.collect([instance])

        Finally, return the collector.
        """
        using = getattr(kwargs, 'using', router.db_for_write(self.__class__, instance=self))
        assert self._get_pk_val() is not None, (
            "%s object can't be deleted because its %s attribute is set to None." %
            (self._meta.object_name, self._meta.pk.attname)
        )

        collector = NestedObjects(using=using)
        collector.collect([self], **kwargs)
        return collector

    @transaction.atomic
    def delete(self, **kwargs):
        collector = self.collect(**kwargs)
        return collector.delete()
    delete.alters_data = True


class RenumberMixin:

    def _renumber_positions(self, objects):
        """Renumber positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)

        <objects> must already be sorted by position.
        """
        for i, obj in enumerate(objects, 1):
            obj.position = i
            obj.save()
    _renumber_positions.alters_data = True
