from itertools import chain

from django.utils.text import capfirst
from functools import reduce

import iso8601
from django.conf import settings
from django.urls import reverse
from django.utils.formats import localize
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import get_current_timezone
from operator import or_
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers import NumberParseException

from agir.people.models import Person, PersonForm
from agir.people.person_forms.fields import (
    PREDEFINED_CHOICES,
    PREDEFINED_CHOICES_REVERSE,
)
from agir.people.person_forms.models import PersonFormSubmission

NA_HTML_PLACEHOLDER = mark_safe('<em style="color: #999;">N/A</em>')
NA_TEXT_PLACEHOLDER = "N/A"
ADMIN_FIELDS_LABELS = ["ID", "Personne", "Date de la réponse"]
PUBLIC_FORMATS = {
    "bold": "<strong>{}</strong>",
    "italic": "<em>{}</em>",
    "normal": "{}",
}


def _get_choice_label(field_descriptor, value, html=False):
    """Renvoie le libellé correct pour un champ de choix

    :param field_descriptor: le descripteur du champ
    :param value: la valeur prise par le champ
    :param html: s'il faut inclure du HTML ou non
    :return:
    """
    if isinstance(field_descriptor["choices"], str):
        if callable(PREDEFINED_CHOICES.get(field_descriptor["choices"])):
            value = PREDEFINED_CHOICES_REVERSE.get(field_descriptor["choices"])(value)
            if hasattr(value, "get_absolute_url") and html:
                return format_html(
                    '<a href="{0}">{1}</a>', value.get_absolute_url(), str(value)
                )
            return str(value)
        choices = PREDEFINED_CHOICES.get(field_descriptor["choices"])
    else:
        choices = field_descriptor["choices"]
    try:
        return next(label for id, label in choices if id == value)
    except StopIteration:
        return value


def _get_formatted_value(field, value, html=True, na_placeholder=None):
    """Récupère la valeur du champ pour les humains

    :param field:
    :param value:
    :param html:
    :param na_placeholder: la valeur à présenter pour les champs vides
    :return:
    """

    if value is None:
        if na_placeholder is not None:
            return na_placeholder
        elif html:
            return NA_HTML_PLACEHOLDER
        return NA_TEXT_PLACEHOLDER

    field_type = field.get("type")

    if field_type == "choice" and "choices" in field:
        return _get_choice_label(field, value, html)
    elif field_type == "multiple_choice" and "choices" in field:
        if isinstance(value, list):
            return [_get_choice_label(field, v, html) for v in value]
        else:
            return value
    elif field_type == "date":
        date = iso8601.parse_date(value)
        return localize(date.astimezone(get_current_timezone()))
    elif field_type == "phone_number":
        try:
            phone_number = PhoneNumber.from_string(value)
            return phone_number.as_international
        except NumberParseException:
            return value
    elif field_type == "file":
        url = settings.FRONT_DOMAIN + settings.MEDIA_URL + value
        if html:
            return format_html('<a href="{}">Accéder au fichier</a>', url)
        else:
            return url

    return value


def _get_admin_fields(submission, html=True):
    return [
        format_html(
            '<a href="{}" title="Supprimer cette submission">&#x274c;</a>&ensp;'
            '<a href="{}" title="Voir le détail">&#128269;</a>&ensp;{}',
            reverse("admin:people_personformsubmission_delete", args=(submission.pk,)),
            reverse("admin:people_personformsubmission_detail", args=(submission.pk,)),
            submission.pk,
        )
        if html
        else submission.pk,
        format_html(
            '<a href="{}">{}</a>',
            settings.API_DOMAIN
            + reverse("admin:people_person_change", args=(submission.person_id,)),
            submission.person.email,
        )
        if html
        else submission.person.email,
        localize(submission.created.astimezone(get_current_timezone())),
    ]


def get_form_field_labels(form, fieldsets_titles=False):
    """Renvoie un dictionnaire associant id de champs et libellés à présenter

    Prend en compte tous les cas de figure :
    - champs dans le libellé est défini explicitement
    - champs de personnes dont le libellé n'est pas reprécisé...
    - etc.

    :param form:
    :param fieldsets_titles:
    :return:
    """
    field_information = {}

    person_fields = {f.name: f for f in Person._meta.get_fields()}

    for fieldset in form.custom_fields:
        for field in fieldset["fields"]:
            if field.get("person_field") and field["id"] in person_fields:
                label = field.get(
                    "label",
                    capfirst(
                        getattr(
                            person_fields[field["id"]],
                            "verbose_name",
                            person_fields[field["id"]].name,
                        )
                    ),
                )
            else:
                label = field["label"]

            field_information[field["id"]] = (
                format_html(
                    "{title}&nbsp;:<br>{label}", title=fieldset["title"], label=label
                )
                if fieldsets_titles
                else label
            )

    return field_information


def get_formatted_submissions(
    submissions_or_form,
    html=True,
    include_admin_fields=True,
    resolve_labels=True,
    fieldsets_titles=False,
):
    if isinstance(submissions_or_form, PersonForm):
        form = submissions_or_form
        submissions = form.submissions.all().order_by("created")

    else:
        if not submissions_or_form:
            return [], []

        submissions = submissions_or_form
        form = submissions[0].form

    field_dict = form.fields_dict

    labels = (
        get_form_field_labels(form, fieldsets_titles=fieldsets_titles)
        if resolve_labels
        else {}
    )

    full_data = [sub.data for sub in submissions]
    full_values = [
        {
            id: _get_formatted_value(field_dict[id], value, html)
            if id in field_dict
            else value
            for id, value in d.items()
        }
        for d in full_data
    ]

    declared_fields = set(field_dict)
    additional_fields = sorted(
        reduce(or_, (set(d) for d in full_data)).difference(declared_fields)
    )

    headers = [labels.get(id, id) for id in field_dict] + additional_fields

    ordered_values = [
        [
            v.get(i, NA_HTML_PLACEHOLDER if html else NA_TEXT_PLACEHOLDER)
            for i in chain(field_dict, additional_fields)
        ]
        for v in full_values
    ]

    if include_admin_fields:
        admin_values = [_get_admin_fields(s, html) for s in submissions]
        return (
            ADMIN_FIELDS_LABELS + headers,
            [
                admin_values + values
                for admin_values, values in zip(admin_values, ordered_values)
            ],
        )

    return headers, ordered_values


def get_formatted_submission(submission, include_admin_fields=False):
    data = submission.data
    field_dicts = submission.form.fields_dict
    labels = get_form_field_labels(submission.form)

    if include_admin_fields:
        res = [
            {
                "title": "Administration",
                "data": [
                    {"label": l, "value": v}
                    for l, v in zip(ADMIN_FIELDS_LABELS, _get_admin_fields(submission))
                ],
            }
        ]
    else:
        res = []

    for fieldset in submission.form.custom_fields:
        fieldset_data = []
        for field in fieldset["fields"]:
            id = field["id"]
            if id in data:
                label = labels[id]
                value = _get_formatted_value(field, data.get(id))
                fieldset_data.append({"label": label, "value": value})
        res.append({"title": fieldset["title"], "data": fieldset_data})

    missing_fields = set(data).difference(set(field_dicts))

    missing_fields_data = []
    for id in sorted(missing_fields):
        missing_fields_data.append({"label": id, "value": data[id]})
    if len(missing_fields_data) > 0:
        res.append({"title": "Champs inconnus", "data": missing_fields_data})

    return res


def _get_full_public_fields_definition(form):
    public_config = form.config.get("public", [])
    field_names = get_form_field_labels(form)

    return [
        {
            "id": f["id"],
            "label": f.get("label", field_names[f["id"]]),
            "format": f.get("format", "normal"),
        }
        for f in public_config
    ]


def get_public_fields(submissions):
    if not submissions:
        return []

    only_one = False

    if isinstance(submissions, PersonFormSubmission):
        only_one = True
        submissions = [submissions]

    field_dict = submissions[0].form.fields_dict
    public_fields_definition = _get_full_public_fields_definition(submissions[0].form)

    public_submissions = []

    for submission in submissions:
        public_submissions.append(
            {
                "date": submission.created,
                "values": [
                    {
                        "label": pf["label"],
                        "value": format_html(
                            PUBLIC_FORMATS[pf["format"]],
                            _get_formatted_value(
                                field_dict[pf["id"]], submission.data.get(pf["id"])
                            ),
                        ),
                    }
                    for pf in public_fields_definition
                ],
            }
        )

    if only_one:
        return public_submissions[0]

    return public_submissions
