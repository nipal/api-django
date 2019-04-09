from django.urls import path, reverse_lazy
from django.views.generic import TemplateView, RedirectView

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
    path(
        "supprimer/",
        views.RedirectView.as_view(url=reverse_lazy("delete_account")),
        name="delete_account_old",
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
        "profil/", views.RedirectView.as_view(url=reverse_lazy("personal_information"))
    ),
    path(
        "profil/identite/",
        views.PersonalInformationsView.as_view(),
        name="personal_information",
    ),
    path("profil/competences", views.SkillsView.as_view(), name="skills"),
    path("profil/engagement/", views.VolunteerView.as_view(), name="voluteer"),
    path(
        "message_preferences/",
        RedirectView.as_view(url=reverse_lazy("contact")),
        name="preferences",
    ),
    path(
        "profil/rejoindre/",
        views.BecomeInsoumiseView.as_view(),
        name="become_insoumise",
    ),
    path("profil/contact/", views.ContactView.as_view(), name="contact"),
    path(
        "profil/contact/adresses/",
        views.AddEmailMergeAccountView.as_view(),
        name="manage_account",
    ),
    path(
        "profil/contact/adresses/confirmer",
        views.ConfirmMergeAccountView.as_view(),
        name="confirm_merge_account",
    ),
    path(
        "profil/contact/adresses/<int:pk>/principale/",
        views.ChangePrimaryEmailView.as_view(),
        name="change_primary_mail",
    ),
    path(
        "profil/contact/adresses/fusion_attente/",
        views.SendConfirmationMergeAccountView.as_view(),
        name="confirm_merge_account_sent",
    ),
    path(
        "profil/contact/adresses/<int:pk>/supprimer/",
        views.DeleteEmailAddressView.as_view(),
        name="delete_email",
    ),
    path(
        "profil/adresses/confirmer",
        views.ConfirmChangeMailView.as_view(),
        name="confirm_change_mail",
    ),
    path(
        "profil/confidentialite/", views.PesonalDataView.as_view(), name="personal_data"
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
        "formulaires/<slug:slug>/reponses/",
        views.PeopleFormSubmissionsView.as_view(),
        name="person_form_submissions",
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
