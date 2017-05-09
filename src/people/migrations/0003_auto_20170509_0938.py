# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-09 09:38
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0002_auto_20170505_1307'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='person',
            name='coordinates_lat',
        ),
        migrations.RemoveField(
            model_name='person',
            name='coordinates_lon',
        ),
        migrations.AddField(
            model_name='person',
            name='coordinates',
            field=django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326, verbose_name='coordonnées'),
        ),
    ]
