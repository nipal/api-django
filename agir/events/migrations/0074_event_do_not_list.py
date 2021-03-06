# Generated by Django 2.2 on 2019-05-27 17:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("events", "0073_event_participation_template")]

    operations = [
        migrations.AddField(
            model_name="event",
            name="do_not_list",
            field=models.BooleanField(
                default=False,
                help_text="L'événement n'apparaîtra pas sur la carte, ni sur le calendrier et ne sera pas cherchable via la recherche interne ou les moteurs de recherche.",
                verbose_name="Ne pas lister l'événement",
            ),
        )
    ]
