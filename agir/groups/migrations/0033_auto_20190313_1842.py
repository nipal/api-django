# Generated by Django 2.1.7 on 2019-03-13 17:42

from django.db import migrations
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [("groups", "0032_auto_20190128_1550")]

    operations = [
        migrations.AlterField(
            model_name="supportgroup",
            name="location_country",
            field=django_countries.fields.CountryField(
                blank=True, default="FR", max_length=2, verbose_name="pays"
            ),
        )
    ]
