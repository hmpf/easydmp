from datetime import datetime

from django import test

from easydmp.dmpt.models.questions.datetime import DateTimeForm
from easydmp.dmpt.utils import make_qid

from tests.dmpt.factories import (
    TemplateFactory,
    SectionFactory,
    QuestionTypeFactory,
    QuestionFactory,
)
from easydmp.lib import UTC


class TestDateTimeForm(test.TestCase):

    def setUp(self):
        template = TemplateFactory()
        section = SectionFactory(template=template, position=1)
        question_type = QuestionTypeFactory(id='datetime')
        question = QuestionFactory(section=section, input_type=question_type)
        self.question = question.get_instance()

    def test_has_correct_json_schema(self):
        form = DateTimeForm(question=self.question)
        result_schema = form.serialize_choice()
        expected_schema = {'type': 'string', 'format': 'date-time'}
        self.assertEqual(result_schema, expected_schema)

    def test_cleans_to_datetime_utc(self):
        data = '2022-01-01T01:02:03Z'
        prefix = make_qid(self.question.pk)
        bound_form = DateTimeForm(data={f'{prefix}-choice': data}, question=self.question)
        self.assertTrue(bound_form.is_valid())
        result = bound_form.cleaned_data['choice']
        expected = datetime(2022, 1, 1, 1, 2, 3, tzinfo=UTC)
        self.assertEqual(result, expected)

    def test_cleans_to_datetime_naive(self):
        data = '2022-01-01T01:02:03'
        prefix = make_qid(self.question.pk)
        bound_form = DateTimeForm(data={f'{prefix}-choice': data}, question=self.question)
        self.assertTrue(bound_form.is_valid())
        result = bound_form.cleaned_data['choice']
        expected = datetime(2022, 1, 1, 1, 2, 3)
        self.assertEqual(result, expected)
