from django.core import checks
from django.db import models
from django.utils.itercompat import is_iterable
from django.utils.translation import ugettext_lazy as _

from agir.donations.validators import validate_iban
from agir.lib.form_fields import IBANField as FormIBANField
from agir.lib.iban import to_iban, IBAN


class IBANFieldDescriptor:
    def __init__(self, field):
        self.field = field

    def __get__(self, instance=None, owner=None):
        if instance is None:
            return self
        return instance.__dict__[self.field.name]

    def __set__(self, instance, value):
        instance.__dict__[self.field.name] = to_iban(value)


class IBANField(models.Field):
    description = _("IBAN identifiant un compte un banque")
    descriptor_class = IBANFieldDescriptor

    default_validators = [validate_iban]

    def __init__(self, *args, allowed_countries=None, **kwargs):
        self.allowed_countries = allowed_countries
        kwargs["max_length"] = 34

        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["allowed_countries"] = self.allowed_countries

        return name, path, args, kwargs

    def get_internal_type(self):
        return "CharField"

    def to_python(self, value):
        return to_iban(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        value = self.to_python(value)

        if isinstance(value, IBAN):
            return value.as_stored_value
        return value

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": FormIBANField,
                "allowed_countries": self.allowed_countries,
                **kwargs,
            }
        )

    def contribute_to_class(self, cls, name, private_only=False):
        super().contribute_to_class(cls, name, private_only)
        setattr(cls, name, self.descriptor_class(self))

    def _check_allowed_countries(self):
        if not self.allowed_countries:
            return []

        if not is_iterable(self.allowed_countries):
            return [
                checks.Error(
                    "'allowed_countries' must be an iterable (e.g. a list or tuple)",
                    obj=self,
                    id="agir.lib.E001",
                )
            ]

        if not all(isinstance(s, str) and len(s) == 2 for s in self.allowed_countries):
            return [
                checks.Error(
                    "'allowed_countries' must be an iterable containing 2-letters country codes",
                    obj=self,
                    id="agir.lib.E002",
                )
            ]

        return []

    def check(self, **kwargs):
        return [*super().check(), *self._check_allowed_countries()]
