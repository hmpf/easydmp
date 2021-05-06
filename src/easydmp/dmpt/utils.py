from __future__ import annotations

from typing import Callable

from django.contrib.admin.utils import NestedObjects
from django.db import router
from django.db import transaction
from django.db.models import (
    ExpressionWrapper, IntegerField, Max, Value,
)
from django.db.models.functions import Coalesce
from django.template import engines
from django.utils.encoding import force_text
from django.utils.html import format_html, escape

from .positioning import Move, get_new_index, flat_reorder


DJANGO_TEMPLATE_ENGINE = engines['django']

__all__ = (
    'render_from_string',
    'force_items_to_str',
    'print_url',
    'DeletionMixin',
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


# Reordering utility functions
# Needed in migrations so cannot only be model methods :/


def _reorder_dependent_models(value, movement: Move, get_order:
                              Callable[[], tuple], set_order:
                              Callable[[list], None], **kwargs):
    order = get_order(**kwargs)
    # May raise ValueError, this is expected
    new_index = get_new_index(movement, order, value)
    new_order = flat_reorder(order, value, new_index)
    set_order(new_order, **kwargs)


class PositionUtils:

    @classmethod
    def get_next_position(cls, queryset):
        "Get next unused position for queryset"
        result = queryset.aggregate(position_max=Coalesce(
            ExpressionWrapper(Max('position') + Value(1), output_field=IntegerField()),
            Value(1)
        ))
        return result['position_max']

    @classmethod
    def _set_order(cls, qs, pk_list, start=1):
        assert qs.count() >= len(pk_list), "More pk's than objects to change"
        Model = qs.model
        qs.bulk_update(
            [Model(pk=pk, position=pos) for pos, pk in enumerate(pk_list, start)],
            ['position']
        )

    @classmethod
    def set_order(cls, queryset, pk_list):
        # This assumes positions are unique. Override otherwise
        # First: get first unusued position and reorder starting with that one
        # This prevents triggering an IntegrityError (for duplicate positions)
        startpos = cls.get_next_position(queryset)
        cls._set_order(queryset, pk_list, startpos)
        # Then: Renumber positions, starting from 1, for debugging readability
        cls._set_order(queryset, pk_list)

    @classmethod
    def get_order(cls, queryset):
        # This assumes positions are unique. Override otherwise
        return [obj.pk for obj in queryset.order_by('position')]

    @classmethod
    def renumber_positions(cls, manager, objects):
        """Renumber positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)

        Assumes <objects> are in the correct order already.
        """
        pk_list = [obj.pk for obj in objects]
        cls.set_order(manager, pk_list)


class SectionPositionUtils(PositionUtils):

    @classmethod
    def ordered_section_subsections(cls, section):
        result = [section]
        try:
            sections = list(section.subsections.order_by('position'))
        except AttributeError:
            return result

        for section in sections:
            result.extend(cls.ordered_section_subsections(section))
        return result

    @classmethod
    def ordered_template_sections(cls, template):
        topmost_sections = template.sections.filter(super_section=None)
        result = []
        for section in topmost_sections.order_by('position'):
            result.extend(cls.ordered_section_subsections(section))
        return result


# Model mixins


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
        using = getattr(kwargs, 'using', router.db_for_write(self.__class__,
                                                             instance=self))
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
