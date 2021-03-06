from datetime import timedelta

from django.conf import settings
from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from django.db.models import Count, Q, QuerySet
from django.db.models.expressions import RawSQL
from django.urls import path
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from functools import partial, update_wrapper

from agir.api.admin import admin_site
from agir.events.models import Event
from agir.lib.admin import CenterOnFranceMixin, DepartementListFilter, RegionListFilter
from agir.lib.display import display_price
from agir.lib.utils import front_url
from . import actions
from . import views
from .forms import SupportGroupAdminForm
from .. import models
from ..actions.promo_codes import get_next_promo_code


class MembershipInline(admin.TabularInline):
    model = models.Membership
    fields = ("person_link", "is_referent", "is_manager")
    readonly_fields = ("person_link",)

    def person_link(self, obj):
        return mark_safe(
            '<a href="%s">%s</a>'
            % (
                reverse("admin:people_person_change", args=(obj.person.id,)),
                escape(obj.person.email),
            )
        )

    person_link.short_description = _("Personne")

    def has_add_permission(self, request):
        return False


class GroupHasEventsFilter(admin.SimpleListFilter):
    title = _("Événements organisés dans les 2 mois précédents ou mois à venir")

    parameter_name = "is_active"

    def lookups(self, request, model_admin):
        return (("yes", _("Oui")), ("no", _("Non")))

    def queryset(self, request, queryset):
        queryset = queryset.annotate(
            current_events_count=Count(
                "organized_events",
                filter=Q(
                    organized_events__start_time__range=(
                        timezone.now() - timedelta(days=62),
                        timezone.now() + timedelta(days=31),
                    ),
                    organized_events__visibility=Event.VISIBILITY_PUBLIC,
                ),
            )
        )
        if self.value() == "yes":
            return queryset.exclude(current_events_count=0)
        if self.value() == "no":
            return queryset.filter(current_events_count=0)


@admin.register(models.SupportGroup, site=admin_site)
class SupportGroupAdmin(CenterOnFranceMixin, OSMGeoAdmin):
    form = SupportGroupAdminForm
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "name",
                    "link",
                    "created",
                    "modified",
                    "action_buttons",
                    "promo_code",
                    "allocation",
                )
            },
        ),
        (
            _("Informations"),
            {
                "fields": (
                    "type",
                    "subtypes",
                    "description",
                    "allow_html",
                    "image",
                    "tags",
                    "published",
                )
            },
        ),
        (
            _("Lieu"),
            {
                "fields": (
                    "location_name",
                    "location_address1",
                    "location_address2",
                    "location_city",
                    "location_zip",
                    "location_state",
                    "location_country",
                    "coordinates",
                    "coordinates_type",
                    "redo_geocoding",
                )
            },
        ),
        (
            _("Contact"),
            {
                "fields": (
                    "contact_name",
                    "contact_email",
                    "contact_phone",
                    "contact_hide_phone",
                )
            },
        ),
        (_("NationBuilder"), {"fields": ("nb_id", "nb_path", "location_address")}),
    )
    inlines = (MembershipInline,)
    readonly_fields = (
        "id",
        "link",
        "action_buttons",
        "created",
        "modified",
        "coordinates_type",
        "promo_code",
        "allocation",
    )
    date_hierarchy = "created"

    list_display = (
        "name",
        "type",
        "published",
        "location_short",
        "membership_count",
        "created",
        "referent",
        "allocation",
    )
    list_filter = (
        "published",
        GroupHasEventsFilter,
        DepartementListFilter,
        RegionListFilter,
        "coordinates_type",
        "type",
        "subtypes",
        "tags",
    )

    search_fields = ("name", "description", "location_city", "location_country")
    actions = (actions.export_groups, actions.make_published, actions.unpublish)

    def promo_code(self, object):
        if object.pk and object.tags.filter(label=settings.PROMO_CODE_TAG).exists():
            return get_next_promo_code(object)
        else:
            return "-"

    promo_code.short_description = _("Code promo du mois")

    def referent(self, object):
        referent = object.memberships.filter(is_referent=True).first()
        if referent:
            return referent.person.email

        return ""

    referent.short_description = _("Animateurice")

    def location_short(self, object):
        return _("{zip} {city}, {country}").format(
            zip=object.location_zip,
            city=object.location_city,
            country=object.location_country.name,
        )

    location_short.short_description = _("Lieu")
    location_short.admin_order_field = "location_zip"

    def membership_count(self, object):
        return format_html(
            _('{nb} (<a href="{link}">Ajouter un membre</a>)'),
            nb=object.membership_count,
            link=reverse("admin:groups_supportgroup_add_member", args=(object.pk,)),
        )

    membership_count.short_description = _("Nombre de membres")
    membership_count.admin_order_field = "membership_count"

    def allocation(self, object, show_add_button=False):
        value = display_price(object.allocation) if object.allocation else "-"

        if show_add_button:
            value = format_html(
                '{value} (<a href="{link}">Changer</a>)',
                value=value,
                link=reverse("admin:donations_operation_add")
                + "?group="
                + str(object.pk),
            )

        return value

    allocation.short_description = _("Allocation")
    allocation.admin_order_field = "allocation"

    def link(self, object):
        if object.pk:
            return format_html(
                '<a href="{0}">{0}</a>',
                front_url("view_group", kwargs={"pk": object.pk}),
            )
        else:
            return mark_safe("-")

    link.short_description = _("Page sur le site")

    def action_buttons(self, object):
        if object._state.adding:
            return mark_safe("-")
        else:
            return format_html(
                '<a href="{add_member_link}" class="button">Ajouter un membre</a> '
                '<a href="{add_allocation_link}" class="button">Changer l\'allocation</a>'
                " <small>Attention : cliquer"
                " sur ces boutons quitte la page et perd vos modifications courantes.</small>",
                add_member_link=reverse(
                    "admin:groups_supportgroup_add_member", args=(object.pk,)
                ),
                add_allocation_link=reverse("admin:donations_operation_add")
                + "?group="
                + str(object.pk),
            )

    action_buttons.short_description = _("Actions")

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)

        return qs.annotate(
            membership_count=RawSQL(
                'SELECT COUNT(*) FROM "groups_membership" WHERE "supportgroup_id" = "groups_supportgroup"."id"',
                (),
            ),
            allocation=RawSQL(
                'SELECT SUM(amount) FROM "donations_operation" WHERE "group_id" = "groups_supportgroup"."id"',
                (),
            ),
        )

    def get_urls(self):
        return [
            path(
                "<uuid:pk>/add_member/",
                admin_site.admin_view(self.add_member),
                name="groups_supportgroup_add_member",
            )
        ] + super().get_urls()

    def add_member(self, request, pk):
        return views.add_member(self, request, pk)

    def get_changelist_instance(self, request):
        cl = super().get_changelist_instance(request)
        if request.user.has_perm("donations.add_operation"):
            try:
                idx = cl.list_display.index("allocation")
            except ValueError:
                pass
            else:
                cl.list_display[idx] = update_wrapper(
                    partial(self.allocation, show_add_button=True), self.allocation
                )
        return cl


@admin.register(models.SupportGroupTag, site=admin_site)
class SupportGroupTagAdmin(admin.ModelAdmin):
    pass


@admin.register(models.SupportGroupSubtype, site=admin_site)
class SupportGroupSubtypeAdmin(admin.ModelAdmin):
    search_fields = ("label", "description")
    list_display = ("label", "description", "type", "visibility")
    list_filter = ("type", "visibility")
