from django.urls import path
from django.views.generic import RedirectView

from . import views

uuid = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
simple_id = r"[0-9]+"


urlpatterns = [
    # groups views
    path("groupes/creer/", views.CreateSupportGroupView.as_view(), name="create_group"),
    path(
        "groupes/creer/form/",
        views.PerformCreateSupportGroupView.as_view(),
        name="perform_create_group",
    ),
    path(
        "groupes/liste/", views.SupportGroupListView.as_view(), name="list_all_groups"
    ),
    path(
        "groupes/<uuid:pk>/", views.SupportGroupDetailView.as_view(), name="view_group"
    ),
    path(
        "groupes/<uuid:pk>/icalendar/",
        views.SupportGroupIcsView.as_view(),
        name="ics_group",
    ),
    path(
        "groupes/<uuid:pk>/manage/",
        RedirectView.as_view(pattern_name="manage_group"),
        name="manage_group_legacy",
    ),
    path(
        "groupes/<uuid:pk>/modifier/",
        RedirectView.as_view(pattern_name="edit_group"),
        name="edit_group_legacy",
    ),
    path(
        "groupes/<uuid:pk>/gestion/",
        views.SupportGroupManagementView.as_view(),
        name="manage_group",
    ),
    path(
        "groupes/<uuid:pk>/gestion/modifier/",
        views.ModifySupportGroupView.as_view(),
        name="edit_group",
    ),
    path(
        "groupes/<uuid:pk>/quitter/",
        views.QuitSupportGroupView.as_view(),
        name="quit_group",
    ),
    path(
        "groupes/<uuid:pk>/localisation/",
        views.ChangeGroupLocationView.as_view(),
        name="change_group_location",
    ),
    path(
        "groupes/<uuid:pk>/rejoindre/",
        views.ExternalJoinSupportGroupView.as_view(),
        name="external_join_group",
    ),
    path(
        "groupes/<uuid:pk>/impression/",
        views.RedirectToPresseroView.as_view(),
        name="redirect_to_pressero",
    ),
    path(
        "groupes/retirer_gestionnaire/<int:pk>/",
        views.RemoveManagerView.as_view(),
        name="remove_manager",
    ),
    path(
        "livrets_thematiques/",
        RedirectView.as_view(pattern_name="thematic_teams_list"),
        name="thematic_groups_list",
    ),
    path(
        "equipes-thematiques/",
        views.ThematicTeamsViews.as_view(),
        name="thematic_teams_list",
    ),
    path(
        "groupes/invitation/",
        views.InvitationConfirmationView.as_view(),
        name="invitation_confirmation",
    ),
    path(
        "groupes/inscription/",
        views.InvitationWithSubscriptionView.as_view(),
        name="invitation_with_subscription_confirmation",
    ),
    path(
        "groupes/invitation/abus/",
        views.InvitationAbuseReportingView.as_view(),
        name="report_invitation_abuse",
    ),
]
