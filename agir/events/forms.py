from django import forms
from django.template.defaultfilters import floatformat
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms import layout
from phonenumber_field.formfields import PhoneNumberField

from agir.events.actions import legal
from agir.events.actions.legal import needs_approval
from agir.groups.models import SupportGroup
from agir.lib.form_components import *
from agir.lib.form_mixins import (
    LocationFormMixin,
    ContactFormMixin,
    GeocodingBaseForm,
    SearchByZipCodeFormBase,
    MetaFieldsMixin,
    ImageFormMixin,
)
from agir.people.forms import BasePersonForm
from agir.payments.payment_modes import PaymentModeField

from ..people.models import Person, PersonFormSubmission
from .models import Event, OrganizerConfig, RSVP, EventImage, EventSubtype
from .tasks import (
    send_event_creation_notification,
    send_event_changed_notification,
    send_external_rsvp_confirmation,
    send_secretariat_notification,
)
from ..lib.tasks import geocode_event
from ..lib.form_fields import AcceptCreativeCommonsLicenceField

__all__ = [
    "EventForm",
    "AddOrganizerForm",
    "EventGeocodingForm",
    "EventReportForm",
    "UploadEventImageForm",
    "SearchEventForm",
]


class AgendaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class EventForm(LocationFormMixin, ContactFormMixin, ImageFormMixin, forms.ModelForm):
    geocoding_task = geocode_event

    CHANGES = {
        "name": "information",
        "start_time": "timing",
        "end_time": "timing",
        "contact_name": "contact",
        "contact_email": "contact",
        "contact_phone": "contact",
        "location_name": "location",
        "location_address1": "location",
        "location_address2": "location",
        "location_city": "location",
        "location_zip": "location",
        "location_country": "location",
        "description": "information",
    }

    image_field = "image"

    subtype = forms.ModelChoiceField(
        queryset=EventSubtype.objects.filter(visibility=EventSubtype.VISIBILITY_ALL),
        to_field_name="label",
    )

    def __init__(self, *args, person, **kwargs):
        super(EventForm, self).__init__(*args, **kwargs)

        self.person = person

        excluded_fields = []

        self.is_creation = self.instance._state.adding
        self.fields["image"].help_text = _(
            """
        Vous pouvez ajouter une image de bannière à votre événement : elle apparaîtra alors sur la page de votre
        événement, et comme illustration si vous le partagez sur les réseaux sociaux. Pour cela, choisissez une image
        à peu près deux fois plus large que haute, et de dimensions supérieures à 1200 par 630 pixels.
        """
        )

        self.fields["description"].help_text = _(
            """
        Cette description doit permettre de comprendre rapidement sur quoi porte et comment se passera votre événement.
        Incluez toutes les informations pratiques qui pourraient être utiles aux insoumis⋅es qui souhaiteraient
        participer (matériel à amener, précisions sur le lieu ou contraintes particulières, par exemple).
        """
        )

        self.fields["as_group"] = forms.ModelChoiceField(
            queryset=SupportGroup.objects.filter(
                memberships__person=person, memberships__is_manager=True, published=True
            ),
            empty_label="Ne pas créer au nom d'un groupe",
            label=_("Créer l'événement au nom d'un groupe d'action"),
            required=False,
        )

        self.fields["name"].label = "Nom de l'événement"
        self.fields["name"].help_text = None

        if not self.is_creation:
            self.fields["notify"] = forms.BooleanField(
                required=False,
                initial=False,
                label=_("Signalez ces changements aux participants à l'événement"),
                help_text=_(
                    "Un email sera envoyé à la validation de ce formulaire. Merci de ne pas abuser de cette"
                    " fonctionnalité."
                ),
            )
            notify_field = [Row(FullCol("notify"))]
            self.organizer_config = OrganizerConfig.objects.get(
                person=self.person, event=self.instance
            )
            self.fields["as_group"].initial = self.organizer_config.as_group
            del self.fields["subtype"]

            excluded_fields = self.instance.subtype.config.get("excluded_fields", [])
            if "image" in excluded_fields:
                excluded_fields.append("image_accept_license")

            for f in excluded_fields:
                if f in self.fields:
                    del self.fields[f]
        else:
            notify_field = []

        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit("submit", "Sauvegarder et publier"))

        self.helper.layout = Layout(
            Row(FullCol("name")),
            Row(FullCol("image")),
            Row(FullCol("image_accept_license")),
            Row(HalfCol("start_time"), HalfCol("end_time")),
            Row(HalfCol("as_group")),
            Section("Inscriptions", Row(FullCol("allow_guests"))),
            Section(
                _("Informations de contact"),
                Row(FullCol("contact_name")),
                Row(
                    HalfCol("contact_email"),
                    HalfCol("contact_phone", "contact_hide_phone"),
                ),
            ),
            Section(
                _("Lieu"),
                Row(
                    FullCol(
                        HTML(
                            "<p><b>Merci d'indiquer une adresse précise avec numéro de rue, sans quoi l'événement n'apparaîtra"
                            " pas sur la carte.</b>"
                            " Si les réunions se déroulent chez vous et que vous ne souhaitez pas rendre cette adresse"
                            " publique, vous pouvez indiquer un endroit à proximité, comme un café, ou votre mairie."
                        )
                    )
                ),
                Row(FullCol("location_name", css_class="col-md-12")),
                Row(
                    FullCol(
                        Field("location_address1", placeholder=_("1ère ligne")),
                        Field("location_address2", placeholder=_("2ème ligne")),
                    )
                ),
                Row(
                    Div("location_zip", css_class="col-md-4"),
                    Div("location_city", css_class="col-md-8"),
                ),
                Row(Div("location_country", css_class="col-md-12")),
            ),
            Row(FullCol("description")),
            *notify_field,
        )

        remove_excluded_field_from_layout(self.helper.layout, excluded_fields)

    def clean_start_time(self):
        start_time = self.cleaned_data["start_time"]

        if start_time < timezone.now():
            raise forms.ValidationError(
                _(
                    "Vos événements feraient mieux de se passer dans le futur ! Ce serait plus efficace…"
                )
            )

        return start_time

    def clean(self):
        cleaned_data = super().clean()

        if (
            self.is_creation
            and isinstance(cleaned_data["legal"], dict)
            and needs_approval(cleaned_data["legal"])
        ):
            self.instance.visibility = Event.VISIBILITY_ORGANIZER

        return cleaned_data

    def save(self, commit=True):
        res = super().save(commit)

        if commit:
            self.schedule_tasks()

        return res

    def _save_m2m(self):
        if self.is_creation:
            self.organizer_config = OrganizerConfig.objects.create(
                person=self.person,
                event=self.instance,
                as_group=self.cleaned_data["as_group"],
            )
            RSVP.objects.create(person=self.person, event=self.instance)
        elif self.organizer_config.as_group != self.cleaned_data["as_group"]:
            self.organizer_config.as_group = self.cleaned_data["as_group"]
            self.organizer_config.save()

    def schedule_tasks(self):
        super().schedule_tasks()

        # create set so that values are unique, but turns to list because set are not JSON-serializable
        changes = list(
            {
                self.CHANGES[field]
                for field in self.changed_data
                if field in self.CHANGES
            }
        )

        # if it's a new group creation, send the confirmation notification and geolocate it
        if self.is_creation:
            # membership attribute created by _save_m2m
            send_event_creation_notification.delay(self.organizer_config.pk)
            if self.organizer_config.event.visibility == Event.VISIBILITY_ORGANIZER:
                send_secretariat_notification.delay(
                    self.organizer_config.event.pk,
                    self.organizer_config.person.pk,
                    complete=False,
                )
        else:
            # send changes notification if the notify checkbox was checked
            if changes and self.cleaned_data.get("notify"):
                send_event_changed_notification.delay(self.instance.pk, changes)

    class Meta:
        model = Event
        fields = (
            "name",
            "image",
            "allow_guests",
            "start_time",
            "end_time",
            "contact_name",
            "contact_email",
            "contact_phone",
            "contact_hide_phone",
            "location_name",
            "location_address1",
            "location_address2",
            "location_city",
            "location_zip",
            "location_country",
            "description",
            "subtype",
            "legal",
        )


class RSVPChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return str(obj.person)


class AddOrganizerForm(forms.Form):
    form = forms.CharField(initial="add_organizer_form", widget=forms.HiddenInput())

    def __init__(self, event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event

        self.fields["organizer"] = RSVPChoiceField(
            queryset=event.rsvps.exclude(person__organized_events=event), label=False
        )

        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Ajouter comme co-organisateur")))

    def save(self, commit=True):
        rsvp = self.cleaned_data["organizer"]

        organizer_config = OrganizerConfig(event=rsvp.event, person=rsvp.person)

        if commit:
            organizer_config.save()

        return organizer_config


class EventGeocodingForm(GeocodingBaseForm):
    geocoding_task = geocode_event
    messages = {
        "use_geocoding": _(
            "La localisation de votre événement sur la carte va être réinitialisée à partir de son adresse."
            " Patientez quelques minutes pour voir la nouvelle localisation apparaître."
        ),
        "coordinates_updated": _(
            "La localisation de votre événement a été correctement mise à jour. Patientez quelques"
            " minutes pour la voir apparaître sur la carte."
        ),
    }

    class Meta:
        model = Event
        fields = ("coordinates",)


class EventReportForm(ImageFormMixin, forms.ModelForm):
    image_field = "image"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["report_image"].label = "Image de couverture (optionnelle)"

        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Sauvegarder et publier")))
        self.helper.layout = Layout(
            "report_content", "report_image", "image_accept_license"
        )

    class Meta:
        model = Event
        fields = ("report_image", "report_content")


class EventLegalForm(MetaFieldsMixin, forms.Form):
    meta_attr = "legal"
    meta_prefix = "documents_"
    filepath = "events_legal"

    sections = {
        "financing": ("Financement", ("financing", "budget", "bill_file")),
        "invited": ("Candidat⋅e⋅s et invité⋅e⋅s", ("invited",)),
        "hosting": (
            "Responsable hébergement militant",
            ("hosting_first_name", "hosting_last_name", "hosting_contact_phone"),
        ),
        "salle": (
            "Salle",
            (
                "salle",
                "salle_name",
                "salle_capacity",
                "salle_address",
                "salle_choice",
                "salle_file",
            ),
        ),
    }

    def __init__(self, instance, *args, **kwargs):
        self.instance = instance
        self.included_sections = []
        if self.instance.legal.get(legal.QUESTION_FRAIS):
            self.included_sections.append(self.sections["financing"])
        if self.instance.legal.get(legal.QUESTION_CANDIDAT):
            self.included_sections.append(self.sections["invited"])
            self.included_sections.append(self.sections["hosting"])
        if self.instance.legal.get(legal.QUESTION_SALLE):
            self.included_sections.append(self.sections["salle"])

        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Sauvegarder ces informations")))
        self.helper.layout = Layout(
            *(Section(section[0], *section[1]) for section in self.included_sections)
        )

        for field_name in list(self.fields.keys()):
            if field_name not in self.get_meta_fields():
                del self.fields[field_name]
                continue
            self.fields[field_name].required = False

        self.update_meta_initial()

    @property
    def incomplete_sections(self):
        return (
            section
            for section in self.included_sections
            if not set(section[1]).issubset(
                filter(
                    lambda x: x,
                    map(
                        lambda name: name.replace(self.meta_prefix, ""),
                        self.instance.legal,
                    ),
                )
            )
        )

    def get_meta_fields(self):
        return (field for section in self.included_sections for field in section[1])

    def save(self):
        self._save_files()
        self.instance.save()
        return self.instance

    financing = forms.ChoiceField(
        label="Mon événement...",
        choices=(
            ("dons", "...sera financé par des dons"),
            ("financé", "...rempli les critères, je demande donc son financement"),
        ),
    )
    budget = forms.IntegerField(label="Budget total (précis)")
    bill_file = forms.FileField(label="Devis", widget=forms.ClearableFileInput())

    hosting_first_name = forms.CharField(label="Prénom", max_length=255)
    hosting_last_name = forms.CharField(label="Nom", max_length=255)
    hosting_contact_phone = PhoneNumberField(label="Numéro de téléphone")

    invited = forms.CharField(
        label="Noms des invité⋅e⋅s",
        help_text="Indiquez le nom complet de chaque candidat⋅e, un par ligne",
        widget=forms.Textarea(attrs={"rows": "5"}),
    )

    salle = forms.ChoiceField(
        choices=(("gratuite", "gratuite"), ("payante", "payante")),
        label="La salle choisie est",
    )
    salle_capacity = forms.IntegerField(
        label="Capacité de la salle", help_text="En nombre de personnes"
    )
    salle_name = forms.CharField(label="Nom de la salle")
    salle_address = forms.CharField(
        label="Adresse", widget=forms.Textarea(attrs={"rows": "5"})
    )
    salle_choice = forms.CharField(
        label="Pourquoi ce choix de salle ?", widget=forms.Textarea(attrs={"rows": "5"})
    )
    salle_file = forms.FileField(
        label="Attestation de gratuité de la salle, ou devis s'il s'agit d'une salle payante",
        widget=forms.ClearableFileInput(),
    )


class UploadEventImageForm(forms.ModelForm):
    accept_license = AcceptCreativeCommonsLicenceField(required=True)

    def __init__(self, *args, author=None, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if author is not None:
            self.instance.author = author
        if event is not None:
            self.instance.event = event

        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Ajouter mon image")))
        self.helper.form_tag = False
        self.helper.layout = Layout("image", "accept_license", "legend")

    class Meta:
        model = EventImage
        fields = ("image", "legend")


class SearchEventForm(SearchByZipCodeFormBase):
    pass


class AuthorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["first_name"].required = self.fields["last_name"].required = True
        self.fields["last_name"].help_text = _(
            """
        Nous avons besoin de votre nom pour pouvoir vous identifier comme l'auteur de l'image.
        """
        )

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout("first_name", "last_name")

    class Meta:
        model = Person
        fields = ("first_name", "last_name")


class BillingForm(forms.ModelForm):
    # these fields are used to make sure there's no problem if user starts paying several events at the same time
    event = forms.ModelChoiceField(
        Event.objects.all(), required=True, widget=forms.HiddenInput
    )
    submission = forms.ModelChoiceField(
        PersonFormSubmission.objects.all(), widget=forms.HiddenInput, required=False
    )
    payment_mode = PaymentModeField(required=True)
    is_guest = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, event, submission, is_guest, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["submission"].initial = submission
        self.fields["event"].initial = event
        self.fields["is_guest"].initial = is_guest

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

        fields = ["submission", "event", "is_guest"]

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

        fields.append("payment_mode")

        self.helper = FormHelper()
        self.helper.add_input(
            layout.Submit(
                "valider",
                f"Je paie {floatformat(event.get_price(submission and submission.data)/100, 2)} €",
            )
        )
        self.helper.layout = layout.Layout(*fields)

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
        )


class GuestsForm(forms.Form):
    guests = forms.IntegerField()


class BaseRSVPForm(BasePersonForm):
    is_guest = forms.BooleanField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, is_guest=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["is_guest"].initial = is_guest
        self.helper.layout.append("is_guest")


class ExternalRSVPForm(forms.Form):
    email = forms.EmailField()

    def send_confirmation_email(self, event):
        send_external_rsvp_confirmation.delay(event.pk, **self.cleaned_data)
