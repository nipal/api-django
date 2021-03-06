# Generated by Django 2.0.6 on 2018-07-19 14:55

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0035_auto_20180719_1655"),
        ("polls", "0007_auto_20180601_1535"),
    ]

    operations = [
        migrations.AddField(
            model_name="pollchoice",
            name="anonymous_id",
            field=models.UUIDField(
                default=uuid.uuid4, verbose_name="Identifiant anonyme"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="pollchoice", unique_together={("person", "poll")}
        ),
    ]
