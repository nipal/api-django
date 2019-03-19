from django.urls import reverse_lazy
from django.views.generic import UpdateView, TemplateView

from agir.authentication.view_mixins import SoftLoginRequiredMixin
from agir.front.view_mixins import SimpleOpengraphMixin
from agir.people.actions.management import merge_persons
from agir.people.forms import ProfileForm, Person
from agir.people.forms.profile import (
    InformationPersonalForm,
    InformationContactForm,
    ActivityAblebilityForm,
)


class ChangeProfileView(SoftLoginRequiredMixin, UpdateView):
    template_name = "people/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("confirmation_profile")

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


# InformationPersonalForm
# InformationContactForm
# ActivityAblebilityForm


class ChangeProfilePersoView(SoftLoginRequiredMixin, UpdateView):
    template_name = "people/profile.html"
    form_class = InformationPersonalForm
    success_url = reverse_lazy("confirmation_profile")

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class ChangeProfileContactView(SoftLoginRequiredMixin, UpdateView):
    template_name = "people/profile.html"
    form_class = InformationContactForm
    success_url = reverse_lazy("confirmation_profile")

    # J'ai besoin de connaitre l'email du user qui effectue la requette.
    # de l'email du compte a mergé, et c'esdt tout.
    def post(self, request):
        email_target = request.POST.get("email_merge_target")
        email_from = self.request.user.person.email

        people_stay = Person.objects.get(email=email_from)
        people_to_merge = Person.objects.get(email=email_target)

        ok = None
        if people_stay == people_to_merge:
            ok = "yes it-easy*"
        elif people_stay.email == people_to_merge.email:
            ok = "we can deal with it"
        elif str(people_stay.email) == str(people_to_merge.email):
            ok = "all right ill do like that"

        ok = ok
        debug = "ok"

        merge_persons(people_stay, people_to_merge)

    # Processus de validation pour la fusion de compte
    #   Les cas d'erreur formulaire:
    #       - l'adresse n'existe pas
    #       - l'adresse nous appartient déjà

    #   Sénario problematique:
    #       - quelqu'un envoie 2 fois le mail
    #       - le mail est 2 fois accepter

    #   Processe de validation:
    #       - On entre le mail de la persone en question
    #       - page de confirmation ??
    #       - Un mail lui est envoyer a l'individue selectioné
    #           - on explique en quoi consiste une fusion de compte
    #           - un lien lui est fourni avec email_from, email_to, token
    #       - il clique et arrive sur une page qui l'ibforme que l'operqtion à été effectué avec succès

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class ChangeProfileSkillsView(SoftLoginRequiredMixin, UpdateView):
    template_name = "people/profile.html"
    form_class = ActivityAblebilityForm
    success_url = reverse_lazy("confirmation_profile")

    def get_object(self, queryset=None):
        """Get the current user as the view object"""
        return self.request.user.person


class ChangeProfileConfirmationView(SimpleOpengraphMixin, TemplateView):
    template_name = "people/confirmation_profile.html"
