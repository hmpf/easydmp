from django.urls import path

from .views import (
    CreatePlanEditorInvitationView,
    ListPlanEditorInvitationView,
    AcceptPlanEditorInvitationView,
    ResendPlanEditorInvitationView,
    RevokePlanEditorInvitationView,
    CreatePlanViewerInvitationView,
    ListPlanViewerInvitationView,
    AcceptPlanViewerInvitationView,
    ResendPlanViewerInvitationView,
    RevokePlanViewerInvitationView,
)


urlpatterns = [
    path('plan/<int:plan>/editor/', ListPlanEditorInvitationView.as_view(), name='invitation_plan_editor_list'),
    path('plan/<int:plan>/editor/new/', CreatePlanEditorInvitationView.as_view(), name='invitation_plan_editor_create'),
    path('<uuid:uuid>/plan/editor/resend/', ResendPlanEditorInvitationView.as_view(), name='invitation_plan_editor_resend'),
    path('<uuid:uuid>/plan/editor/accept/', AcceptPlanEditorInvitationView.as_view(), name='invitation_plan_editor_accept'),
    path('<uuid:uuid>/plan/editor/revoke/', RevokePlanEditorInvitationView.as_view(), name='invitation_plan_editor_revoke'),

    path('plan/<int:plan>/viewer/', ListPlanViewerInvitationView.as_view(), name='invitation_plan_viewer_list'),
    path('plan/<int:plan>/viewer/new/', CreatePlanViewerInvitationView.as_view(), name='invitation_plan_viewer_create'),
    path('<uuid:uuid>/plan/viewer/resend/', ResendPlanViewerInvitationView.as_view(), name='invitation_plan_viewer_resend'),
    path('<uuid:uuid>/plan/viewer/accept/', AcceptPlanViewerInvitationView.as_view(), name='invitation_plan_viewer_accept'),
    path('<uuid:uuid>/plan/viewer/revoke/', RevokePlanViewerInvitationView.as_view(), name='invitation_plan_viewer_revoke'),
]
