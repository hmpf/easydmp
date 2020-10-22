from collections import OrderedDict

from django import test

from easydmp.auth.models import User
from easydmp.dmpt.models import Template
from easydmp.plan.models import Plan
from tests.dmpt.factories import TemplateFactory, SectionFactory
from tests.plan.factories import PlanFactory


class TestPlanValidation(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()
        self.section = SectionFactory(template=self.template, position=1)

    def test_validate_plan_empty_plan(self):
        plan = PlanFactory(template=self.template)
        plan.data = None
        plan.template.list_unknown_questions = lambda x: set()
        result = plan.validate_data(recalculate=False)
        expected = False
        self.assertEqual(result, expected)

# TODO: replace with test that verifies that answers for deleted questions get
# deleted on save/verify
#     def test_validate_plan_wrong_pks_in_plan(self):
#         plan = PlanFactory(template=self.template)
#         plan.data = None
#         plan.template.list_unknown_questions = lambda x: set((56, 57))
#         with self.assertLogs(logger='easydmp.dmpt.models', level='ERROR') as log:
#             result = plan.validate_data(recalculate=False)
#             expected = False
#             self.assertEqual(result, expected)
#             self.assertIn('contains nonsense data:', log.output[0])

    def test_search_data(self):
        plan = PlanFactory(template=self.template)
        plan.data = OrderedDict({
            "29": {
                "notes": "",
                "choice": "Yes"
            },
            "101": {
                "notes": "",
                "choice": [
                    {
                        "access_url": "",
                        "type": "teddybear",
                        "reason": "All teddybears will be mine, just mine."
                    }
                ]
            },
            "81": {
                "notes": "",
                "choice": [
                    {
                        "url": "http://www.adressa.no",
                        "name": ""
                    },
                    {
                        "url": "http://www.foo.no",
                        "name": "FOO!"
                    }
                ]
            },
            "98": {
                "notes": "blbl",
                "choice": {
                    "not-listed": True,
                    "choices": [
                        "license:creativecommons/81b21ab2-9545-4526-b281-e372751800b0"
                    ]
                }
            },
            "79": {
                "notes": "",
                "choice": [
                    "fileformat:pronom-generic/e3bb0d2f-85dd-455e-bc39-cecbf9d2b9ed",
                    "fileformat:pronom-generic/5ead5583-1fc7-4469-a6aa-102989e929a0"
                ]
            },
            "31": {
                "notes": "",
                "choice": {
                    "end": "2018-01-27",
                    "start": "2018-01-08"
                }
            },
            "30": {
                "notes": "",
                "choice": [
                    "surprise",
                    "fear"
                ]
            },
            "59": {
                "notes": "",
                "choice": 3
            },
            "115": {
                "notes": "",
                "choice": {
                    "not-listed": False,
                    "choices": "license:creativecommons/2b6751e3-57fa-423b-ae74-f978beae773e"
                }
            },
            "60": {
                "notes": "dsqdqw",
                "choice": "fileformat:pronom-generic/25761c33-bea4-4684-86ac-565594e601f1"
            },
            "80": {
                "notes": "",
                "choice": {
                    "url": "http://www.vg.no",
                    "name": "VG"
                }
            },
            "28": {
                "choice": "To get to the other side",
                "notes": "This is possibly the worst joke ever, on par with \"knock-knock\"-jokes."
            },
            "58": {
                "notes": "",
                "choice": "bah"
            },
            "32": {
                "notes": "",
                "choice": "Yes"
            }
        })
        self.assertEqual(
            "29 notes choice Yes 101 notes choice access_url type teddybear reason All teddybears will be mine, "
            "just mine. 81 notes choice url http://www.adressa.no name  url http://www.foo.no name FOO! 98 notes blbl "
            "choice not-listed True choices license:creativecommons/81b21ab2-9545-4526-b281-e372751800b0 79 notes "
            "choice fileformat:pronom-generic/e3bb0d2f-85dd-455e-bc39-cecbf9d2b9ed  fileformat:pronom-generic/5ead5583-"
            "1fc7-4469-a6aa-102989e929a0 31 notes choice end 2018-01-27 start 2018-01-08 30 notes choice surprise  fear "
            "59 notes choice 3 115 notes choice not-listed choices license:creativecommons/2b6751e3-57fa-423b-ae74-"
            "f978beae773e 60 notes dsqdqw choice fileformat:pronom-generic/25761c33-bea4-4684-86ac-565594e601f1 80 "
            "notes choice url http://www.vg.no name VG 28 choice To get to the other side notes This is possibly the "
            "worst joke ever, on par with \"knock-knock\"-jokes. 58 notes choice bah 32 notes choice Yes ",
            plan._search_data_in(plan.data))
