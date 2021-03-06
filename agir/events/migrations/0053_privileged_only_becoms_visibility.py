# Generated by Django 2.1.2 on 2018-10-08 09:22

from django.db import migrations, models


def privileged_to_visibility(apps, schema):
    EventSubtype = apps.get_model("events", "EventSubtype")

    EventSubtype.objects.update(
        visibility=models.Case(
            models.When(privileged_only=True, then=models.Value("D")),
            default=models.Value("A"),
        )
    )


def visibility_to_privileged(apps, schema):
    EventSubtype = apps.get_model("events", "EventSubtype")

    EventSubtype.objects.update(
        privileged_only=models.Case(
            models.When(visibility="A", then=False), default=True
        )
    )


class Migration(migrations.Migration):

    dependencies = [("events", "0052_auto_20180622_1621")]

    operations = [
        migrations.AddField(
            model_name="eventsubtype",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("N", "Personne (plus utilisé)"),
                    ("D", "Seulement depuis l'administration"),
                    ("A", "N'importe qui"),
                ],
                default="D",
                max_length=1,
                verbose_name="Qui peut créer avec ce sous-type ?",
            ),
        ),
        migrations.RunPython(
            code=privileged_to_visibility, reverse_code=visibility_to_privileged
        ),
        migrations.RemoveField(model_name="eventsubtype", name="privileged_only"),
    ]
