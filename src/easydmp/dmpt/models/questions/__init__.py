from datetime import date
import logging

from django.utils.safestring import mark_safe

from easydmp.constants import NotSet

from .mixins import ChoiceValidationMixin
from .mixins import EEStoreMixin
from .mixins import IsSetValidationMixin
from .mixins import NoCheckMixin
from .mixins import NotListedMixin
from .mixins import PrimitiveTypeMixin
from .mixins import SaveMixin
from ..base import Question
from ...typing import AnswerChoice, Data
from ...utils import print_url
from ...utils import render_from_string

from easydmp.lib import pprint_list


LOG = logging.getLogger(__name__)


# models, querysets, managers


class BooleanQuestion(ChoiceValidationMixin, SaveMixin, Question):
    """A branch-capable question answerable with "Yes" or "No"

    The choice is converted to True or False.
    """
    TYPE = 'bool'
    branching_possible = True

    class Meta:
        proxy = True

    def is_valid(self):
        canned_answers = self.canned_answers.values_list('choice', flat=True)
        if set(canned_answers) == set(('Yes', 'No')):
            return True
        return False

    def _serialize_condition(self, answer):
        """
        answer in (True, False)
        """
        if answer is True:
            return 'Yes'
        if str(answer).lower() in ('true', 'yes', 'on'):
            return 'Yes'
        return 'No'

    def get_choices(self):
        choices = (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )
        return choices


class ChoiceQuestion(ChoiceValidationMixin, SaveMixin, Question):
    "A branch-capable question answerable with one of a small set of choices"
    TYPE = 'choice'
    branching_possible = True

    class Meta:
        proxy = True

    def is_valid(self):
        if self.canned_answers.count() > 1:
            return True
        return False

    def _serialize_condition(self, answer):
        """
        Return answer unchanged
        """
        return answer

    def get_choices(self):
        choices = self.canned_answers.order().values_list('choice', 'canned_text')
        fixed_choices = []
        for (k, v) in choices:
            if not v:
                v = k
            fixed_choices.append((k, v))
        return tuple(fixed_choices)


class MultipleChoiceOneTextQuestion(SaveMixin, Question):
    "A non-branch-capable question answerable with one or more of a small set of choices"
    TYPE = 'multichoiceonetext'

    class Meta:
        proxy = True

    def is_valid(self):
        if self.canned_answers.count() > 1:
            return True
        return False

    def get_canned_answer(self, choice: AnswerChoice, frame=True, **kwargs):
        """
        answer = ['list', 'of', 'answers']
        """

        if not choice:
            return self.get_optional_canned_answer()

        if len(choice) == 1:
            return self.frame_canned_answer(choice[0], frame)

        joined_answer = '{} and {}'.format(', '.join(choice[:-1]), choice[-1])
        return self.frame_canned_answer(joined_answer, frame)

    def pprint(self, value):
        return pprint_list(value['choice'])

    def get_choices(self):
        choices = tuple(self.canned_answers.order().values_list('choice', 'choice'))
        return choices

    def validate_choice(self, data):
        choice = set(data.get('choice', []))
        if self.optional and not choice:
            return True
        choices = set(self.get_choices_keys())
        if choice <= choices:
            return True
        return False


class DateRangeQuestion(NoCheckMixin, SaveMixin, Question):
    "A non-branch-capable question answerable with a daterange"

    TYPE = 'daterange'
    DEFAULT_FRAMING_TEXT = 'From {start} to {end}'

    class Meta:
        proxy = True

    def get_canned_answer(self, daterange, **kwargs):
        """
        daterange = {
            'start': date(),
            'end': date(),
        }
        """
        if not daterange:
            return self.get_optional_canned_answer()

        framing_text = self.framing_text or self.DEFAULT_FRAMING_TEXT
        return framing_text.format(**daterange)

    def pprint(self, value):
        return self.framing_text.format(**value['choice'])

    def validate_choice(self, data):
        choice = data.get('choice', {})
        if self.optional and not choice:
            return True
        if choice.get('start', False) and choice.get('end', False):
            return True
        return False


class ReasonQuestion(IsSetValidationMixin, PrimitiveTypeMixin, SaveMixin, Question):
    "A non-branch-capable question answerable with plaintext"
    TYPE = 'reason'
    has_notes = False

    class Meta:
        proxy = True


class ShortFreetextQuestion(IsSetValidationMixin, PrimitiveTypeMixin, SaveMixin, Question):
    "A non-branch-capable question answerable with plaintext"
    TYPE = 'shortfreetext'
    has_notes = False

    class Meta:
        proxy = True


class PositiveIntegerQuestion(PrimitiveTypeMixin, SaveMixin, Question):
    "A non-branch-capable question answerable with a positive integer"
    TYPE = 'positiveinteger'

    class Meta:
        proxy = True

    def validate_choice(self, data: Data) -> bool:
        answer = data.get('choice', NotSet)
        if self.optional and answer is NotSet:
            return True
        try:
            value = int(answer)
        except (ValueError, TypeError):
            return False
        return value >= 0


class DateQuestion(PrimitiveTypeMixin, SaveMixin, Question):
    """A non-branch-capable question answerable with an iso date

    Stored format: "YYYY-mm-dd"
    """
    TYPE = 'date'

    class Meta:
        proxy = True

    def validate_choice(self, data: Data) -> bool:
        answer = data.get('choice', NotSet)
        if self.optional and answer is NotSet:
            return True
        return isinstance(answer, date)


class ExternalChoiceQuestion(ChoiceValidationMixin, EEStoreMixin, SaveMixin, Question):
    """A non-branch-capable question answerable with a single choice

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
    too many for a drop down/radio field list.
    """
    TYPE = 'externalchoice'

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        answers = self.get_entries([choice])
        if not answers:
            return ''
        answer = answers[0]
        return self.frame_canned_answer(answer.name, frame)


class ExternalChoiceNotListedQuestion(NotListedMixin, EEStoreMixin, SaveMixin, Question):
    """A branch-capable question answerable with a single choice

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
    too many for a standard multiselect.

    If the user chooses "Not listed", which is a CannedAnswer, it is possible
    to branch.
    """
    TYPE = 'extchoicenotlisted'
    branching_possible = True

    class Meta:
        proxy = True

    def get_canned_answer(self, choice_dict, frame=True, **kwargs):
        """
        choice = {
            'choices': 'answer',
            'not-listed': bool()
        }
        """
        if not choice_dict:
            return self.get_optional_canned_answer()

        choice = choice_dict.get('choices', '')
        notlisted = choice_dict.get('not-listed', False)
        answer = ''

        if choice:
            answers = self.get_entries([choice])
            if answers:
                answer = self.frame_canned_answer(answers[0], frame)

        notlisted_string = ''
        if notlisted:
            canned_answer = super().get_canned_answer('not-listed', **kwargs)
            if canned_answer and canned_answer != 'not-listed':
                notlisted_string = canned_answer
            else:
                notlisted_string = 'Not found in the list'

        out = list(filter(None, (answer, notlisted_string)))
        if out:
            return mark_safe(' '.join(out))
        return mark_safe('')

    def validate_choice(self, data):
        answer = data.get('choice', {})
        if self.optional and not answer:
            return True
        choice = answer.get('choices', '')
        not_listed = answer.get('not-listed', False)
        choices = self.get_choices_keys()
        if choice in choices or not_listed:
            return True
        return False


class ExternalMultipleChoiceOneTextQuestion(EEStoreMixin, SaveMixin, Question):
    """A non-branch-capable question answerable with multiple choices

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
    too many for a standard multiselect.
    """
    TYPE = 'externalmultichoiceonetext'

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, frame=True, **kwargs):
        """
        choice = ['list', 'of', 'answers']
        """
        if not choice:
            return self.get_optional_canned_answer()

        answers = self.get_entries(choice)

        if not answers:  # Prevent 500 if the EE cache is empty
            return ''

        out = []
        for answer in answers:
            name = answer.name
            url = answer.uri
            entry = name
            if url:
                entry = print_url({'url': url, 'name': name})
            out.append(entry)

        if len(out) == 1:
            canned_answer = out[0]
        else:
            canned_answer = '{} and {}'.format(', '.join(out[:-1]), out[-1])
        canned_answer = mark_safe(canned_answer)
        return self.frame_canned_answer(canned_answer, frame)

    def validate_choice(self, data):
        choice = data.get('choice', [])
        if self.optional and not choice:
            return True
        choices = set(self.get_choices_keys())
        if choices.issuperset(choice):
            return True
        return False


class ExternalMultipleChoiceNotListedOneTextQuestion(NotListedMixin, EEStoreMixin, SaveMixin, Question):
    """A branch-capable question answerable with multiple choices

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
    too many for a standard multiselect.

    If the user chooses "Not listed", which is a CannedAnswer, it is possible
    to branch.
    """
    TYPE = 'extmultichoicenotlistedonetext'
    branching_possible = True

    class Meta:
        proxy = True

    def get_canned_answer(self, choice_dict, frame=True, **kwargs):
        """
        choice = {
            'choices': ['list', 'of', 'answers'],
            'not-listed': bool()
        }
        """
        if not choice_dict:
            return self.get_optional_canned_answer()

        choices = choice_dict.get('choices', ())
        notlisted = choice_dict.get('not-listed', False)
        answers = self.get_entries(choices)

        out = []
        for answer in answers:
            name = answer.name
            url = answer.uri
            entry = name
            if url:
                entry = print_url({'url': url, 'name': name})
            out.append(entry)

        answer = ''
        if out:
            if len(out) == 1:
                answer = out[0]
            else:
                answer = '{} and {}'.format(', '.join(out[:-1]), out[-1])
        answer = self.frame_canned_answer(answer, frame)

        notlisted_string = ''
        if notlisted:
            canned_answer = super().get_canned_answer('not-listed', **kwargs)
            if canned_answer and canned_answer != 'not-listed':
                notlisted_string = canned_answer

        out = list(filter(None, (answer, notlisted_string)))
        if out:
            return mark_safe(' '.join(out))
        return mark_safe('')

    def validate_choice(self, data):
        answer = data.get('choice', {})
        if self.optional and not answer:
            return True
        try:
            choice = set(answer.get('choices', []))
        except AttributeError:
            errormsg = 'Choice is in wrong format: pk {}, input "{}", choice {}'
            LOG.error(errormsg.format(self.pk, self.input_type, answer))
            return False
        not_listed = answer.get('not-listed', False)
        choices = set(self.get_choices_keys())
        if choice <= choices or not_listed:
            return True
        return False


class NamedURLQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question answerable with an url

    A name/title/description for the url is optional.
    """
    TYPE = 'namedurl'

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        answer = print_url(choice)
        return self.frame_canned_answer(answer, frame)

    def pprint(self, value):
        url = value['choice']['url']
        name = value['choice'].get('name', None)
        if name:
            return '{url} ({name})'.format(url=url, name=name)
        return url

    def pprint_html(self, value):
        return self.get_canned_answer(value['choice'], frame=False)

    def validate_choice(self, data):
        choice = data.get('choice', {})
        if self.optional and not choice:
            return True
        if choice.get('url', False):
            return True
        return False


class MultiNamedURLOneTextQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question answerable with several urls

    A name/title/description per url is optional.
    """
    TYPE = 'multinamedurlonetext'

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        urlpairs = []
        for pair in choice:
            urlpairs.append(print_url(pair))

        if len(urlpairs) == 1:
            joined_pairs = urlpairs[0]
        else:
            joined_pairs = '{} and {}'.format(', '.join(urlpairs[:-1]), urlpairs[-1])
        return self.frame_canned_answer(joined_pairs, frame)

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices, frame=False)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
        for choice in choices:
            url = choice.get('url', None)
            if url:
                return True
        return False


class MultiDMPTypedReasonOneTextQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question answerable several type+reason+url sets

    The url is optional.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    TYPE = 'multidmptypedreasononetext'
    DEFAULT_FRAMING_TEXT = """<dl>{% for triple in choices %}
<dt>{{ triple.type }}</dt>
<dd>Because {{ triple.reason }}</dd>
{% if triple.access_url %}<dd><a href="{{ triple.access_url }}">Access instructions</a></dd>{% endif %}
{% endfor %}
</dl>
"""

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        framing_text = self.framing_text if self.framing_text else self.DEFAULT_FRAMING_TEXT
        return mark_safe(render_from_string(framing_text, {'choices': choice}))

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
        for choice in choices:
            type_ = choice.get('type', None)
            reason = choice.get('reason', None)
            if type_ and reason:
                return True
        return False


class MultiRDACostOneTextQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question for RDA DMP Common Standard Cost

    Only title is required.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    TYPE = 'multirdacostonetext'
    DEFAULT_FRAMING_TEXT = """<dl class="answer-cost">{% for obj in choices %}
<dt>{{ obj.title }}
{% if obj.currency_code or obj.value %}
<span>{{ obj.currency_code }} {{ obj.value|default_if_none:"Unknown" }}</span>
{% endif %}
</dt>
<dd>{{ obj.description|default:"-" }}</dd>
{% endfor %}
</dl>
"""

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        framing_text = self.framing_text if self.framing_text else self.DEFAULT_FRAMING_TEXT
        return mark_safe(render_from_string(framing_text, {'choices': choice}))

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
        for choice in choices:
            if choice.get('title', None):
                return True
        return False


class StorageForecastQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question for RDA DMP Common Standard Cost

    Only title is required.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    TYPE = 'storageforecast'
    DEFAULT_FRAMING_TEXT = """<p>Storage forecast:</p>
<ul class="storage-estimate">{% for obj in choices %}
    <li>{{ obj.year }}: {{ obj.storage_estimate }} TiB, backup {{ obj.backup_percentage }}</li>
{% endfor %}</ul>
"""

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        framing_text = self.framing_text if self.framing_text else self.DEFAULT_FRAMING_TEXT
        return mark_safe(render_from_string(framing_text, {'choices': choice}))

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
        for choice in choices:
            year = choice.get('year', None)
            storage_estimate = choice.get('storage_estimate', None)
            backup_percentage = choice.get('backup_percentage', None)
            if year and storage_estimate and backup_percentage:
                return True
        return False
