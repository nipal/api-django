import reversion
from django.contrib import messages
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils.translation import ugettext as _
from django.views import View
from django.views.generic import UpdateView, TemplateView, DetailView, CreateView
from django.views.generic.detail import SingleObjectMixin

from agir.authentication.view_mixins import HardLoginRequiredMixin
from agir.donations.actions import (
    summary,
    history,
    validate_action,
    group_can_handle_allocation,
    can_edit,
    EDITABLE_STATUSES,
    get_current_action,
    find_or_create_person_from_payment,
)
from agir.donations.apps import DonsConfig
from agir.donations.base_views import BaseAskAmountView, BasePersonalInformationView
from agir.donations.forms import (
    DocumentOnCreationFormset,
    DocumentHelper,
    SpendingRequestCreationForm,
    DocumentForm,
)
from agir.groups.models import SupportGroup, Membership
from agir.payments import payment_modes
from agir.payments.models import Payment
from agir.people.models import Person
from . import forms
from .models import SpendingRequest, Operation, Document
from .tasks import send_donation_email

__all__ = ("AskAmountView", "PersonalInformationView")


DONATION_SESSION_NAMESPACE = "_donation_"


class AskAmountView(BaseAskAmountView):
    meta_title = "Je donne à la France insoumise"
    meta_description = (
        "Pour financer les dépenses liées à l’organisation d’événements, à l’achat de matériel, au"
        "fonctionnement du site, etc., nous avons besoin du soutien financier de chacun.e d’entre vous !"
    )
    meta_type = "website"

    form_class = forms.AllocationDonationForm
    template_name = "donations/ask_amount.html"
    success_url = reverse_lazy("donation_information")
    session_namespace = DONATION_SESSION_NAMESPACE

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["group_id"] = self.request.GET.get("group")
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        # use int to floor down the value as well as converting to an int
        allocation = int(form.cleaned_data.get("allocation", 0) * 100)
        self.data_to_persist["allocation"] = allocation
        self.data_to_persist["group_id"] = form.group and str(form.group.pk)
        return super().form_valid(form)


class PersonalInformationView(BasePersonalInformationView):
    form_class = forms.AllocationDonorForm
    template_name = "donations/personal_information.html"
    enable_allocations = True
    payment_mode = payment_modes.DEFAULT_MODE
    payment_type = DonsConfig.PAYMENT_TYPE
    session_namespace = DONATION_SESSION_NAMESPACE
    base_redirect_url = "donation_amount"

    def get_context_data(self, **kwargs):
        amount = self.persistent_data["amount"]
        allocation = self.persistent_data.get("allocation", 0)
        group_id = self.persistent_data.get("group_id", None)
        group_name = None

        if group_id:
            try:
                group_name = SupportGroup.objects.get(pk=group_id).name
            except SupportGroup.DoesNotExist:
                pass

        return super().get_context_data(
            allocation=allocation,
            national=amount - allocation,
            group_name=group_name,
            **kwargs
        )

    def get_payment_meta(self, form):
        meta = super().get_payment_meta(form)

        allocation = form.cleaned_data["allocation"]
        group = form.cleaned_data["group"]

        if allocation and group:
            meta["allocation"] = allocation
            meta["group_id"] = str(group.pk)

        return meta


class ReturnView(TemplateView):
    template_name = "donations/thanks.html"


def notification_listener(payment):
    if payment.status == Payment.STATUS_COMPLETED:
        find_or_create_person_from_payment(payment)
        send_donation_email.delay(payment.person.pk)

        if (
            payment.meta.get("allocation") is not None
            and payment.meta.get("group_id") is not None
        ):
            Operation.objects.create(
                payment=payment,
                group_id=payment.meta.get("group_id"),
                amount=payment.meta.get("allocation"),
            )


class CreateSpendingRequestView(HardLoginRequiredMixin, TemplateView):
    template_name = "donations/create_spending_request.html"

    def is_authorized(self, request):
        return (
            super().is_authorized(request)
            and group_can_handle_allocation(self.group)
            and Membership.objects.filter(
                person=request.user.person, supportgroup=self.group, is_manager=True
            ).exists()
        )

    def dispatch(self, request, *args, **kwargs):
        try:
            self.group = SupportGroup.objects.get(pk=self.kwargs["group_id"])
        except SupportGroup.DoesNotExist:
            raise Http404()

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.spending_request = None
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.spending_request = None
        spending_request_form, document_formset = self.get_forms()
        if spending_request_form.is_valid() and document_formset.is_valid():
            return self.form_valid(spending_request_form, document_formset)
        return self.form_invalid(spending_request_form, document_formset)

    def form_valid(self, spending_request_form, document_formset):
        with reversion.create_revision():
            reversion.set_user(self.request.user)
            reversion.set_comment("Création de la demande de dépense")

            self.spending_request = spending_request_form.save()
            document_formset.save()

        return HttpResponseRedirect(
            reverse("manage_spending_request", kwargs={"pk": self.spending_request.pk})
        )

    def form_invalid(self, spending_request_form, document_formset):
        return self.render_to_response(
            self.get_context_data(
                spending_request_form=spending_request_form,
                document_formset=document_formset,
            )
        )

    def get_forms(self):
        kwargs = {}
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"data": self.request.POST, "files": self.request.FILES})

        spending_request_form = SpendingRequestCreationForm(
            group=get_object_or_404(
                SupportGroup.objects.active(), id=self.kwargs["group_id"]
            ),
            user=self.request.user,
            **kwargs
        )
        document_formset = DocumentOnCreationFormset(
            instance=spending_request_form.instance, **kwargs
        )

        return spending_request_form, document_formset

    def get_context_data(self, **kwargs):
        if "spending_request_form" not in kwargs or "document_formset" not in kwargs:
            spending_request, document_formset = self.get_forms()
            kwargs["spending_request_form"] = spending_request
            kwargs["document_formset"] = document_formset
        kwargs["document_helper"] = DocumentHelper()
        return super().get_context_data(**kwargs)


class IsGroupManagerMixin(HardLoginRequiredMixin):
    spending_request_pk_field = "pk"

    def is_authorized(self, request):
        return super().is_authorized(request) and self.get_membership(request)

    def get_membership(self, request):
        return Membership.objects.filter(
            person=request.user.person,
            supportgroup__spending_request__id=self.kwargs[
                self.spending_request_pk_field
            ],
        )


class CanEdit(IsGroupManagerMixin):
    def get_membership(self, request):
        return (
            super()
            .get_membership(request)
            .filter(supportgroup__spending_request__status__in=EDITABLE_STATUSES)
        )


class ManageSpendingRequestView(IsGroupManagerMixin, DetailView):
    model = SpendingRequest
    template_name = "donations/manage_spending_request.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            supportgroup=self.object.group,
            documents=self.object.documents.filter(deleted=False),
            can_edit=can_edit(self.object),
            action=get_current_action(self.object, self.request.user),
            summary=summary(self.object),
            history=history(self.object),
            **kwargs
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        validate = self.request.POST.get("validate")

        if validate != self.object.status or not validate_action(
            self.object, request.user
        ):
            messages.add_message(
                request,
                messages.WARNING,
                _("Il y a eu un problème, veuillez réessayer."),
            )
            return self.render_to_response(self.get_context_data())

        return HttpResponseRedirect(
            reverse("manage_spending_request", args=(self.object.pk,))
        )


class EditSpendingRequestView(IsGroupManagerMixin, UpdateView):
    model = SpendingRequest
    form_class = forms.SpendingRequestEditForm
    template_name = "donations/edit_spending_request.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("manage_spending_request", args=(self.object.pk,))

    def render_to_response(self, context, **response_kwargs):
        if self.object.status in SpendingRequest.STATUS_EDITION_MESSAGES:
            messages.add_message(
                self.request,
                messages.WARNING,
                SpendingRequest.STATUS_EDITION_MESSAGES[self.object.status],
            )
        return super().render_to_response(context, **response_kwargs)


class CreateDocument(IsGroupManagerMixin, CreateView):
    model = Document
    form_class = DocumentForm
    spending_request_pk_field = "spending_request_id"
    template_name = "donations/create_document.html"

    def get(self, *args, **kwargs):
        self.spending_request = get_object_or_404(
            SpendingRequest, pk=self.kwargs["spending_request_id"]
        )
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.spending_request = get_object_or_404(
            SpendingRequest, pk=self.kwargs["spending_request_id"]
        )
        return super().post(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["spending_request"] = self.spending_request
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("manage_spending_request", args=(self.spending_request.pk,))

    def render_to_response(self, context, **response_kwargs):
        if self.spending_request.status in SpendingRequest.STATUS_EDITION_MESSAGES:
            messages.add_message(
                self.request,
                messages.WARNING,
                SpendingRequest.STATUS_EDITION_MESSAGES[self.spending_request.status],
            )
        return super().render_to_response(context, **response_kwargs)


class EditDocument(IsGroupManagerMixin, UpdateView):
    model = Document
    queryset = Document.objects.filter(deleted=False)
    form_class = DocumentForm
    spending_request_pk_field = "spending_request_id"
    template_name = "donations/edit_document.html"

    def get(self, *args, **kwargs):
        self.spending_request = get_object_or_404(
            SpendingRequest,
            pk=self.kwargs["spending_request_id"],
            document__pk=self.kwargs["pk"],
        )

        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.spending_request = get_object_or_404(
            SpendingRequest,
            pk=self.kwargs["spending_request_id"],
            document__pk=self.kwargs["pk"],
        )
        return super().post(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("manage_spending_request", args=(self.spending_request.pk,))

    def render_to_response(self, context, **response_kwargs):
        if self.spending_request.status in SpendingRequest.STATUS_EDITION_MESSAGES:
            messages.add_message(
                self.request,
                messages.WARNING,
                SpendingRequest.STATUS_EDITION_MESSAGES[self.object.request.status],
            )

        return super().render_to_response(context, **response_kwargs)


class DeleteDocument(IsGroupManagerMixin, SingleObjectMixin, View):
    model = Document
    spending_request_pk_field = "spending_request_id"

    def post(self, request, *args, **kwargs):
        self.spending_request = get_object_or_404(
            SpendingRequest,
            pk=self.kwargs[self.spending_request_pk_field],
            document__pk=self.kwargs["pk"],
        )
        self.object = self.get_object()

        with reversion.create_revision():
            reversion.set_user(request.user)
            self.object.deleted = True
            self.object.save()

        messages.add_message(
            request, messages.SUCCESS, _("Ce document a bien été supprimé.")
        )

        return HttpResponseRedirect(
            reverse("manage_spending_request", args=(self.spending_request.pk,))
        )
