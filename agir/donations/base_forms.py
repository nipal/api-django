from crispy_forms import layout
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row
from django import forms
from django.conf import settings
from django.utils.formats import number_format
from django.utils.functional import keep_lazy_text
from django.utils.safestring import mark_safe
from django.utils.text import format_lazy
from django.utils.translation import ugettext_lazy as _
from django_countries.fields import CountryField

from agir.donations.form_fields import AskAmountField
from agir.lib.data import FRANCE_COUNTRY_CODES
from agir.lib.form_mixins import MetaFieldsMixin
from agir.people.models import Person


class SimpleDonationForm(forms.Form):
    button_label = "Je donne !"

    amount = AskAmountField(
        label="Montant du don",
        max_value=settings.DONATION_MAXIMUM,
        min_value=settings.DONATION_MINIMUM,
        decimal_places=2,
        required=True,
        error_messages={
            "invalid": _("Indiquez le montant à donner."),
            "min_value": format_lazy(
                _("Il n'est pas possible de donner moins que {min} €."),
                min=settings.DONATION_MINIMUM,
            ),
            "max_value": format_lazy(
                _("Les dons de plus de {max} € ne peuvent être faits par carte bleue."),
                max=settings.DONATION_MAXIMUM,
            ),
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "donation-form"
        self.helper.add_input(layout.Submit("valider", self.button_label))

        self.helper.layout = Layout()


class SimpleDonorForm(MetaFieldsMixin, forms.ModelForm):
    meta_fields = ["nationality"]
    button_label = "Je donne {amount}"

    email = forms.EmailField(
        label=_("Votre adresse email"),
        required=True,
        help_text=_(
            "Si vous êtes déjà inscrit⋅e sur la plateforme, utilisez l'adresse avec laquelle vous êtes inscrit⋅e"
        ),
    )

    subscribed = forms.BooleanField(
        label=_(
            "Je souhaite être tenu informé de l'actualité de la France insoumise par email."
        ),
        required=False,
    )

    amount = forms.IntegerField(
        max_value=settings.DONATION_MAXIMUM * 100,
        min_value=settings.DONATION_MINIMUM * 100,
        required=True,
        widget=forms.HiddenInput,
    )

    declaration = forms.BooleanField(
        required=True,
        label=_(
            "Je certifie sur l'honneur être une personne physique et que le réglement de mon don ne provient pas"
            " d'une personne morale (association, société, société civile...) mais de mon compte bancaire"
            " personnel."
        ),
        help_text=keep_lazy_text(mark_safe)(
            'Un reçu, édité par la <abbr title="Commission Nationale des comptes de campagne et des financements'
            ' politiques">CNCCFP</abbr>, me sera adressé, et me permettra de déduire cette somme de mes impôts'
            " dans les limites fixées par la loi."
        ),
    )

    nationality = CountryField(
        blank=False, blank_label=_("Indiquez le pays dont vous êtes citoyen")
    ).formfield(
        label=_("Nationalité"),
        help_text=_(
            "Indiquez France, si vous êtes de double nationalité, dont française."
        ),
    )

    fiscal_resident = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"disabled": True}),
        label=_("Je certifie être domicilié⋅e fiscalement en France"),
    )

    def __init__(self, *args, amount, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["amount"].initial = amount

        self.adding = self.instance._state.adding

        if not self.adding:
            del self.fields["email"]

        # we remove the subscribed field for people who are already subscribed
        if not self.adding and self.instance.subscribed:
            del self.fields["subscribed"]

        for f in [
            "first_name",
            "last_name",
            "location_address1",
            "location_zip",
            "location_city",
            "location_country",
            "contact_phone",
        ]:
            self.fields[f].required = True
        self.fields["location_address1"].label = "Adresse"
        self.fields["location_address2"].label = False
        self.fields["contact_phone"].help_text = (
            "Nous sommes dans l'obligation de pouvoir vous contacter en cas "
            "de demande de vérification par la CNCCFP."
        )

        fields = ["amount"]

        if "email" in self.fields:
            fields.append("email")

        fields.extend(["nationality", "fiscal_resident"])
        fields.extend(["first_name", "last_name"])
        fields.extend(
            [
                layout.Field("location_address1", placeholder="Ligne 1"),
                layout.Field("location_address2", placeholder="Ligne 2"),
            ]
        )

        fields.append(
            Row(
                layout.Div("location_zip", css_class="col-md-4"),
                layout.Div("location_city", css_class="col-md-8"),
            )
        )

        fields.append("location_country")

        fields.append("contact_phone")

        fields.append("declaration")

        if "subscribed" in self.fields:
            fields.append("subscribed")

        self.helper = FormHelper()
        self.helper.add_input(
            layout.Submit(
                "valider",
                self.button_label.format(amount=number_format(amount / 100, 2) + " €"),
            )
        )
        self.helper.layout = layout.Layout(*fields)

    def clean(self):
        cleaned_data = super().clean()

        nationality, fiscal_resident, location_country = (
            cleaned_data.get("nationality"),
            cleaned_data.get("fiscal_resident"),
            cleaned_data.get("location_country"),
        )

        if (
            "fiscal_resident" in self.fields
            and nationality != "FR"
            and not fiscal_resident
        ):
            self.add_error(
                "fiscal_resident",
                forms.ValidationError(
                    _(
                        "Les personnes non-françaises doivent être fiscalement domiciliées en France."
                    ),
                    code="not_fiscal_resident",
                ),
            )

        if fiscal_resident and location_country not in FRANCE_COUNTRY_CODES:
            self.add_error(
                "location_country",
                forms.ValidationError(
                    _(
                        "Pour pouvoir donner si vous n'êtes pas français, vous devez être domicilié⋅e fiscalement en"
                        " France et nous indiquer votre adresse fiscale en France."
                    )
                ),
            )

        return cleaned_data

    class Meta:
        model = Person
        fields = (
            "first_name",
            "last_name",
            "location_address1",
            "location_address2",
            "location_zip",
            "location_city",
            "location_country",
            "contact_phone",
            "subscribed",
        )
