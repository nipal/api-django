from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    # people views
    path("desinscription/", views.UnsubscribeView.as_view(), name="unsubscribe"),
    path("desabonnement/", views.UnsubscribeView.as_view(), name="unsubscribe"),
    path(
        "desabonnement/succes/",
        TemplateView.as_view(template_name="people/unsubscribe_success.html"),
        name="unsubscribe_success",
    ),
    path("profil/supprimer/", views.DeleteAccountView.as_view(), name="delete_account"),
    path(
        "supprimer/succes",
        TemplateView.as_view(template_name="people/delete_account_success.html"),
        name="delete_account_success",
    ),
    path("inscription/", views.SimpleSubscriptionView.as_view(), name="subscription"),
    path(
        "inscription/etranger/",
        views.OverseasSubscriptionView.as_view(),
        name="subscription_overseas",
    ),
    path(
        "inscription/attente/",
        views.ConfirmationMailSentView.as_view(),
        name="subscription_mail_sent",
    ),
    path(
        "inscription/confirmer/",
        views.ConfirmSubscriptionView.as_view(),
        name="subscription_confirm",
    ),
    path(
        "profil/identite/",
        views.ChangeProfilePersoView.as_view(),
        name="profile_personal",
    ),
    path(
        "profil/competence",
        views.ChangeProfileSkillsView.as_view(),
        name="profile_skills",
    ),
    path(
        "profil/engagement/", views.VolunteerView.as_view(), name="profile_involvement"
    ),
    path(
        "profil/preference/",
        views.ChangeProfilePreference.as_view(),
        name="profile_preferences",
    ),
    path(
        "profil/participation/",
        views.ChangeProfileParticipation.as_view(),
        name="profile_participation",
    ),
    path(
        "profil/rejoindre/", views.ChangeProfileRejoin.as_view(), name="profile_rejoin"
    ),
    path(
        "profil/contact/",
        views.ChangeProfileContactView.as_view(),
        name="profile_contact",
    ),
    path(
        "profil/contact/adresses/",
        views.AddEmailMergeAccountView.as_view(),
        name="manage_account",
    ),
    path(
        "profil/contact/adresses/confirmer",
        views.ConfirmMergeAccount.as_view(),
        name="confirm_merge_account",
    ),
    path(
        "profil/contact/adresses/<int:pk>/principale/",
        views.ChangePrimaryEmail.as_view(),
        name="change_mail",
    ),
    path(
        "profil/contact/adresses/fusion_attente/",
        views.SendConfirmationMergeAccount.as_view(),
        name="confirm_merge_account_sent",
    ),
    path(
        "profil/contact/adresses/<int:pk>/supprimer/",
        views.DeleteEmailAddressView.as_view(),
        name="delete_email",
    ),
    path(
        "profil/adresses/confirmer",
        views.ConfirmChangeMail.as_view(),
        name="confirm_change_mail",
    ),
    path(
        "profil/confidentialite/",
        views.ChangeProfilePrivacy.as_view(),
        name="profile_privacy",
    ),
    path("agir/", views.VolunteerView.as_view(), name="volunteer"),
    path(
        "formulaires/<slug:slug>/",
        views.PeopleFormView.as_view(),
        name="view_person_form",
    ),
    path(
        "formulaires/<slug:slug>/edit/<pk>",
        views.PeopleFormEditSubmissionView.as_view(),
        name="edit_person_form_submission",
    ),
    path(
        "formulaires/<slug:slug>/confirmation/",
        views.PeopleFormConfirmationView.as_view(),
        name="person_form_confirmation",
    ),
    path(
        "telephone/sms",
        views.SendValidationSMSView.as_view(),
        name="send_validation_sms",
    ),
    path(
        "telephone/validation",
        views.CodeValidationView.as_view(),
        name="sms_code_validation",
    ),
    # dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
]
