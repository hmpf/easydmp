from uuid import uuid4
from io import StringIO
import json

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.messages import get_messages
from django.test import TestCase as DjangoTestCase, override_settings, Client, tag, skipUnlessDBFeature
from django.urls import reverse

from easydmp.dmpt.admin import TemplateAdmin
from easydmp.dmpt.export_template import ExportSerializer
from easydmp.dmpt.models import Template, TemplateImportMetadata

from tests.auth.factories import SuperuserFactory
from tests.dmpt.factories import *

VERSION = 'blbl'


def create_minimum_template():
    template = TemplateFactory()
    section = SectionFactory(template=template, position=1)
    question = QuestionFactory(input_type_id='shortfreetext', section=section, position=1)
    return template


@tag('JSONField', 'view')
@override_settings(VERSION=VERSION)
class TestImportTemplate(DjangoTestCase):

    def setUp(self):
        self.superuser = SuperuserFactory()
        self.client = Client()
        self.admin = TemplateAdmin(model=Template, admin_site=AdminSite())
        self.template = create_minimum_template()
        template_export = self.template.create_export_object()
        template_export_dict = ExportSerializer(template_export).data
        # ensure that the export looks different from the local template
        template_export_dict['template']['uuid'] = str(uuid4())
        template_export_json = json.dumps(template_export_dict)
        self.template_export_file = StringIO(template_export_json)

    def test_import_template_should_create_template(self):
        self.client.force_login(self.superuser)
        url = reverse('admin:dmpt_template_import')
        response = self.client.post(url, {'template_export_file': self.template_export_file})
        self.assertEqual(response.status_code, 302)
        tims = TemplateImportMetadata.objects.all()
        self.assertEqual(tims.count(), 1)
        self.assertEqual(Template.objects.count(), 2)
        tim = tims.get()
        self.assertTrue(tim.template.title.startswith(self.template.title))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages, 'No messages sent')
        # TODO: test auditlog, admin.log
