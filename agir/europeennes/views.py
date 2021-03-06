from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import FormView, TemplateView, DetailView
from functools import partial
from wsgiref.util import FileWrapper

from agir.authentication.view_mixins import SoftLoginRequiredMixin
from agir.donations.actions import find_or_create_person_from_payment
from agir.donations.base_views import BaseAskAmountView
from agir.donations.tasks import send_donation_email
from agir.donations.views import BasePersonalInformationView
from agir.europeennes import AFCESystemPayPaymentMode, tasks
from agir.europeennes.actions import generate_html_contract, SUBSTITUTIONS
from agir.europeennes.apps import EuropeennesConfig
from agir.europeennes.forms import LoanForm, ContractForm, LenderForm
from agir.front.view_mixins import SimpleOpengraphMixin
from agir.payments.actions import create_payment, redirect_to_payment
from agir.payments.models import Payment

DONATIONS_SESSION_NAMESPACE = "_europeennes_donations"
LOANS_INFORMATION_SESSION_NAMESPACE = "_europeennes_loans"
LOANS_CONTRACT_SESSION_NAMESPACE = "_europeennes_loans_contract"


class DonationAskAmountView(SimpleOpengraphMixin, BaseAskAmountView):
    meta_title = "Dernier appel aux dons : objectif 300 000 € pour boucler le budget !"
    meta_description = (
        "La France insoumise est le seul mouvement transparent sur le financement de la campagne européenne."
        " Pour l’aider à boucler le budget de campagne, il est encore possible de faire un don !"
    )
    meta_type = "website"
    meta_image = urljoin(
        urljoin(settings.FRONT_DOMAIN, settings.STATIC_URL),
        "europeennes/RELANCE-300-000_FB.jpg",
    )
    template_name = "europeennes/donations/ask_amount.html"
    success_url = reverse_lazy("europeennes_donation_information")
    session_namespace = DONATIONS_SESSION_NAMESPACE


class DonationPersonalInformationView(BasePersonalInformationView):
    template_name = "europeennes/donations/personal_information.html"
    payment_mode = AFCESystemPayPaymentMode.id
    payment_type = EuropeennesConfig.DONATION_PAYMENT_TYPE
    session_namespace = DONATIONS_SESSION_NAMESPACE
    base_redirect_url = "europeennes_donation_amount"


class DonationReturnView(TemplateView):
    template_name = "donations/thanks.html"


def donation_notification_listener(payment):
    if payment.status == Payment.STATUS_COMPLETED:
        find_or_create_person_from_payment(payment)
        send_donation_email.delay(
            payment.person.pk, template_code="DONATION_MESSAGE_EUROPEENNES"
        )


class MaxTotalLoanMixin:
    def dispatch(self, *args, **kwargs):
        if (
            Payment.objects.filter(
                type=EuropeennesConfig.LOAN_PAYMENT_TYPE,
                status=Payment.STATUS_COMPLETED,
            ).aggregate(amount=Coalesce(Sum("price"), 0))["amount"]
            > settings.LOAN_MAXIMUM_TOTAL
        ):
            return HttpResponseRedirect(settings.LOAN_MAXIMUM_THANK_YOU_PAGE)

        return super().dispatch(*args, **kwargs)


class LoanAskAmountView(MaxTotalLoanMixin, SimpleOpengraphMixin, BaseAskAmountView):
    meta_title = "Je prête à la campagne France insoumise pour les élections européennes le 26 mai"
    meta_description = (
        "Nos 79 candidats, menés par Manon Aubry, la tête de liste, sillonent déjà le pays. Ils ont"
        " besoin de votre soutien pour pouvoir mener cette campagne. Votre contribution sera décisive !"
    )
    meta_type = "website"
    meta_image = urljoin(
        urljoin(settings.FRONT_DOMAIN, settings.STATIC_URL), "europeennes/dons.jpg"
    )
    template_name = "europeennes/loans/ask_amount.html"
    success_url = reverse_lazy("europeennes_loan_information")
    form_class = LoanForm
    session_namespace = LOANS_INFORMATION_SESSION_NAMESPACE


class LoanPersonalInformationView(MaxTotalLoanMixin, BasePersonalInformationView):
    template_name = "europeennes/loans/personal_information.html"
    session_namespace = LOANS_INFORMATION_SESSION_NAMESPACE
    form_class = LenderForm
    base_redirect_url = "europeennes_loan_amount"

    def prepare_data_for_serialization(self, data):
        return {
            **data,
            "contact_phone": data["contact_phone"].as_e164,
            "date_of_birth": data["date_of_birth"].strftime("%d/%m/%Y"),
            "payment_mode": data["payment_mode"].id,
            "iban": data["iban"].as_stored_value,
        }

    def form_valid(self, form):
        if not form.adding:
            form.save()

        self.request.session[
            LOANS_CONTRACT_SESSION_NAMESPACE
        ] = self.prepare_data_for_serialization(form.cleaned_data)

        return HttpResponseRedirect(reverse("europeennes_loan_sign_contract"))


class LoanAcceptContractView(MaxTotalLoanMixin, FormView):
    form_class = ContractForm
    template_name = "europeennes/loans/validate_contract.html"

    def dispatch(self, request, *args, **kwargs):
        if LOANS_CONTRACT_SESSION_NAMESPACE not in request.session:
            if LOANS_INFORMATION_SESSION_NAMESPACE in request.session:
                return HttpResponseRedirect(reverse("europeennes_loan_information"))
            else:
                return HttpResponseRedirect(reverse("europeennes_loan_amount"))

        self.contract_information = request.session[LOANS_CONTRACT_SESSION_NAMESPACE]

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            contract=generate_html_contract(self.contract_information, baselevel=3),
            **self.contract_information,
            **kwargs
        )

    def clear_session(self):
        del self.request.session[LOANS_INFORMATION_SESSION_NAMESPACE]
        del self.request.session[LOANS_CONTRACT_SESSION_NAMESPACE]

    def form_valid(self, form):
        self.contract_information["acceptance_datetime"] = (
            timezone.now()
            .astimezone(timezone.get_default_timezone())
            .strftime("%d/%m/%Y à %H:%M")
        )

        person = None
        if self.request.user.is_authenticated:
            person = self.request.user.person

        payment_fields = [f.name for f in Payment._meta.get_fields()]

        kwargs = {
            f: v for f, v in self.contract_information.items() if f in payment_fields
        }
        if "email" in self.contract_information:
            kwargs["email"] = self.contract_information["email"]

        with transaction.atomic():
            payment = create_payment(
                person=person,
                mode=self.contract_information["payment_mode"],
                type=EuropeennesConfig.LOAN_PAYMENT_TYPE,
                price=self.contract_information["amount"],
                meta=self.contract_information,
                **kwargs
            )

        self.clear_session()

        return redirect_to_payment(payment)


class LoanReturnView(TemplateView):
    template_name = "europeennes/loans/return.html"

    def get_context_data(self, **kwargs):
        gender = self.kwargs["payment"].meta["gender"]

        return super().get_context_data(
            chere_preteur=SUBSTITUTIONS["cher_preteur"][gender], **kwargs
        )


class LoanContractView(SoftLoginRequiredMixin, DetailView):
    queryset = Payment.objects.filter(
        status=Payment.STATUS_COMPLETED, type=EuropeennesConfig.LOAN_PAYMENT_TYPE
    )

    def get(self, request, *args, **kwargs):
        payment = self.get_object()

        if payment.person != request.user.person:
            raise PermissionDenied("Vous n'avez pas le droit d'accéder à cette page.")

        if "contract_path" not in payment.meta:
            raise Http404()

        with default_storage.open(payment.meta["contract_path"], "rb") as f:
            return HttpResponse(FileWrapper(f), content_type="application/pdf")


def generate_and_send_contract(payment_id):
    return (
        tasks.generate_contract.si(payment_id)
        | tasks.send_contract_confirmation_email.si(payment_id)
    ).delay()


def loan_notification_listener(payment):
    if payment.status == Payment.STATUS_COMPLETED:
        find_or_create_person_from_payment(payment)
        transaction.on_commit(partial(generate_and_send_contract, payment.id))
