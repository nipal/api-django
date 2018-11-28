import django_filters

from agir.events.models import Event, Calendar


class EventFilterSet(django_filters.FilterSet):
    calendars = django_filters.filterset.ModelMultipleChoiceFilter(
        queryset=Calendar.objects.all(), method="filter_calendar"
    )

    def filter_calendar(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(calendar_items__calendar__in=value)

    class Meta:
        model = Event
        fields = {
            "name": ["search"],
            "published": ["exact"],
            "start_time": ["lt", "gt"],
            "subtype": ["exact"],
        }
