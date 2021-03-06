# Generated by Django 2.2 on 2019-05-21 15:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("people", "0055_personform_result_url_uuid")]

    operations = [
        migrations.AddField(
            model_name="personform",
            name="allow_anonymous",
            field=models.BooleanField(
                default=False,
                verbose_name="Les répondant⋅es n'ont pas besoin d'être connecté⋅es",
            ),
        ),
        migrations.AlterField(
            model_name="personformsubmission",
            name="person",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="form_submissions",
                to="people.Person",
            ),
        ),
    ]
