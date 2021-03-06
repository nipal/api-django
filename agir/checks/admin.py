from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.http import (
    HttpResponseRedirect,
    Http404,
    HttpResponseNotAllowed,
    HttpResponseForbidden,
)
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html_join
from django.utils.translation import ugettext_lazy as _, ugettext, ngettext
from django.template.response import TemplateResponse

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from agir.api.admin import admin_site
from agir.payments.actions import notify_status_change

from .models import CheckPayment


class CheckPaymentSearchForm(forms.Form):
    numbers = forms.CharField(
        label="Numéro(s) de chèque",
        required=True,
        help_text=_(
            "Saisissez les numéros de transaction du chèque, séparés par des espaces"
        ),
    )
    amount = forms.DecimalField(
        label="Montant du chèque", decimal_places=2, min_value=0, required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Rechercher"))

    def clean_numbers(self):
        numbers = self.cleaned_data["numbers"].split()

        try:
            numbers = [int(n) for n in numbers]
        except ValueError:
            raise forms.ValidationError(
                _("Entrez les numéros de chèque séparés par des espace")
            )

        missing_checks = []
        for n in numbers:
            try:
                CheckPayment.objects.get(pk=n)
            except CheckPayment.DoesNotExist:
                missing_checks.append(n)

        if len(missing_checks) == 1:
            raise forms.ValidationError(
                ugettext("Le chèque n°{n} n'existe pas.").format(n=missing_checks[0])
            )
        elif missing_checks:
            raise forms.ValidationError(
                ugettext("Les paiements de numéros {numeros} n'existent pas.").format(
                    numeros=", ".join([str(i) for i in missing_checks])
                )
            )

        return numbers


def change_payment_status(status, description):
    def action(modeladmin, request, queryset):
        with transaction.atomic():
            now = timezone.now().astimezone(timezone.utc).isoformat()

            for payment in queryset.filter(status=CheckPayment.STATUS_WAITING):
                payment.status = status
                payment.events.append(
                    {
                        "change_status": status,
                        "date": now,
                        "origin": "check_payment_admin_action",
                    }
                )
                payment.save()
                notify_status_change(payment)

    # have to change the function name so that django admin see that they are different functions
    action.__name__ = f"change_to_{status}"
    action.short_description = description

    return action


@admin.register(CheckPayment, site=admin_site)
class CheckPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "status",
        "price",
        "person",
        "email",
        "first_name",
        "last_name",
    )
    fields = readonly_fields = (
        "type",
        "mode",
        "person",
        "email",
        "first_name",
        "last_name",
        "price",
        "status",
        "phone_number",
        "location_address1",
        "location_address2",
        "location_zip",
        "location_city",
        "location_country",
        "meta",
        "events",
        "actions_buttons",
    )

    list_filter = ("price", "status")
    search_fields = ("id", "email", "first_name", "last_name")

    actions = [
        change_payment_status(CheckPayment.STATUS_COMPLETED, _("Marquer comme reçu")),
        change_payment_status(
            CheckPayment.STATUS_CANCELED, _("Marqué comme abandonné par l'acheteur")
        ),
        change_payment_status(CheckPayment.STATUS_REFUSED, _("Marqué comme refusé")),
    ]

    def actions_buttons(self, object):
        if object.status == CheckPayment.STATUS_WAITING:
            statuses = [
                (CheckPayment.STATUS_COMPLETED, "Valider"),
                (CheckPayment.STATUS_CANCELED, "Annuler"),
                (CheckPayment.STATUS_REFUSED, "Refuser"),
            ]

            return format_html_join(
                " ",
                '<a href="{}" class="button">{}</a>',
                (
                    (
                        reverse(
                            "admin:checks_checkpayment_change_status",
                            kwargs={"pk": object.pk, "status": status},
                        ),
                        label,
                    )
                    for status, label in statuses
                ),
            )
        return "Aucune"

    actions_buttons.short_description = _("Actions")

    def has_add_permission(self, request):
        """Forbidden to add checkpayment through this model admin"""
        return False

    def get_urls(self):
        return [
            path(
                "search/",
                admin_site.admin_view(self.search_check_view),
                name="checks_checkpayment_search",
            ),
            path(
                "validate/",
                admin_site.admin_view(self.validate_check_view),
                name="checks_checkpayment_validate",
            ),
            path(
                "<int:pk>/change/<int:status>/",
                admin_site.admin_view(self.change_status),
                name="checks_checkpayment_change_status",
            ),
        ] + super().get_urls()

    def search_check_view(self, request):
        if request.method == "POST":
            form = CheckPaymentSearchForm(data=request.POST)

            if form.is_valid():
                return HttpResponseRedirect(
                    "{}?{}".format(
                        reverse("admin:checks_checkpayment_validate"),
                        request.POST.urlencode(),
                    )
                )
        else:
            form = CheckPaymentSearchForm()

        return TemplateResponse(
            request,
            template="admin/checks/checkpayment/search_check.html",
            context={"form": form, "opts": CheckPayment._meta},
        )

    def validate_check_view(self, request):
        get_form = CheckPaymentSearchForm(data=request.GET)
        return_response = HttpResponseRedirect(
            reverse("admin:checks_checkpayment_search")
        )

        if not get_form.is_valid():
            return return_response

        amount, numbers = (
            get_form.cleaned_data["amount"],
            get_form.cleaned_data["numbers"],
        )
        payments = CheckPayment.objects.filter(pk__in=numbers)

        if not len(payments) == len(numbers):
            messages.add_message(
                request,
                messages.ERROR,
                _("Erreur avec un des paiements : veuillez rééssayer"),
            )

        total_price = sum(p.price for p in payments)
        check_amount = int(amount * 100)

        can_validate = (total_price == check_amount) and all(
            c.status == CheckPayment.STATUS_WAITING for c in payments
        )

        if can_validate and request.method == "POST":
            now = timezone.now().astimezone(timezone.utc).isoformat()

            with transaction.atomic():
                for p in payments:
                    p.status = CheckPayment.STATUS_COMPLETED
                    p.events.append(
                        {
                            "change_status": CheckPayment.STATUS_COMPLETED,
                            "date": now,
                            "origin": "check_payment_admin_validation",
                        }
                    )
                    p.save()

            # notifier en dehors de la transaction, pour être sûr que ça ait été committé
            for p in payments:
                notify_status_change(p)

            messages.add_message(
                request,
                messages.SUCCESS,
                ngettext(
                    "Chèque %(numbers)s validé",
                    "Chèques %(numbers)s validés",
                    len(numbers),
                )
                % {"numbers": ", ".join(str(n) for n in numbers)},
            )
            return return_response

        return TemplateResponse(
            request,
            "admin/checks/checkpayment/validate_check.html",
            context={
                "checks": payments,
                "can_validate": can_validate,
                "total_price": total_price,
                "check_amount": check_amount,
                "opts": CheckPayment._meta,
            },
        )

    def change_status(self, request, pk, status):

        if status not in [
            CheckPayment.STATUS_COMPLETED,
            CheckPayment.STATUS_REFUSED,
            CheckPayment.STATUS_CANCELED,
        ]:
            raise Http404()

        if request.method != "GET":
            return HttpResponseNotAllowed(permitted_methods="POST")

        try:
            payment = CheckPayment.objects.get(pk=pk)
        except CheckPayment.DoesNotExist:
            raise Http404()

        if payment.status != CheckPayment.STATUS_WAITING:
            return HttpResponseForbidden()

        now = timezone.now().astimezone(timezone.utc).isoformat()
        with transaction.atomic():
            payment.status = status
            payment.events.append(
                {
                    "change_status": status,
                    "date": now,
                    "origin": "check_payment_admin_change_button",
                }
            )
            payment.save()
            notify_status_change(payment)

        return HttpResponseRedirect(
            reverse("admin:checks_checkpayment_change", args=[payment.pk])
        )
