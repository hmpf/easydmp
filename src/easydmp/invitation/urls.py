from django.conf.urls import url

from .views import (
    CreatePlanEditorInvitationView,
    ListPlanEditorInvitationView,
    AcceptPlanEditorInvitationView,
    ResendPlanEditorInvitationView,
)


PLAN_RE = r'(?P<plan>\d+)'
UUID_RE = r'(?P<uuid>[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12})'

urlpatterns = [
    url(r'plan/' + PLAN_RE + r'/editor/$', ListPlanEditorInvitationView.as_view(), name='invitation_plan_editor_list'),
    url(r'plan/' + PLAN_RE + r'/editor/new/$', CreatePlanEditorInvitationView.as_view(), name='invitation_plan_editor_create'),
    url(UUID_RE + r'/plan/editor/resend/$', ResendPlanEditorInvitationView.as_view(), name='invitation_plan_editor_resend'),
    url(UUID_RE + r'/plan/editor/accept/$', AcceptPlanEditorInvitationView.as_view(), name='invitation_plan_editor_accept'),
]
