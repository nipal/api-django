# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-17 19:04
from __future__ import unicode_literals

from django.db import migrations, models
import stdimage.models
import stdimage.utils


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0009_rename_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportgroup',
            name='allow_html',
            field=models.BooleanField(default=False, verbose_name='autoriser le HTML dans la description'),
        ),
        migrations.AddField(
            model_name='supportgroup',
            name='image',
            field=stdimage.models.StdImageField(blank=True, help_text="L'image à utiliser pour l'affichage sur la page, comme miniature dans les listes, et pour le partage sur les réseaux sociaux. Elle doit faire au minimum 1200 pixels de large, et 630 de haut. Préférer un rapport largeur/hauteur de 2 (deux fois plus large que haut)?", upload_to=stdimage.utils.UploadToAutoSlugClassNameDir('name', path='banners'), verbose_name='image'),
        ),
        migrations.AddField(
            model_name='supportgroup',
            name='type',
            field=models.CharField(choices=[('L', 'Groupe local'), ('B', 'Livret thématique')], default='L', max_length=1, verbose_name='type de groupe'),
        ),
    ]