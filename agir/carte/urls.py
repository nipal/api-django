from django.urls import path
from . import views

app_name = "carte"

urlpatterns = [
    path("liste_evenements/", views.EventsView.as_view(), name="event_list"),
    path("liste_groupes/", views.GroupsView.as_view(), name="group_list"),
    path("evenements/", views.EventMapView.as_view(), name="events_map"),
    path(
        "evenements/<uuid:pk>/",
        views.SingleEventMapView.as_view(),
        name="single_event_map",
    ),
    path("groupes/", views.GroupMapView.as_view(), name="groups_map"),
    path(
        "groupes/<uuid:pk>/",
        views.SingleGroupMapView.as_view(),
        name="single_group_map",
    ),
]
