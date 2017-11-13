from django.conf import settings
from django.db import models
from django.db import transaction

from jsonfield import JSONField

from .client import EEStoreServer, EEStoreRepo

# With postgres 9.4+, use this instead
# from django.contrib.postgres.fields import JSONField

EESTORE_API_ROOT = 'https://eestore.paas2.uninett.no/api'


class EEStoreType(models.Model):
    name = models.CharField(max_length=64, primary_key=True)

    class Meta:
        db_table = 'easydmp_eestore_type'
        verbose_name = 'EEStore type'

    def __str__(self):
        return self.name


class EEStoreSource(models.Model):
    eestore_type = models.ForeignKey(EEStoreType, related_name='sources')
    name = models.CharField(max_length=64)

    class Meta:
        db_table = 'easydmp_eestore_source'
        verbose_name = 'EEStore source'

    def __str__(self):
        return '{}:{}'.format(self.eestore_type.name, self.name)


class EEStoreCacheManager(models.Manager):

    def get_server(self):
        return EEStoreServer(EESTORE_API_ROOT)

    def bootstrap(self):
        server = self.get_server()
        for eestore_type in server.available_repos():
            EEStoreType.objects.get_or_create(name=eestore_type)

    def get_repo(self, eestore_type):
        server = self.get_server()
        if eestore_type in server.available_repos():
            repo = server.get_repo(eestore_type)
            return repo
        return None

    def get_remote_data(self, eestore_type, search=None, source=None):
        repo = self.get_repo(eestore_type)
        return repo.get_list(source=source, search=search)

    def fill_one(self, item):
        data = item['attributes'].copy()
        text_eestore_type = item['type'].lower()
        eestore_type, _ = EEStoreType.objects.get_or_create(name=text_eestore_type)
        try:
            text_source = data.pop('source')
        except KeyError:
            print('Broken:', item)
            return
        eestore_source, _ = EEStoreSource.objects.get_or_create(name=text_source, eestore_type=eestore_type)
        eestore_pid = data.pop('pid')

        kwargs = {
            'source': eestore_source,
            'eestore_id': item['id'],
            'eestore_type': eestore_type,
            'eestore_pid': eestore_pid,
            'last_fetched': data.pop('last_fetched'),
            'name': data.pop('name'),
            'uri': data.pop('uri'),
            'remote_id': data.pop('remote_id'),
            'pid': data.pop('remote_pid'),
        }
        kwargs['data'] = data
        # get_or_create for some reason makes duplicates
        with transaction.atomic():
            try:
                self.get(eestore_pid=eestore_pid)
            except self.model.DoesNotExist:
                self.create(**kwargs)

    def fill_from_remote(self, *eestore_types):
        all_eestore_types = EEStoreType.objects.values_list('name', flat=True)
        eestore_types = set(all_eestore_types) & set(eestore_types)
        for eestore_type in eestore_types:
            data = self.get_remote_data(eestore_type)
            for entry in data:
                self.fill_one(entry)


class EEStoreCache(models.Model):
    eestore_pid = models.CharField(unique=True, max_length=255)
    eestore_id = models.IntegerField()
    eestore_type = models.ForeignKey(EEStoreType, related_name='records')
    source = models.ForeignKey(EEStoreSource, related_name='records')

    name = models.CharField(max_length=255)
    uri = models.URLField(blank=True)
    pid = models.CharField(max_length=255, blank=True)
    remote_id = models.CharField(max_length=255)

    data = JSONField(default={})
    last_fetched = models.DateTimeField(blank=True, null=True)

    objects = EEStoreCacheManager()

    class Meta:
        db_table = 'easydmp_eestore_cache'
        verbose_name = 'EEStore cache'

    def __str__(self):
        return '{}: {}'.format(self.source, self.name)


class EEStoreMount(models.Model):
    """Configure a question to fetch its choices from an eestore

    If no <sources> are given, all sources are used.
    """
    question = models.OneToOneField('dmpt.Question', related_name='eestore')
    eestore_type = models.ForeignKey(EEStoreType)
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

    def get_cached_entries(self, source=None, search=None):
        all = EEStoreCache.objects.filter(eestore_type=self.eestore_type, source__in=self.sources.all())
        return all

    def __str__(self):
        return '{}: {}'.format(self.eestore_type, self.question)
