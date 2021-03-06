from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import ugettext as _

from agir.api.admin import admin_site
from agir.lib.form_fields import AdminJsonWidget

from .models import Poll, PollOption
from agir.lib.utils import front_url


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 1


class PollAdminForm(forms.ModelForm):
    class Meta:
        widgets = {"rules": AdminJsonWidget()}


@admin.register(Poll, site=admin_site)
class PollAdmin(admin.ModelAdmin):
    form = PollAdminForm
    inlines = [PollOptionInline]

    fields = ["title", "link", "description", "start", "end", "rules", "tags"]
    readonly_fields = ["link"]

    def link(self, object):
        if object.pk:
            return format_html(
                '<a href="{url}">{text}</a>',
                url=front_url("participate_poll", args=[object.pk]),
                text=_("Voir la consultation"),
            )
