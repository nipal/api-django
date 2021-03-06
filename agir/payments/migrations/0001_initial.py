# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-04-17 10:48
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.utils.timezone
import django_countries.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [("people", "0029_person_mandates")]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "coordinates",
                    django.contrib.gis.db.models.fields.PointField(
                        blank=True,
                        geography=True,
                        null=True,
                        srid=4326,
                        verbose_name="coordonnées",
                    ),
                ),
                (
                    "coordinates_type",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Coordonnées manuelles"),
                            (10, "Coordonnées automatiques précises"),
                            (
                                20,
                                "Coordonnées automatiques approximatives (niveau rue)",
                            ),
                            (30, "Coordonnées automatiques approximatives (ville)"),
                            (50, "Coordonnées automatiques (qualité inconnue)"),
                            (255, "Coordonnées introuvables"),
                        ],
                        editable=False,
                        help_text="Comment les coordonnées ci-dessus ont-elle été acquises",
                        null=True,
                        verbose_name="type de coordonnées",
                    ),
                ),
                (
                    "location_name",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="nom du lieu"
                    ),
                ),
                (
                    "location_address1",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="adresse (1ère ligne)"
                    ),
                ),
                (
                    "location_address2",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="adresse (2ème ligne)"
                    ),
                ),
                (
                    "location_city",
                    models.CharField(blank=True, max_length=100, verbose_name="ville"),
                ),
                (
                    "location_zip",
                    models.CharField(
                        blank=True, max_length=20, verbose_name="code postal"
                    ),
                ),
                (
                    "location_state",
                    models.CharField(blank=True, max_length=40, verbose_name="état"),
                ),
                (
                    "location_country",
                    django_countries.fields.CountryField(
                        blank=True, max_length=2, verbose_name="pays"
                    ),
                ),
                (
                    "location_address",
                    models.CharField(
                        blank=True,
                        help_text="L'adresse telle qu'elle a éventuellement été copiée depuis NationBuilder. Ne plus utiliser.",
                        max_length=255,
                        verbose_name="adresse complète",
                    ),
                ),
                ("email", models.EmailField(max_length=255, verbose_name="email")),
                ("first_name", models.CharField(max_length=255, verbose_name="prénom")),
                (
                    "last_name",
                    models.CharField(max_length=255, verbose_name="nom de famille"),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("don", "don"),
                            ("inscription à un événement", "événement"),
                        ],
                        max_length=255,
                        verbose_name="type",
                    ),
                ),
                ("price", models.IntegerField(verbose_name="prix en centimes d'euros")),
                (
                    "status",
                    models.IntegerField(
                        choices=[
                            (0, "En attente"),
                            (1, "Terminé"),
                            (2, "Abandonné"),
                            (3, "Annulé"),
                            (4, "Refusé"),
                        ],
                        default=0,
                        verbose_name="status",
                    ),
                ),
                (
                    "meta",
                    django.contrib.postgres.fields.jsonb.JSONField(
                        blank=True, default=dict
                    ),
                ),
                (
                    "systempay_responses",
                    django.contrib.postgres.fields.jsonb.JSONField(
                        blank=True, default=list
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="people.Person"
                    ),
                ),
            ],
            options={"abstract": False},
        )
    ]
