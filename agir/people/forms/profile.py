from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Fieldset
from crispy_forms.layout import HTML, Row, Submit, Layout
from django import forms
from django.urls import reverse_lazy, reverse
from django.utils.html import format_html

from django.utils.translation import ugettext_lazy as _

from agir.lib.form_components import HalfCol, FullCol, ThirdCol
from agir.lib.form_mixins import TagMixin, MetaFieldsMixin
from agir.lib.forms import MediaInHead
from agir.lib.models import RE_FRENCH_ZIPCODE
from agir.lib.tasks import geocode_person
from agir.people.form_mixins import ContactPhoneNumberMixin
from agir.people.models import PersonTag, Person
from agir.people.tags import skills_tags


def cut_list(list, parts):
    lst = []
    size = len(list)

    for i in range(parts):
        beg = int(i * size / parts)
        end = int((i + 1) * size / parts)
        lst.append(list[beg:end])
    return lst


class ProfileForm(MetaFieldsMixin, ContactPhoneNumberMixin, TagMixin, forms.ModelForm):
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

        self.fields["location_address1"].label = _("Adresse")
        self.fields["location_address2"].label = False
        self.fields["location_country"].required = True

        self.helper.layout = Layout(
            Row(
                HalfCol(  # contact part
                    Row(HalfCol("first_name"), HalfCol("last_name")),
                    Row(
                        HalfCol("gender"),
                        HalfCol(Field("date_of_birth", placeholder=_("JJ/MM/AAAA"))),
                    ),
                    Row(
                        FullCol(
                            Field("location_address1", placeholder=_("1ère ligne")),
                            Field("location_address2", placeholder=_("2ème ligne")),
                        )
                    ),
                    Row(HalfCol("location_zip"), HalfCol("location_city")),
                    Row(FullCol("location_country")),
                    Row(HalfCol("contact_phone"), HalfCol("occupation")),
                    Row(HalfCol("associations"), HalfCol("unions")),
                    Row(
                        HalfCol(
                            Field("party", placeholder="Nom du parti"),
                            Field("party_responsibility", placeholder="Responsabilité"),
                        ),
                        HalfCol("other"),
                    ),
                    Row(FullCol(Field("mandates"))),
                ),
                HalfCol(
                    HTML("<label>Savoir-faire</label>"),
                    *(tag for tag, desc in skills_tags),
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

    @property
    def media(self):
        return MediaInHead.from_media(super().media)

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
            "contact_phone",
            "mandates",
        )


class InformationPersonalForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit("submit", "Enregistrer mes informations"))

        self.fields["location_address1"].label = _("Adresse")
        self.fields["location_address2"].label = False
        # self.fields["location_address2"].label = "Complement d'adresse"
        self.fields["location_country"].required = True

        # self.helper.layout = Layout(
        #     Row(
        #         HalfCol(
        #             Row(HalfCol("first_name"), HalfCol("last_name")),
        #             Row(
        #                 HalfCol("gender"),
        #                 HalfCol(Field("date_of_birth", placeholder=_("JJ/MM/AAAA"))),
        #             ),
        #             Row(
        #                 FullCol(
        #                     Field("location_address1", placeholder=_("1ère ligne"))
        #                 ),
        #                 FullCol(
        #                     Field("location_address2", placeholder=_("2ème ligne"))
        #                 ),
        #                 HalfCol("location_zip"),
        #                 HalfCol("location_city"),
        #             ),
        #             Row(FullCol("location_country")),
        #         )
        #     )
        # )

        self.helper.layout = Layout(
            Row(
                HalfCol(
                    Row(HalfCol("first_name"), HalfCol("last_name")),
                    Row(
                        HalfCol("gender"),
                        HalfCol(Field("date_of_birth", placeholder=_("JJ/MM/AAAA"))),
                    ),
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


# TODO: ajouter le champ d'email (+selection), champ fusion de compte + fonction associer
class InformationContactForm(MetaFieldsMixin, ContactPhoneNumberMixin, forms.ModelForm):
    email_merge_target = forms.EmailField(
        max_length=200, label=_("L'adresse du compte à fusioner"), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit("submit", "Enregistrer mes informations"))

        block_template = """
                    <label class="control-label">{label}</label>
                    <div class="controls">
                      <div>{value}</div>
                      <p class="help-block">{help_text}</p>
                    </div>
                """

        email_management_block = HTML(
            format_html(
                block_template,
                label=_("Gérez vos adresses emails"),
                value=format_html(
                    '<a href="{}" class="btn btn-default">{}</a>',
                    reverse("email_management"),
                    _("Accéder au formulaire de gestion de vos emails"),
                ),
                help_text=_(
                    "Ce formulaire vous permet d'ajouter de nouvelles adresses ou de supprimer les existantes"
                ),
            )
        )

        emails = self.instance.emails.all()
        email_fieldset_name = _("Mes adresses emails")
        email_label = _("Email de contact")
        email_help_text = _(
            "L'adresse que nous utilisons pour vous envoyer les lettres d'informations et les notifications."
        )

        validation_link = format_html(
            '<input type="submit" name="validation" value="{label}" class="btn btn-default">',
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
                    "Validez votre numéro de téléphone afin de certifier votre compte"
                )
                if unverified
                else "",
            )
        )

        self.fields["primary_email"] = forms.ModelChoiceField(
            queryset=emails,
            required=True,
            label=email_label,
            initial=emails[0],
            help_text=email_help_text,
        )
        self.helper.layout = Layout(
            Row(Row(HalfCol("contact_phone"))),
            Fieldset(
                email_fieldset_name,
                Row(
                    HalfCol("primary_email"),
                    HalfCol(email_management_block),
                    HalfCol(validation_block),
                ),
                "email_merge_target",
            ),
        )

    class Meta:
        model = Person
        fields = ("contact_phone",)


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

        # self.helper.layout = Layout(
        #     Row(
        #         HalfCol(  # contact part
        #             HalfCol("occupation"),
        #             Row(HalfCol("associations"), HalfCol("unions")),
        #             Row(FullCol(Field("mandates"))),
        #         ),
        #         HalfCol(
        #             HalfCol(
        #                 Field("party", placeholder="Nom du parti"),
        #                 Field("party_responsibility", placeholder="Responsabilité"),
        #             ),
        #             HalfCol("other"),
        #         ),
        #     ),
        #     Row(
        #         HalfCol(
        #             HTML("<label>Savoir-faire</label>"),
        #             *(tag for tag, desc in skills_tags[0 : int(len(skills_tags) / 2)]),
        #         ),
        #         HalfCol(
        #             *(
        #                 tag
        #                 for tag, desc in skills_tags[
        #                     int(len(skills_tags) / 2) : int(len(skills_tags))
        #                 ]
        #             )
        #         ),
        #     ),
        # )
        #

    @property
    def media(self):
        return MediaInHead.from_media(super().media)

    class Meta:
        model = Person
        fields = ("mandates",)
