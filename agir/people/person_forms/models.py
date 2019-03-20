from collections import OrderedDict
from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django_prometheus.models import ExportModelOperationsMixin

from agir.lib.form_fields import CustomJSONEncoder
from agir.lib.models import DescriptionField, TimeStampedModel

__all__ = ["PersonForm", "PersonFormSubmission"]


class PersonFormQueryset(models.QuerySet):
    def published(self):
        return self.filter(models.Q(published=True))

    def open(self):
        now = timezone.now()
        return self.published().filter(
            (models.Q(start_time__isnull=True) | models.Q(start_time__lt=now))
            & (models.Q(end_time__isnull=True) | models.Q(end_time__gt=now))
        )


def default_custom_forms():
    return [
        {
            "title": "Mes informations",
            "fields": [
                {"id": "first_name", "person_field": True},
                {"id": "last_name", "person_field": True},
            ],
        }
    ]


class PersonForm(TimeStampedModel):
    objects = PersonFormQueryset.as_manager()

    title = models.CharField(_("Titre"), max_length=250)
    slug = models.SlugField(_("Slug"), max_length=50)
    published = models.BooleanField(_("Publié"), default=True)

    start_time = models.DateTimeField(
        _("Date d'ouverture du formulaire"), null=True, blank=True
    )
    end_time = models.DateTimeField(
        _("Date de fermeture du formulaire"), null=True, blank=True
    )

    editable = models.BooleanField(
        _("Les répondant⋅e⋅s peuvent modifier leurs réponses"), default=False
    )

    send_answers_to = models.EmailField(
        _("Envoyer les réponses par email à une adresse email (facultatif)"), blank=True
    )

    description = DescriptionField(
        _("Description"),
        allowed_tags=settings.ADMIN_ALLOWED_TAGS,
        help_text=_(
            "Description visible en haut de la page de remplissage du formulaire"
        ),
    )

    send_confirmation = models.BooleanField(
        _("Envoyer une confirmation par email"), default=False
    )

    confirmation_note = DescriptionField(
        _("Note après complétion"),
        allowed_tags=settings.ADMIN_ALLOWED_TAGS,
        help_text=_(
            "Note montrée (et éventuellement envoyée par email) à l'utilisateur une fois le formulaire validé."
        ),
    )
    before_message = DescriptionField(
        _("Note avant ouverture"),
        allowed_tags=settings.ADMIN_ALLOWED_TAGS,
        help_text=_(
            "Note montrée à l'utilisateur qui essaye d'accéder au formulaire avant son ouverture."
        ),
        blank=True,
    )

    after_message = DescriptionField(
        _("Note de fermeture"),
        allowed_tags=settings.ADMIN_ALLOWED_TAGS,
        help_text=_(
            "Note montrée à l'utilisateur qui essaye d'accéder au formulaire après sa date de fermeture."
        ),
        blank=True,
    )

    required_tags = models.ManyToManyField(
        "PersonTag",
        related_name="authorized_forms",
        related_query_name="authorized_form",
        blank=True,
    )

    unauthorized_message = DescriptionField(
        _("Note pour les personnes non autorisées"),
        allowed_tags=settings.ADMIN_ALLOWED_TAGS,
        help_text=_(
            "Note montrée à tout utilisateur qui n'aurait pas le tag nécessaire pour afficher le formulaire."
        ),
        blank=True,
    )

    main_question = models.CharField(
        _("Intitulé de la question principale"),
        max_length=200,
        help_text=_("Uniquement utilisée si des choix de tags sont demandés."),
        blank=True,
    )
    tags = models.ManyToManyField(
        "PersonTag", related_name="forms", related_query_name="form", blank=True
    )

    custom_fields = JSONField(_("Champs"), blank=False, default=default_custom_forms)

    @property
    def fields_dict(self):
        return OrderedDict(
            (field["id"], field)
            for fieldset in self.custom_fields
            for field in fieldset["fields"]
        )

    @property
    def is_open(self):
        now = timezone.now()
        return (self.start_time is None or self.start_time < now) and (
            self.end_time is None or now < self.end_time
        )

    def is_authorized(self, person):
        return bool(
            not self.required_tags.all()
            or (person.tags.all() & self.required_tags.all())
        )

    @property
    def html_closed_message(self):
        now = timezone.now()
        if self.start_time is not None and self.start_time > now:
            if self.before_message:
                return self.html_before_message()
            else:
                return "Ce formulaire n'est pas encore ouvert."
        else:
            if self.after_message:
                return self.html_after_message()
            else:
                return "Ce formulaire est maintenant fermé."

    def __str__(self):
        return "« {} »".format(self.title)

    class Meta:
        verbose_name = _("Formulaire")


class PersonFormSubmission(
    ExportModelOperationsMixin("person_form_submission"), TimeStampedModel
):
    form = models.ForeignKey(
        "PersonForm",
        on_delete=models.CASCADE,
        related_name="submissions",
        editable=False,
    )
    person = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="form_submissions",
        editable=False,
    )

    data = JSONField(
        _("Données"), default=dict, editable=False, encoder=CustomJSONEncoder
    )

    def __str__(self):
        return f"{self.form.title} : réponse de {str(self.person)}"
