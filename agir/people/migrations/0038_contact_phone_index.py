# Generated by Django 2.0.8 on 2018-09-19 14:11

import agir.people.model_fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("people", "0037_personvalidationsms")]

    operations = [
        migrations.AlterField(
            model_name="person",
            name="contact_phone",
            field=agir.people.model_fields.ValidatedPhoneNumberField(
                blank=True,
                max_length=128,
                unverified_value="U",
                validated_field_name="contact_phone_status",
                verbose_name="Numéro de téléphone de contact",
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="contact_phone_status",
            field=models.CharField(
                choices=[
                    ("U", "Non vérifié"),
                    ("V", "Vérifié"),
                    ("P", "En attente de validation manuelle"),
                ],
                default="U",
                max_length=1,
                verbose_name="Statut du numéro de téléphone",
            ),
        ),
        migrations.AddIndex(
            model_name="person",
            index=models.Index(fields=["contact_phone"], name="contact_phone_index"),
        ),
    ]
