from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db import transaction

from .client import EEStoreServer
from .utils import get_types_from_eestore
from .utils import get_sources_from_eestore
from .utils import get_entries_from_eestore
from .utils import parse_single_row

# With postgres 9.4+, use this instead
# from django.contrib.postgres.fields import JSONField

EESTORE_API_ROOT = 'https://eestore.paas2.uninett.no/api/source-types/'


__all__ = [
    'EEStoreType',
    'EEStoreSource',
    'EEStoreCache',
    'EEStoreMount',
]


def create_new_types_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    sourcetypes = get_types_from_eestore(server, endpoint)
    new_types = list()
    for sourcetype, endpoint in sourcetypes.items():
        obj, new = EEStoreType.objects.get_or_create(
            name=sourcetype,
            defaults={'name': sourcetype, 'endpoint': endpoint},
        )
        if new:
            new_types.append(obj)
    return new_types


def update_types_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    sourcetypes = get_types_from_eestore(server, endpoint)
    for sourcetype, endpoint in sourcetypes.items():
        try:
            EEStoreType.objects.get(name=sourcetype).update(
                endpoint=endpoint
            )
        except EEStoreType.DoesNotExist:
            pass


def create_new_sources_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    new_sources = []
    for repo, data in get_sources_from_eestore(server, endpoint).items():
        sourcetype, _ = EEStoreType.objects.get_or_create(
            name=repo,
            defaults={'name': repo, 'endpoint': data['endpoint']}
        )
        for name, endpoint in data['sources'].items():
            obj, new = EEStoreSource.objects.get_or_create(
                eestore_type=sourcetype,
                name=name,
                defaults={
                    'eestore_type': sourcetype,
                    'name': name,
                    'endpoint': endpoint},
            )
            if new:
                new_sources.append(obj)
    return new_sources


def update_sources_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    for repo, data in get_sources_from_eestore(server, endpoint).items():
        sourcetype, _ = EEStoreType.objects.get_or_create(
            name=repo,
            defaults={'name': repo, 'endpoint': data['endpoint']}
        )
        for name, endpoint in data['sources'].items():
            try:
                EEStoreSource.objects.get(
                    eestore_type=sourcetype,
                    name=name
                ).update(endpoint=endpoint)
            except EEStoreSource.DoesNotExist:
                pass


def update_cache_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    eestore_types = {etype.name: etype for etype in EEStoreType.objects.all()}
    sources = {source.name: source for source in EEStoreSource.objects.all()}
    unknown_types = set()
    unknown_sources = set()
    dump = get_entries_from_eestore(server, endpoint)
    for row in dump:
        item = parse_single_row(row)
        eestore_pid = item['eestore_pid']
        try:
            item['eestore_type'] = eestore_types[item['eestore_type']]
        except KeyError:
            unknown_types.add(item['eestore_type'])
            continue
        try:
            item['source'] = sources[item['source']]
        except KeyError:
            unknown_sources.add(item['source'])
            continue
        with transaction.atomic():
            try:
                EEStoreCache.objects.get(eestore_pid=eestore_pid)
            except EEStoreCache.DoesNotExist:
                EEStoreCache.objects.create(**item)
    return (unknown_types, unknown_sources)


class EEStoreTypeManager(models.Manager):

    def update_from_eestore(self, endpoint):
        update_types_from_eestore(endpoint=endpoint)


class EEStoreSourceManager(models.Manager):

    def update_from_eestore(self, api_root):
        update_sources_from_eestore(api_root)


class EEStoreCacheManager(models.Manager):

    def update_from_eestore(self, server=None, endpoint=EESTORE_API_ROOT):
        update_cache_from_eestore(server, endpoint)

    def bootstrap(self, server=None, endpoint=EESTORE_API_ROOT):
        update_types_from_eestore(server, endpoint)
        update_sources_from_eestore(server, endpoint)

    def get_repo(self, eestore_type, server=None, endpoint=EESTORE_API_ROOT):
        assert server or endpoint, 'Either `server` or `endpoint` must be given'
        server = server or EEStoreServer(endpoint)
        if eestore_type in server.available_repos:
            repo = server.get_repo(eestore_type)
            return repo
        return None

    def get_remote_data(self, eestore_type, search=None, source=None, **kwargs):
        repo = self.get_repo(eestore_type, **kwargs)
        return repo.get_list(source=source, search=search)

    def fill_one(self, item):
        kwargs = parse_single_row(item)

        eestore_pid = kwargs['eestore_pid']
        # get_or_create for some reason makes duplicates
        with transaction.atomic():
            try:
                self.get(eestore_pid=eestore_pid)
            except self.model.DoesNotExist:
                self.create(**kwargs)


class EEStoreType(models.Model):
    """
    One EEStoreType can only be fetched from a single source
    """
    name = models.CharField(max_length=64, primary_key=True)
    endpoint = models.URLField(blank=True)

#    objects = EEStoreTypeManager()

    class Meta:
        db_table = 'easydmp_eestore_type'
        verbose_name = 'EEStore type'
        unique_together = ('name', 'endpoint')

    def __str__(self):
        return self.name


class EEStoreSourceQuerySet(models.QuerySet):

    def lookup(self, colon_string):
        eestore_type, name = colon_string.split(':')
        return self.get(eestore_type=eestore_type, name=name)


class EEStoreSource(models.Model):
    eestore_type = models.ForeignKey(
        EEStoreType,
        on_delete=models.CASCADE,
        related_name='sources',
    )
    name = models.CharField(max_length=64)
    endpoint = models.URLField(blank=True)

    objects = EEStoreSourceQuerySet.as_manager()

    class Meta:
        db_table = 'easydmp_eestore_source'
        verbose_name = 'EEStore source'
        unique_together = ('eestore_type', 'name')

    def __str__(self):
        return '{}:{}'.format(self.eestore_type.name, self.name)


class EEStoreCache(models.Model):
    eestore_pid = models.CharField(unique=True, max_length=255)
    eestore_id = models.IntegerField()
    eestore_type = models.ForeignKey(
        EEStoreType,
        on_delete=models.CASCADE,
        related_name='records',
    )
    source = models.ForeignKey(
        EEStoreSource,
        on_delete=models.CASCADE,
        related_name='records',
    )

    name = models.CharField(max_length=255)
    uri = models.URLField(blank=True)
    pid = models.CharField(max_length=255, blank=True)
    remote_id = models.CharField(max_length=255)

    data = JSONField(default=dict, encoder=DjangoJSONEncoder)
    last_fetched = models.DateTimeField(blank=True, null=True)

    #objects = EEStoreCacheManager()

    class Meta:
        db_table = 'easydmp_eestore_cache'
        verbose_name = 'EEStore cache'

    def __str__(self):
        return '{}: {}'.format(self.source, self.name)


class EEStoreMount(models.Model):
    """Configure a question to fetch its choices from an eestore

    If no <sources> are given, all sources are used.
    """
    question = models.OneToOneField(
        'dmpt.Question',
        on_delete=models.CASCADE,
        related_name='eestore',
    )
    eestore_type = models.ForeignKey(EEStoreType, on_delete=models.CASCADE)
    sources = models.ManyToManyField(
        EEStoreSource,
        help_text='Select a subset of the eestore types\' sources here. Keep empty to select all types.',
        blank=True)

    class Meta:
        db_table = 'easydmp_eestore_mount'
        verbose_name = 'EEStore mount'

    def clean(self):
        # Remove invalid sources
        if self.id:
            for source in self.sources.all():
                if not source.eestore_type == self.eestore_type:
                    self.sources.remove(source)

    def clone(self, question):
        new = self.__class__.objects.create(
            question=question,
            eestore_type=self.eestore_type,
        )
        for source in self.sources.all():
            new.sources.add(source)

    def get_cached_entries(self, source=None, search=None):
        by_type = EEStoreCache.objects.filter(eestore_type=self.eestore_type)
        return by_type

    def __str__(self):
        return '{}: {}'.format(self.eestore_type, self.question)
