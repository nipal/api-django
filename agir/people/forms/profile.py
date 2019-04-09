from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Div
from crispy_forms.layout import Fieldset
from crispy_forms.layout import HTML, Row, Submit, Layout
from django import forms
from django.forms import Form
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from agir.lib.form_components import HalfCol, FullCol, ThirdCol
from agir.lib.form_mixins import TagMixin, MetaFieldsMixin
from agir.lib.forms import MediaInHead
from agir.lib.models import RE_FRENCH_ZIPCODE
from agir.lib.tasks import geocode_person
from agir.people.form_mixins import ContactPhoneNumberMixin
from agir.people.forms import FormActions, PreferencesFormMixin
from agir.people.models import PersonTag, Person
from agir.people.tags import skills_tags
from agir.people.tasks import (
    send_confirmation_change_email,
    send_confirmation_merge_account,
)
from agir.people.token_buckets import ChangeMailBucket


def cut_list(list, parts):
    lst = []
    size = len(list)

    for i in range(parts):
        beg = int(i * size / parts)
        end = int((i + 1) * size / parts)
        lst.append(list[beg:end])
    return lst


class PersonalInformationsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit("submit", "Enregistrer mes informations"))

        self.fields["location_address1"].label = _("Adresse")
        self.fields["location_address2"].label = False
        self.fields["location_country"].required = True

        description_gender = HTML(
            format_html(
                """<p class="help-block">{help_text}</p>""",
                help_text="Utilisé pour la parité des tirages au sort et de l'animation des groupes d'action.",
            )
        )

        description_address = HTML(
            format_html(
                """<p class="help-block">{help_text}</p>""",
                help_text="Permet de vous informer d'événements se déroulant près de chez vous.",
            )
        )

        description_birth_date = HTML(
            format_html(
                """<p class="help-block">{help_text}</p>""",
                help_text="Utilisé à des fins statistiques.",
            )
        )

        description = HTML(
            """<p>Ces informations nous permettrons de s'adresser à vous plus correctement et 
            en fonction de votre situation géographique.</p>"""
        )

        self.helper.layout = Layout(
            Row(
                FullCol(description),
                HalfCol(
                    Row(HalfCol("first_name"), HalfCol("last_name")),
                    Row(
                        HalfCol("gender"),
                        HalfCol(Field("date_of_birth", placeholder=_("JJ/MM/AAAA"))),
                    ),
                    Row(HalfCol(description_gender), HalfCol(description_birth_date)),
                ),
                HalfCol(
                    Row(
                        FullCol(
                            Field("location_address1", placeholder=_("1ère ligne"))
                        ),
                        FullCol(
                            Field("location_address2", placeholder=_("2ème ligne"))
                        ),
                        HalfCol("location_zip"),
                        HalfCol("location_city"),
                    ),
                    Row(FullCol("location_country")),
                    Row(FullCol(description_address)),
                ),
            )
        )

    def clean(self):
        if self.cleaned_data.get("location_country") == "FR":
            if self.cleaned_data["location_zip"] == "":
                self.add_error(
                    "location_zip",
                    forms.ValidationError(
                        self.fields["location_zip"].error_messages["required"],
                        code="required",
                    ),
                )
            elif not RE_FRENCH_ZIPCODE.match(self.cleaned_data["location_zip"]):
                self.add_error(
                    "location_zip",
                    forms.ValidationError(
                        _("Merci d'indiquer un code postal valide"), code="invalid"
                    ),
                )

        return self.cleaned_data

    def _save_m2m(self):
        super()._save_m2m()

        address_has_changed = any(
            f in self.changed_data for f in self.instance.GEOCODING_FIELDS
        )

        if address_has_changed and self.instance.should_relocate_when_address_changed():
            geocode_person.delay(self.instance.pk)

    class Meta:
        model = Person
        fields = (
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "location_address1",
            "location_address2",
            "location_city",
            "location_zip",
            "location_country",
        )


class AddEmailMergeAccountForm(Form):
    email_add_merge = forms.EmailField(
        max_length=200,
        label="adresse e-mail",
        required=False,
        error_messages={
            "rate_limit": "Trop d'email de confirmation envoyés. Merci de réessayer dans quelques minutes.",
            "same_person": "Cette adresse e-mail correspond déjà à l'une de vos adresses pour vous connecter.",
        },
    )

    def __init__(self, user_pk, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.user_pk = user_pk
        self.fields["email_add_merge"].label = "Adresse e-mail"
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit("submit", "Envoyer"))
        self.helper.layout = Layout(("email_add_merge"))

    def is_rate_limited(self):
        if not ChangeMailBucket.has_tokens(self.user_pk):
            self.add_error(
                "email_add_merge",
                self.fields["email_add_merge"].error_messages["rate_limit"],
            )
            return True
        False

    def send_confirmation(self):
        email = self.cleaned_data["email_add_merge"]

        try:
            pk_merge = Person.objects.get(email=email).pk
        except Person.DoesNotExist:
            if self.is_rate_limited():
                return [None, None]

            # l'utilisateur n'existe pas. On envoie une demande d'ajout d'adresse e-mail
            send_confirmation_change_email.delay(
                new_email=email, user_pk=str(self.user_pk)
            )
            return [email, False]
        else:
            if pk_merge == self.user_pk:
                self.add_error(
                    "email_add_merge",
                    self.fields["email_add_merge"].error_messages["same_person"],
                )
                return [None, None]

            # l'utilisateur existe. On envoie une demande de fusion de compte
            if self.is_rate_limited():
                return [None, None]
            send_confirmation_merge_account.delay(self.user_pk, pk_merge)
            return [email, True]


class InformationConfidentialityForm(Form):
    def get_fields(self, fields=None):
        fields = fields or []

        block_template = """
                    <label class="control-label">{label}</label>
                    <div class="controls">
                      <div>{value}</div>
                      <p class="help-block">{help_text}</a></p>
                    </div>
                """

        delete_account_link = format_html(
            '<a href="{url}" class="btn btn-default">{label}</a>',
            url=reverse("delete_account"),
            label="Je veux supprimer mon compte définitivement",
        )

        validation_block = HTML(
            format_html(
                block_template,
                label="Suppression de votre compte",
                value=delete_account_link,
                help_text="Attention cette action est irréversible !",
            )
        )

        description_block = HTML(
            format_html(
                """<p>{description}<a href="{link_url}">{link_text}</a></p>""",
                description="Vous pouvez en savoir plus sur le traitement de vos données personnelles en lisant ",
                link_url="https://lafranceinsoumise.fr/mentions-legales/",
                link_text="nos mentions légales.",
            )
        )

        fields.extend([description_block, validation_block])
        return fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(*self.get_fields())


class ContactForm(TagMixin, MetaFieldsMixin, ContactPhoneNumberMixin, forms.ModelForm):
    tags = [
        (
            "newsletter_efi",
            _(
                "Recevoir les informations liées aux cours de l'École de Formation insoumise"
            ),
        )
    ]
    tag_model_class = PersonTag

    def __init__(self, data=None, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "POST"

        self.no_mail = data is not None and "no_mail" in data

        self.helper.layout = Layout(*self.get_fields())

        self.fields["contact_phone"].label = "Numéro de contact"

        if not self.instance.is_insoumise:
            del self.fields["subscribed"]
            del self.fields["subscribed_sms"]
            del self.fields["event_notifications"]
            del self.fields["group_notifications"]
            del self.fields["newsletter_efi"]

    def get_fields(self, fields=None):
        fields = fields or []

        block_template = """
                    <label class="control-label">{label}</label>
                    <div class="controls">
                      <div>{value}</div>
                      <p class="help-block">{help_text}</p>
                    </div>
                """
        validation_link = format_html(
            '<a href="{url}" class="btn btn-default">{label}</a>',
            url=reverse("send_validation_sms"),
            label=_("Valider mon numéro de téléphone"),
        )

        unverified = (
            self.instance.contact_phone_status == Person.CONTACT_PHONE_UNVERIFIED
        )

        validation_block = HTML(
            format_html(
                block_template,
                label=_("Vérification de votre compte"),
                value=validation_link
                if unverified
                else f"Compte {self.instance.get_contact_phone_status_display().lower()}",
                help_text=_(
                    "Validez votre numéro de téléphone afin de certifier votre compte."
                )
                if unverified
                else "",
            )
        )

        btn_no_mails = (
            FormActions(
                Submit(
                    "no_mail",
                    "Ne plus recevoir d'emails ou de SMS",
                    css_class="btn-danger",
                ),
                css_class="text-right",
            )
            if self.instance.is_insoumise
            else Div()
        )

        fields.extend(
            [
                "subscribed",
                Div("newsletter_efi", style="margin-left: 50px;"),
                "group_notifications",
                "event_notifications",
                Fieldset(
                    "Téléphone",
                    Row(ThirdCol("contact_phone"), ThirdCol(validation_block)),
                    "subscribed_sms",
                ),
                FormActions(Submit("submit", "Sauvegarder")),
                btn_no_mails,
            ]
        )
        return fields

    def clean(self):
        cleaned_data = super().clean()

        if self.no_mail:
            # if the user clicked the "unsubscribe from all button", we want to put all fields thare are boolean
            # to false, and keep all the others to their initial values: it allows posting to this form with
            # the single "no_mail" content
            for k, v in cleaned_data.items():
                if isinstance(v, bool):
                    cleaned_data[k] = False
                else:
                    cleaned_data[k] = self.get_initial_for_field(self.fields[k], k)

        return cleaned_data

    class Meta:
        model = Person
        fields = (
            "contact_phone",
            "subscribed_sms",
            "subscribed",
            "group_notifications",
            "event_notifications",
        )


class ActivityAblebilityForm(MetaFieldsMixin, TagMixin, forms.ModelForm):
    tags = skills_tags
    tag_model_class = PersonTag
    meta_fields = [
        "occupation",
        "associations",
        "unions",
        "party",
        "party_responsibility",
        "other",
    ]

    occupation = forms.CharField(max_length=200, label=_("Métier"), required=False)
    associations = forms.CharField(
        max_length=200, label=_("Engagements associatifs"), required=False
    )
    unions = forms.CharField(
        max_length=200, label=_("Engagements syndicaux"), required=False
    )
    party = forms.CharField(max_length=60, label=_("Parti politique"), required=False)
    party_responsibility = forms.CharField(max_length=100, label=False, required=False)
    other = forms.CharField(
        max_length=200, label=_("Autres engagements"), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit("submit", "Enregistrer mes informations"))

        self.helper.layout = Layout(
            Row(
                FullCol(
                    HTML(
                        """<p>Lorsque nous cherchons des membres du mouvement avec des compétences particulières, 
                        nous utilisons les informations saisies dans ce formulaire.</p>"""
                    )
                ),
                ThirdCol(
                    "occupation",
                    "associations",
                    "unions",
                    Field("party", placeholder="Nom du parti"),
                    Field("party_responsibility", placeholder="Responsabilité"),
                    "mandates",
                ),
                ThirdCol(
                    HTML("<label>Savoir-faire</label>"),
                    *(tag for tag, desc in skills_tags[0 : int(len(skills_tags) / 2)]),
                ),
                ThirdCol(
                    *(
                        tag
                        for tag, desc in skills_tags[
                            int(len(skills_tags) / 2) : int(len(skills_tags))
                        ]
                    )
                ),
            )
        )

    @property
    def media(self):
        return MediaInHead.from_media(super().media)

    class Meta:
        model = Person
        fields = ("mandates",)
