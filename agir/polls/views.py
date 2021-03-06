from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.contrib import messages
from django.utils.translation import ugettext as _

from agir.authentication.view_mixins import SoftLoginRequiredMixin
from agir.people.models import Person
from .forms import PollParticipationForm
from .models import Poll, PollChoice

__all__ = ["PollParticipationView", "PollConfirmationView", "PollFinishedView"]


class PollParticipationView(SoftLoginRequiredMixin, SingleObjectMixin, FormView):
    template_name = "polls/detail.html"
    context_object_name = "poll"
    form_class = PollParticipationForm

    def get_queryset(self):
        # use get queryset because timezone.now must be evaluated each time
        return Poll.objects.filter(start__lt=timezone.now())

    def get_success_url(self):
        return reverse_lazy("participate_poll", args=[self.object.pk])

    def get_form_kwargs(self):
        return {"poll": self.object, **super().get_form_kwargs()}

    def get_context_data(self, **kwargs):
        poll_choice = PollChoice.objects.filter(
            person=self.request.user.person, poll=self.object
        ).first()
        return super().get_context_data(
            already_voted=(poll_choice is not None),
            anonymous_id=(poll_choice is not None and poll_choice.anonymous_id),
            **kwargs
        )

    def get(self, *args, **kwargs):
        self.object = self.get_object()
        if (
            self.object.end < timezone.now()
            and PollChoice.objects.filter(
                person=self.request.user.person, poll=self.object
            ).first()
            is None
        ):
            return redirect("finished_poll")

        if (
            self.object.rules.get("require_verified")
            and self.request.user.person.contact_phone_status
            != Person.CONTACT_PHONE_VERIFIED
        ):
            return redirect_to_login(
                self.request.get_full_path(), reverse_lazy("send_validation_sms")
            )

        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        if (
            self.object.rules.get("require_verified")
            and self.request.user.person.contact_phone_status
            != Person.CONTACT_PHONE_VERIFIED
        ):
            raise PermissionDenied(
                "Vous devez avoir vérifié votre compte pour participer."
            )
        if self.request.user.person.created > self.object.start:
            raise PermissionDenied(
                "Vous vous êtes inscrit⋅e trop récemment pour participer."
            )
        if PollChoice.objects.filter(
            person=self.request.user.person, poll=self.object
        ).exists():
            raise PermissionDenied("Vous avez déjà participé !")

        return super().post(*args, **kwargs)

    def form_valid(self, form):
        try:
            form.make_choice(self.request.user)
        except IntegrityError:  # there probably has been a race condition when POSTing twice
            return HttpResponseRedirect(self.get_success_url())

        messages.add_message(
            self.request,
            messages.SUCCESS,
            _(
                "Votre choix a bien été pris en compte. Merci d'avoir participé à cette consultation !"
            ),
        )
        return super().form_valid(form)


class PollConfirmationView(TemplateView):
    template_name = "polls/confirmation.html"


class PollFinishedView(TemplateView):
    template_name = "polls/finished.html"
