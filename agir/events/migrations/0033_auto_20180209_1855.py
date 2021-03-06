# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-09 17:55
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models
import django.utils.timezone
from agir.events import models as events_models


class Migration(migrations.Migration):

    dependencies = [("events", "0032_add_subtypes")]

    operations = [
        migrations.AlterModelOptions(
            name="eventsubtype",
            options={
                "verbose_name": "Sous-type d'événement",
                "verbose_name_plural": "Sous-types d'événement",
            },
        ),
        migrations.RemoveField(model_name="eventsubtype", name="popup_anchor_x"),
        migrations.AddField(
            model_name="eventsubtype",
            name="created",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                editable=False,
                verbose_name="created",
            ),
        ),
        migrations.AddField(
            model_name="eventsubtype",
            name="modified",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                editable=False,
                verbose_name="modified",
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="subtype",
            field=models.ForeignKey(
                default=events_models.get_default_subtype,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="events.EventSubtype",
            ),
        ),
        migrations.AlterField(
            model_name="eventsubtype",
            name="color",
            field=models.CharField(
                blank=True,
                help_text="La couleur associée aux marqueurs sur la carte.",
                max_length=7,
                validators=[
                    django.core.validators.RegexValidator(regex="^#[0-9a-f]{6}$")
                ],
                verbose_name="couleur",
            ),
        ),
        migrations.AlterField(
            model_name="eventsubtype",
            name="icon_anchor_x",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="ancre de l'icône (x)"
            ),
        ),
        migrations.AlterField(
            model_name="eventsubtype",
            name="icon_anchor_y",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="ancre de l'icône (y)"
            ),
        ),
        migrations.AlterField(
            model_name="eventsubtype",
            name="popup_anchor_y",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="placement de la popup (par rapport au point)",
            ),
        ),
    ]
