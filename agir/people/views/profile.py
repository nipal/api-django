from urllib.parse import urlencode
from uuid import UUID

from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import UpdateView, TemplateView, FormView, RedirectView
from django.views.generic.edit import DeleteView

from agir.authentication.subscription import merge_account_token_generator
from agir.authentication.utils import hard_login
from agir.authentication.view_mixins import (
    SoftLoginRequiredMixin,
    HardLoginRequiredMixin,
)
from agir.people.actions.management import merge_persons
from agir.people.forms import (
    Person,
    AddEmailMergeAccountForm,
    VolunteerForm,
    ParticipationForm,
    InformationConfidentialityForm,
    BecomeInsoumiseForm,
)
from agir.people.forms.profile import (
    InformationPersonalForm,
    InformationContactForm,
    ActivityAblebilityForm,
    PreferencesForm,
)
from agir.people.models import PersonEmail
from agir.people.views.mixins import (
    NavsProfileMixin,
    NAVS_PROFILE_PREFERENCES,
    NAVS_PROFILE_PARTICIPATION,
    NAVS_PROFILE_IDENTITY,
    NAVS_PROFILE_CONTACT,
    NAVS_PROFILE_SKILLS,
    NAVS_PROFILE_ACT,
    NAVS_PROFILE_CONFIDENTIALITY,
    NAVS_PROFILE_BECOME_INSOUMISE,
)


class DeleteAccountView(HardLoginRequiredMixin, NavsProfileMixin, DeleteView):
    template_name = "people/delete_account.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_CONFIDENTIALITY, **kwargs)

    def get_success_url(self):
        return reverse("delete_account_success")

    def get_object(self, queryset=None):
        return self.request.user.person

    def delete(self, request, *args, **kwargs):
        messages.add_message(
            self.request, messages.SUCCESS, "Votre compte a bien été supprimé !"
        )
        response = super().delete(request, *args, **kwargs)
        logout(self.request)

        return response


class ContactPreferencesView(SoftLoginRequiredMixin, NavsProfileMixin, UpdateView):
    template_name = "people/profile_default.html"
    form_class = PreferencesForm
    success_url = reverse_lazy("contact_preferences")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_PREFERENCES, **kwargs)

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person

    def form_valid(self, form):
        res = super().form_valid(form)

        if getattr(form, "no_mail", False):
            messages.add_message(
                self.request,
                messages.INFO,
                "Vous êtes maintenant désinscrit⋅e de toutes les lettres d'information de la France insoumise.",
            )
        else:
            messages.add_message(
                self.request,
                messages.SUCCESS,
                "Vos préférences ont bien été enregistrées !",
            )

        return res


class ParticipationView(SoftLoginRequiredMixin, NavsProfileMixin, UpdateView):
    template_name = "people/profile_default.html"
    form_class = ParticipationForm
    success_url = reverse_lazy("participation")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_PARTICIPATION, **kwargs)

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class BecomeInsoumiseView(SoftLoginRequiredMixin, NavsProfileMixin, UpdateView):
    template_name = "people/profile_default.html"
    form_class = BecomeInsoumiseForm
    success_url = reverse_lazy("personal_informations")

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            tab_code=NAVS_PROFILE_BECOME_INSOUMISE, **kwargs
        )

    def form_valid(self, form):
        self.object.subscribed = True
        self.object.subscribed_sms = True
        self.object.group_notifications = True
        self.object.event_notifications = True
        return super().form_valid(form)

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class PersonalInformationsView(SoftLoginRequiredMixin, NavsProfileMixin, UpdateView):
    template_name = "people/profile_default.html"
    form_class = InformationPersonalForm
    success_url = reverse_lazy("personal_informations")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_IDENTITY, **kwargs)

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class ChangeProfileContactView(SoftLoginRequiredMixin, NavsProfileMixin, UpdateView):
    template_name = "people/information_contact.html"
    form_class = InformationContactForm
    success_url = reverse_lazy("profile_contact")

    def get_information_contact_form(self):
        kwargs = {}

        if self.request.method in ("POST", "PUT"):
            kwargs.update({"data": self.request.POST, "files": self.request.FILES})

        return InformationContactForm(**kwargs)

    def get_context_data(self, **kwargs):
        emails = self.object.emails.all()

        return super().get_context_data(
            person=self.object,
            emails=emails,
            can_delete=len(emails) > 1,
            tab_code=NAVS_PROFILE_CONTACT,
            **kwargs,
        )

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class AddEmailMergeAccountView(SoftLoginRequiredMixin, NavsProfileMixin, FormView):
    template_name = "people/account_management.html"
    form_class = AddEmailMergeAccountForm
    success_url = reverse_lazy("confirm_merge_account_sent")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_CONTACT, **kwargs)

    def get_form(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"data": self.request.POST, "files": self.request.FILES})

        return AddEmailMergeAccountForm(user_pk=self.request.user.person.pk, **kwargs)

    def form_valid(self, form):
        (email, is_merging) = form.send_confirmation()
        if not email:
            return self.form_invalid(form)
        self.success_url += "?" + urlencode({"email": email, "is_merging": is_merging})
        return super().form_valid(form)


class ConfirmMergeAccountView(View):
    """
    Fusionne 2 compte.

    Cette vue peut être atteinte depuis n'importe quel navigateur donc pas besoin d'être connecté.
    Elle vérifie l'integriter du pk_merge + pk_requester + token
    Elle redirige vers la vue `dashboard` en cas de succès
    En cas de problème vérification du token une page est affiché explicant le problème: `invalid`, `expiration`
    """

    success_url = reverse_lazy("dashboard")
    error_template = "people/confirmation_mail_change_error.html"
    error_messages = {
        "invalid": "Quelque chose d'étrange c'est produit",
        "expired": "Il semble que le lien soit expiré.",
        "same_person": "Il semble que l'opération de fusion à déjà été effectué.",
    }

    def error_page(self, key_error):
        return TemplateResponse(
            self.request,
            [self.error_template],
            context={"message": self.error_messages[key_error]},
        )

    def get(self, request, **kwargs):
        pk_requester = request.GET.get("pk_requester")
        pk_merge = request.GET.get("pk_merge")
        token = request.GET.get("token")

        # Check part
        if not pk_requester or not pk_merge or not token:
            return self.error_page(key_error="invalid")

        try:
            pk_requester = UUID(pk_requester)
            pk_merge = UUID(pk_merge)
        except ValueError:
            return self.error_page(key_error="invalid")

        try:
            person_requester = Person.objects.get(pk=pk_requester)
            person_merge = Person.objects.get(pk=pk_merge)
        except Person.DoesNotExist:
            return self.error_page(key_error="invalid")

        if merge_account_token_generator.is_expired(token):
            return self.error_page(key_error="expired")

        params = {"pk_requester": str(pk_requester), "pk_merge": str(pk_merge)}
        if not merge_account_token_generator.check_token(token, **params):
            return self.error_page(key_error="invalid")

        try:
            merge_persons(person_requester, person_merge)
        except ValueError:
            return self.error_page(key_error="same_person")

        # success part
        hard_login(request, person_requester)
        messages.add_message(
            self.request,
            messages.SUCCESS,
            "Votre fusion de compte à été effectué avec succès",
        )

        return HttpResponseRedirect(self.success_url)


class SendConfirmationMergeAccountView(HardLoginRequiredMixin, TemplateView):
    template_merge = "people/confirmation_change_mail_merge_account_sent.html"
    template_name = "people/confirmation_change_mail_merge_account_sent.html"

    def get(self, request):
        self.email = request.GET.get("email")
        self.is_merging = True if request.GET.get("is_merging") == "True" else False
        return super().get(request)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            email1=self.email, email2=self.email, is_merging=self.is_merging, **kwargs
        )


class ChangePrimaryEmailView(SoftLoginRequiredMixin, RedirectView):
    url = reverse_lazy("profile_contact")

    def get(self, request, *args, **kwargs):
        self.person = request.user.person
        email = PersonEmail.objects.get(pk=self.kwargs["pk"])
        self.person.set_primary_email(email)

        return super().get(request, *args, **kwargs)


class SkillsView(SoftLoginRequiredMixin, NavsProfileMixin, UpdateView):
    template_name = "people/profile_default.html"
    form_class = ActivityAblebilityForm
    success_url = reverse_lazy("skills")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_SKILLS, **kwargs)

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class PesonalDataView(SoftLoginRequiredMixin, NavsProfileMixin, FormView):
    template_name = "people/profile_default.html"
    form_class = InformationConfidentialityForm
    success_url = reverse_lazy("personal_data")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_CONFIDENTIALITY, **kwargs)

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class VolunteerView(SoftLoginRequiredMixin, NavsProfileMixin, UpdateView):
    template_name = "people/volunteer.html"
    form_class = VolunteerForm
    success_url = reverse_lazy("voluteer")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tab_code=NAVS_PROFILE_ACT)

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person
