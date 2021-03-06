# Generated by Django 2.1.2 on 2018-10-04 10:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("people", "0040_auto_20181019_1641")]

    operations = [
        migrations.AlterField(
            model_name="person",
            name="draw_participation",
            field=models.BooleanField(
                blank=True,
                default=False,
                help_text="Vous pourrez être tiré⋅e au sort parmis les Insoumis⋅es pour participer à des événements comme la Convention.Vous aurez la possibilité d'accepter ou de refuser cette participation.",
                verbose_name="Participer aux tirages au sort",
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="event_notifications",
            field=models.BooleanField(
                blank=True,
                default=True,
                help_text="Vous recevrez des messages quand les informations des évènements auxquels vous souhaitez participer sont mis à jour ou annulés.",
                verbose_name="Recevoir les notifications des événements",
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="group_notifications",
            field=models.BooleanField(
                blank=True,
                default=True,
                help_text="Vous recevrez des messages quand les informations du groupe change, ou quand le groupe organise des événements.",
                verbose_name="Recevoir les notifications de mes groupes",
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="subscribed",
            field=models.BooleanField(
                blank=True,
                default=True,
                help_text="Vous recevrez les lettres de la France insoumise, notamment : les lettres d'information, les appels à volontaires, les annonces d'émissions ou d'événements...",
                verbose_name="Recevoir les lettres d'information",
            ),
        ),
    ]
