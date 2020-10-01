from functools import reduce
from operator import or_
from copy import deepcopy

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.timezone import now as tznow

from jsonfield import JSONField


GFK_MAPPER = {
    'actor': {'ct': 'actor_content_type', 'id': 'actor_object_id'},
    'target': {'ct': 'target_content_type', 'id': 'target_object_id'},
    'action_object': {
        'ct': 'action_object_content_type',
        'id': 'action_object_object_id'
    },
}
Q = models.Q


def _get_gfk(obj):
    obj_ct = ContentType.objects.get_for_model(obj)
    obj_id = obj.pk
    return (obj_ct, obj_id)


def _get_remote_obj(obj_ct, obj_id):
    if obj_ct and obj_id:
        obj = obj_ct.get_object_for_this_type(pk=obj_id)
        return obj


def _serialize_gfk(obj):
    if not obj:
        return
    if isinstance(obj, dict):
        ct = obj['ct']
        pk = obj['pk']
        value = obj['value']
    else:
        ct, pk = _get_gfk(obj)
        value = str(obj)
    return {
        'ct': {'pk': ct.pk, 'name': str(ct)},
        'pk': pk,
        'value': str(obj)
    }


def delazify_object(obj):
    if hasattr(obj, '_wrapped') and hasattr(obj, '_setup'):
        if obj._wrapped.__class__ == object:
            obj._setup()
        obj = obj._wrapped
    return obj


def _format_obj(obj):
    try:
        objstring = obj.logprint()
    except AttributeError:
        obj = delazify_object(obj)
        objstring = repr(obj).strip('<>')
    return objstring


def _format_timestamp(timestamp):
    "Print timestamp in JSON serializer compatible format"
    timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f%Z')
    timestamp = timestamp.replace('UTC', 'Z', 1)
    return timestamp


def _format_description(kwargs, description_template):
    context = deepcopy(kwargs)
    context['timestamp'] = _format_timestamp(context['timestamp'])
    for field in ('actor', 'target', 'action_object'):
        obj = kwargs[field]
        if not obj:
            continue
        objstring = _format_obj(obj)
        context[field] = objstring
    return description_template.format(**context)


def _serialize_event(kwargs):
    data = {}
    data['actor'] = _serialize_gfk(kwargs['actor'])
    data['target'] = _serialize_gfk(kwargs['target'])
    data['action_object'] = _serialize_gfk(kwargs['action_object'])
    # copy the rest
    for field in ('verb', 'description', 'timestamp', 'extra'):
        data[field] = kwargs[field]
    return data


class EventLogQuerySet(models.QuerySet):

    def delete(self):
        return (0, {})
    delete.queryset_only = True  # type: ignore

    def update(self, **_):
        return 0
    update.queryset_only = True  # type: ignore

    def _get_gfks(self, field, *objects):
        ct = GFK_MAPPER[field]['ct']
        id = GFK_MAPPER[field]['id']
        q_objs = []
        for obj in objects:
            if not obj:
                continue
            obj_ct, obj_id = _get_gfk(obj)
            lookups = {ct: obj_ct, id: obj_id}
            q_objs.append(Q(**lookups))
        return self.filter(reduce(or_, q_objs))

    def actors(self, *actors):
        return self._get_gfks('actor', *actors)

    def targets(self, *targets):
        return self._get_gfks('target', *targets)

    def action_objects(self, *action_objects):
        return self._get_gfks('action_object', *action_objects)

    def model_actions(self, model):
        ct = ContentType.objects.get_for_model(model)
        return self.filter(
            Q(actor_content_type=ct),
            Q(target_content_type=ct),
            Q(action_object_content_type=ct),
        )

    def any(self, obj):
        ct = ContentType.objects.get_for_model(obj)
        qs = self.actors(obj) | self.targets(obj) | self.action_objects(obj)
        return qs.distinct()


class EventLogManager(models.Manager):

    def log_event(self, actor, verb, target=None, action_object=None,
                  description_template='', timestamp=None, extra=None,
                  using=None):
        """Log event

        `actor`, `target` and `action_object` are model instances. `actor`
        is required.

        `verb` is a short string, preferrably an infinitive. It should not
        duplicate information about the model instances of `actor`, `target`
        or `action_object`.

        `description_template` is used to build a human-readble string from
        the other arguments.

         `timestamp` must be a datetime with timezone

        `extra` must be JSON serializable, preferrably a dict. The info will
        be added to the `data`-field, and may be looked up from the
        `description_template`.
        """
        timestamp = timestamp if timestamp else tznow()
        description = _format_description(locals(), description_template)
        data = _serialize_event(locals())
        return self.create(
            actor=actor,
            target=target,
            action_object=action_object,
            verb=verb,
            description=description,
            timestamp=timestamp,
            data=data,
        )


class EventLog(models.Model):
    actor_content_type = models.ForeignKey(ContentType,
                                           on_delete=models.DO_NOTHING,
                                           related_name='actor', db_index=True)
    actor_object_id = models.TextField(db_index=True)

    verb = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, null=True)

    target_content_type = models.ForeignKey(ContentType,
                                            on_delete=models.DO_NOTHING,
                                            blank=True, null=True,
                                            related_name='target',
                                            db_index=True)
    target_object_id = models.TextField(blank=True, null=True, db_index=True)

    action_object_content_type = models.ForeignKey(ContentType,
                                                   on_delete=models.DO_NOTHING,
                                                   blank=True, null=True,
                                                   related_name='action_object',
                                                   db_index=True)
    action_object_object_id = models.TextField(blank=True, null=True,
                                               db_index=True)

    data = JSONField(default={})
    timestamp = models.DateTimeField(default=tznow, db_index=True)

    objects = EventLogManager.from_queryset(EventLogQuerySet)()

    class Meta:
        ordering = ('-timestamp',)

    def __str__(self):
        return self.description

    def delete(self, **_):
        # Deletion not allowed
        return (0, {})

    @property
    def actor(self):
        obj_ct = self.actor_content_type
        obj_id = self.actor_object_id
        return _get_remote_obj(obj_ct, obj_id)

    @actor.setter
    def actor(self, actor):
        obj_ct, obj_id = _get_gfk(actor)
        self.actor_content_type = obj_ct
        self.actor_object_id = obj_id

    @property
    def target(self):
        obj_ct = self.target_content_type
        obj_id = self.target_object_id
        return _get_remote_obj(obj_ct, obj_id)

    @target.setter
    def target(self, target):
        if target:
            obj_ct, obj_id = _get_gfk(target)
            self.target_content_type = obj_ct
            self.target_object_id = obj_id

    @property
    def action_object(self):
        obj_ct = self.action_object_content_type
        obj_id = self.action_object_object_id
        return _get_remote_obj(obj_ct, obj_id)

    @action_object.setter
    def action_object(self, action_object):
        if action_object:
            obj_ct, obj_id = _get_gfk(action_object)
            self.action_object_content_type = obj_ct
            self.action_object_object_id = obj_id
