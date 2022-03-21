from django import test

from easydmp.dmpt.flow import Transition
from easydmp.dmpt.models import ExplicitBranch
from easydmp.dmpt.positioning import Move

from tests.dmpt.factories import (
    TemplateFactory,
    SectionFactory,
    QuestionTypeFactory,
    QuestionFactory,
    BooleanQuestionFactory,
    ChoiceQuestionFactory,
    ReasonQuestionFactory,
    CannedAnswerFactory,
)


class TestTypedIdentifierQuestion(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()
        self.section = SectionFactory(template=self.template, position=1)
        self.question_type = QuestionTypeFactory(id='typedidentifier')

    def test_typedidentifier_can_be_an_identifier(self):
        q = QuestionFactory(section=self.section, input_type=self.question_type)
        self.assertTrue(q.can_identify)
        answer = {'identifier': 'bgjnhk', 'type': 'chvgy'}
        self.assertEqual(answer['identifier'], q.get_identifier(answer))
