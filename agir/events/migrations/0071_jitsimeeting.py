# Generated by Django 2.2 on 2019-05-09 11:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("events", "0070_auto_20190313_1842")]

    operations = [
        migrations.CreateModel(
            name="JitsiMeeting",
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
                ("domain", models.CharField(max_length=255)),
                ("room_name", models.CharField(max_length=255, unique=True)),
                (
                    "start_time",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Début effectif"
                    ),
                ),
                (
                    "end_time",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Fin effective"
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="events.Event",
                    ),
                ),
            ],
            options={"verbose_name": "Visio-conférence"},
        )
    ]
