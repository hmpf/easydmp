import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.db import models
from django.template.loader import render_to_string
from django.utils.timezone import now as utcnow


TTL = getattr(settings, 'EASYDMP_INVITATION_TTL', 30)
FROM_EMAIL = getattr(settings, 'EASYDMP_INVITATION_FROM_ADDRESS')


class AbstractEmailInvitation(models.Model):
    template_name = None
    email_subject_template = None

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_address = models.EmailField()
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    sent = models.DateTimeField(blank=True, null=True)
    used = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def get_absolute_accept_url(self):
        return reverse('invitation_plan_editor_accept',kwargs={'uuid':
                                                               str(self.uuid)})

    def is_valid(self):
        "Return whether the invitation is out of date or still valid"
        creation_date = self.created
        if self.created and self.sent:
            creation_date = max(self.created, self.sent)
        days_since_creation = utcnow() - creation_date
        if days_since_creation.days < TTL:
            return True
        return False

    def accept_invitation(self, user):
        self.used = utcnow()
        self.save()

    def revoke_invitation(self):
        if not self.used:
            self.delete()

    def get_context_data(self, **context):
        data = {
            'invitation': self,
            'uuid': self.uuid,
            'email_address': self.email_address,
            'invited_by': self.invited_by,
            'valid_until': self.created + timedelta(TTL),
        }
        data.update(**context)
        return data

    def send_invitation(self, request=None, baseurl=None):
        """Create and send an email with an invitation link

        Either `request` (a HttpRequest`) or a `baseurl` is needed to generate
        an absolute uri for the invitation link.
        """
        # Ensure that template and subject is set
        if None in (self.template_name, self.email_subject_template):
            raise NotImplemented
        # Create an absolute uri to the invitation accept view
        link = self.get_absolute_accept_url()
        if request is not None:
            link = request.build_absolute_uri(link)
        elif baseurl is not None:
            link = baseurl + link

        context = self.get_context_data(link=link)
        subject = render_to_string(self.email_subject_template, context)
        subject = ''.join(subject.splitlines()) #  Ensure single line
        message = render_to_string(self.template_name, context)
        to_address = self.email_address

        sent = send_mail(subject, message, FROM_EMAIL, [to_address],
                          fail_silently=False)

        self.sent = utcnow()
        self.save()
        return sent


class PlanEditorInvitation(AbstractEmailInvitation):
    template_name = 'easydmp/invitation/email/plan/message.txt'
    email_subject_template = 'easydmp/invitation/email/plan/subject.txt'

    plan = models.ForeignKey('plan.Plan')

    def accept_invitation(self, user):
        super().accept_invitation(user)
        self.plan.add_user_to_editor_group(user)

    def get_context_data(self, **context):
        data = super().get_context_data(**context)
        data['plan'] = self.plan
        return data
