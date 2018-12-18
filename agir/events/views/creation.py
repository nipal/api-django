import json

from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse

from django.utils.safestring import mark_safe
from django.views.generic import TemplateView
from django.views.generic.edit import FormMixin, ProcessFormView

from agir.authentication.view_mixins import SoftLoginRequiredMixin
from agir.events.actions.legal import QUESTIONS
from agir.events.forms import EventForm
from agir.events.models import EventSubtype, Event


class CreateEventView(SoftLoginRequiredMixin, TemplateView):
    template_name = "events/create.html"

    def get_context_data(self, **kwargs):
        person = self.request.user.person

        groups = [
            {"id": str(m.supportgroup.pk), "name": m.supportgroup.name}
            for m in person.memberships.filter(
                supportgroup__published=True, is_manager=True
            )
        ]

        initial = {"email": person.email}

        if person.contact_phone:
            initial["phone"] = person.contact_phone.as_e164

        if person.first_name and person.last_name:
            initial["name"] = "{} {}".format(person.first_name, person.last_name)

        initial_group = self.request.GET.get("group")
        if initial_group in [g["id"] for g in groups]:
            initial["organizerGroup"] = initial_group

        subtype_queryset = EventSubtype.objects.filter(
            visibility=EventSubtype.VISIBILITY_ALL
        )

        subtype_label = self.request.GET.get("subtype")
        if subtype_label:
            try:
                subtype = subtype_queryset.get(label=subtype_label)
                initial["subtype"] = subtype.label
            except EventSubtype.DoesNotExist:
                pass

        types = [
            {
                "id": id,
                "label": str(label),
                "description": str(EventSubtype.TYPE_DESCRIPTION[id]),
            }
            for id, label in EventSubtype.TYPE_CHOICES
        ]

        subtypes = [
            {"id": s.id, "label": s.label, "description": s.description, "type": s.type}
            for s in subtype_queryset
        ]

        questions = QUESTIONS

        return super().get_context_data(
            props=mark_safe(
                json.dumps(
                    {
                        "initial": initial,
                        "groups": groups,
                        "types": types,
                        "subtypes": subtypes,
                        "questions": questions,
                    }
                )
            ),
            **kwargs
        )


class PerformCreateEventView(SoftLoginRequiredMixin, FormMixin, ProcessFormView):
    model = Event
    form_class = EventForm

    def get_form_kwargs(self):
        """Add user person profile to the form kwargs"""

        kwargs = super().get_form_kwargs()

        person = self.request.user.person
        kwargs["person"] = person
        return kwargs

    def form_invalid(self, form):
        return JsonResponse({"errors": form.errors}, status=400)

    def form_valid(self, form):
        messages.add_message(
            request=self.request,
            level=messages.SUCCESS,
            message="Votre événement a été correctement créé.",
        )

        form.save()

        return JsonResponse(
            {
                "status": "OK",
                "id": form.instance.id,
                "url": reverse("view_event", args=[form.instance.id]),
            }
        )
