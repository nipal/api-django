# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-10-03 13:54
from __future__ import unicode_literals

from django.db import migrations
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    dependencies = [("people", "0013_format_phones_to_E164")]

    operations = [
        migrations.AlterField(
            model_name="person",
            name="contact_phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                max_length=128,
                verbose_name="Numéro de téléphone de contact",
            ),
        )
    ]
