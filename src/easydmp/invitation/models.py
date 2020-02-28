import uuid
from datetime import timedelta
from enum import Enum

from django.conf import settings
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.db import models
from django.db import transaction
from django.db.models  import Q
from django.template.loader import render_to_string
from django.utils.timezone import now as utcnow

from easydmp.eventlog.utils import log_event


TTL = getattr(settings, 'EASYDMP_INVITATION_TTL', 30)
FROM_EMAIL = getattr(settings, 'EASYDMP_INVITATION_FROM_ADDRESS')


class ChoiceEnum(Enum):
    @classmethod
    def choices(cls):
        return tuple((i.name, i.value) for i in cls)


class InvitationQuerySet(models.QuerySet):

    def valid_only(self, now=None):
        now = now if now else utcnow()
        newer_than = now - timedelta(days=30)
        return self.filter(Q(sent__gte=newer_than) | Q(created__gte=newer_than))


class AbstractEmailInvitation(models.Model):
    template_name = None
    email_subject_template = None

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_address = models.EmailField()
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    sent = models.DateTimeField(blank=True, null=True)
    used = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def get_absolute_accept_url(self):
        assert hasattr(self, 'accept_viewname'), '`accept_viewname` not set on model'
        return reverse(
            self.accept_viewname,
            kwargs={'uuid': str(self.uuid)}
        )

    def is_valid(self):
        "Return whether the invitation is out of date or still valid"
        creation_date = self.created
        if self.created and self.sent:
            creation_date = max(self.created, self.sent)
        days_since_creation = utcnow() - creation_date
        if days_since_creation.days < TTL:
            return True
        return False

    @transaction.atomic
    def accept_invitation(self, user):
        self.used = utcnow()
        self.save()
        template = '{timestamp} {actor} accepted {target}'
        log_event(user, 'accept', target=self, timestamp=self.used,
                  template=template)

    @transaction.atomic
    def revoke_invitation(self, user):
        if not self.used:
            self.delete()
            template = '{timestamp} {actor} revoked unused {target}'
            log_event(user, 'revoke unused', target=self, template=template)

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

    @transaction.atomic
    def send_invitation(self, user, request=None, baseurl=None, resend=None):
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
        subject = ''.join(subject.splitlines())  # Ensure single line
        message = render_to_string(self.template_name, context)
        to_address = self.email_address

        sent = send_mail(subject, message, FROM_EMAIL, [to_address],
                         fail_silently=False)

        self.sent = utcnow()
        self.save()
        verb = 'send'
        template = '{timestamp} {actor} sent {target}'
        if resend:
            verb = 'resend'
            template = '{timestamp} {actor} resent {target}'
        log_event(user, verb, target=self, timestamp=self.sent,
                  template=template)
        return sent


class PlanInvitationQuerySet(InvitationQuerySet):

    def invitations_to_edit(self):
        invitation_type = PlanEditorInvitation.invitation_type
        return self.filter(type=invitation_type)

    def invitations_to_view(self):
        invitation_type = PlanViewerInvitation.invitation_type
        return self.filter(type=invitation_type)


class PlanInvitationManager(models.Manager):

    def get_queryset(self):
        return PlanInvitationQuerySet(self.model, using=self._db)

    def invitations_to_edit(self):
        return self.invitations_to_edit()

    def invitations_to_view(self):
        return self.invitations_to_view()


class PlanInvitation(AbstractEmailInvitation):

    class InvitationType(ChoiceEnum):
        edit = 'Edit'
        view = 'View'

    VERBOSE_INVITATION_TYPES = {
        InvitationType.edit.name: 'view and edit',
        InvitationType.view.name: 'view',
    }

    plan = models.ForeignKey('plan.Plan', on_delete=models.CASCADE)
    type = models.CharField(choices=InvitationType.choices(), max_length=4, default='view')

    objects = PlanInvitationManager()

    def __str__(self):
        return 'Plan {} Invitation: "{}" by "{}"'.format(self.type, self.plan, self.email_address)

    def logprint(self):
        return '{type}: {plan.title} #{plan.pk} to {invitee}'.format(
            type=self.__class__.__name__,
            plan=self.plan,
            invitee=self.email_address
        )

    def get_context_data(self, **context):
        data = super().get_context_data(**context)
        data['plan'] = self.plan
        data['invitation_type'] = self.type
        return data

    @property
    def verbose_invitation_type(self):
        return self.VERBOSE_INVITATION_TYPES[self.type]


class PlanEditorInvitationManager(PlanInvitationManager):

    def get_queryset(self):
        return super().get_queryset().invitations_to_edit()


class PlanViewerInvitationManager(PlanInvitationManager):

    def get_queryset(self):
        return super().get_queryset().invitations_to_view()


class PlanEditorInvitation(PlanInvitation):
    template_name = 'easydmp/invitation/plan/edit/email_message.txt'
    email_subject_template = 'easydmp/invitation/plan/edit/email_subject.txt'
    accept_viewname = 'invitation_plan_editor_accept'
    invitation_type = 'edit'

    objects = PlanEditorInvitationManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.type = 'edit'
        super().save(*args, **kwargs)

    @transaction.atomic
    def accept_invitation(self, user):
        super().accept_invitation(user)
        self.plan.add_user_to_editors(user)


class PlanViewerInvitation(PlanInvitation):
    template_name = 'easydmp/invitation/plan/view/email_message.txt'
    email_subject_template = 'easydmp/invitation/plan/view/email_subject.txt'
    accept_viewname = 'invitation_plan_viewer_accept'
    invitation_type = 'view'

    objects = PlanViewerInvitationManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.type = 'view'
        super().save(*args, **kwargs)

    @transaction.atomic
    def accept_invitation(self, user):
        super().accept_invitation(user)
        self.plan.add_user_to_viewers(user)
