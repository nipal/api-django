import json
from unittest import skip

from django.test import TestCase
from django.utils import timezone, formats
from django.utils.http import urlquote_plus
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point

from rest_framework.test import APIRequestFactory, force_authenticate, APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from agir.people.models import Person
from agir.clients.models import Client

from ..models import Event, Calendar, RSVP, OrganizerConfig, CalendarItem
from ..viewsets import LegacyEventViewSet, RSVPViewSet


class LegacyEventViewSetTestCase(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            name="event",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=4),
            nb_id=1,
        )

        self.unprivileged_person = Person.objects.create_person(
            email="jean.georges@domain.com", first_name="Jean", last_name="Georges"
        )

        self.changer_person = Person.objects.create_person(email="changer@changer.fr")

        self.one_event_person = Person.objects.create_person(email="event@event.com")

        self.attendee_person = Person.objects.create_person(
            email="attendee@attendee.com"
        )

        self.view_all_person = Person.objects.create_person(email="viewer@viewer.fr")

        event_content_type = ContentType.objects.get_for_model(Event)
        change_permission = Permission.objects.get(
            content_type=event_content_type, codename="change_event"
        )
        view_hidden_permission = Permission.objects.get(
            content_type=event_content_type, codename="view_hidden_event"
        )

        self.changer_person.role.user_permissions.add(change_permission)
        self.view_all_person.role.user_permissions.add(view_hidden_permission)

        OrganizerConfig.objects.create(
            event=self.event, person=self.one_event_person, is_creator=True
        )

        RSVP.objects.create(person=self.attendee_person, event=self.event, guests=10)

        self.detail_view = LegacyEventViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        )

        self.list_view = LegacyEventViewSet.as_view({"get": "list", "post": "create"})

        self.new_event_data = {
            "name": "event 2",
            "start_time": timezone.now().isoformat(),
            "end_time": (timezone.now() + timezone.timedelta(hours=2)).isoformat(),
        }

        self.factory = APIRequestFactory()

    def test_can_list_event_while_unauthenticated(self):
        request = self.factory.get("")
        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertEqual(len(response.data["_items"]), 1)

        item = response.data["_items"][0]

        self.assertEqual(item["_id"], str(self.event.pk))
        self.assertEqual(item["name"], self.event.name)
        self.assertEqual(item["participants"], self.event.participants)
        assert {
            "name",
            "path",
            "id",
            "location",
            "contact",
            "tags",
            "coordinates",
            "participants",
        }.issubset(item)

    def unpublish_event(self):
        self.event.visibility = Event.VISIBILITY_ADMIN
        self.event.save()

    def test_cannot_list_unpublished_events_while_unauthicated(self):
        self.unpublish_event()
        request = self.factory.get("")
        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertEqual(len(response.data["_items"]), 0)

    def test_can_see_event_details_while_unauthenticated(self):
        request = self.factory.get("")
        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["_id"], str(self.event.pk))

    def test_cannot_view_unpublished_events_while_unauthicated(self):
        self.unpublish_event()
        request = self.factory.get("")
        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_can_view_unpublished_groups_with_correct_permissions(self):
        self.unpublish_event()
        request = self.factory.get("")
        force_authenticate(request, self.view_all_person.role)
        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["_id"], str(self.event.pk))

    def test_cannot_create_event_while_unauthenticated(self):
        request = self.factory.post("", data=self.new_event_data)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_modify_event_while_unauthenticated(self):
        request = self.factory.put("", data=self.new_event_data)

        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_modify_event_without_permission(self):
        request = self.factory.put("", data=self.new_event_data)
        force_authenticate(request, self.unprivileged_person.role)

        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_create_event_whith_no_privilege(self):
        request = self.factory.post("", data=self.new_event_data)
        force_authenticate(request, self.unprivileged_person.role)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("_id", response.data)
        new_id = response.data["_id"]

        events = Event.objects.all()
        event = Event.objects.get(pk=new_id)

        self.assertEqual(len(events), 2)
        self.assertEqual(event.organizers.first(), self.unprivileged_person)
        self.assertIn(new_id, {str(e.id) for e in events})

    def test_can_modify_event_with_global_perm(self):
        request = self.factory.patch(
            "",
            data={
                "description": "Plus mieux!",
                "visibility": "A",
                "organizers": [
                    reverse(
                        "legacy:person-detail",
                        kwargs={"pk": self.unprivileged_person.pk},
                    )
                ],
            },
        )

        force_authenticate(request, user=self.changer_person.role)

        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()

        self.assertEqual(self.event.description, "Plus mieux!")
        self.assertEqual(self.event.visibility, Event.VISIBILITY_ADMIN)
        # When PATCHing through a client, the organizers should be repaced by
        # the new list
        self.assertIn(self.unprivileged_person, self.event.organizers.all())
        self.assertNotIn(self.one_event_person, self.event.organizers.all())

    def test_field_is_organizer(self):
        request = self.factory.get("")
        force_authenticate(request, user=self.one_event_person.role)
        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["is_organizer"], True)

    def test_organizer_can_modify_event(self):
        request = self.factory.patch(
            "",
            data={
                "description": "Plus mieux!",
                "organizers": [
                    reverse(
                        "legacy:person-detail",
                        kwargs={"pk": self.unprivileged_person.pk},
                    )
                ],
            },
        )

        force_authenticate(request, user=self.one_event_person.role)

        response = self.detail_view(request, pk=self.event.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()

        # The organizer should be able to modify list of other organizer but not
        # to remove themselves
        self.assertEqual(self.event.description, "Plus mieux!")
        self.assertIn(self.unprivileged_person, self.event.organizers.all())
        self.assertIn(self.one_event_person, self.event.organizers.all())

    def test_cannot_create_event_with_same_nb_id(self):
        self.client.force_login(self.unprivileged_person.role)
        response = self.client.post(
            "/legacy/events/", data={**self.new_event_data, "id": self.event.nb_id}
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_can_get_event_summary(self):
        response = self.client.get("/legacy/events/summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data), 1)


class FiltersTestCase(APITestCase):
    def setUp(self):
        self.superuser = Person.objects.create_superperson("super@user.fr", None)

        self.calendar1 = calendar1 = Calendar.objects.create_calendar("Agenda")
        self.calendar2 = calendar2 = Calendar.objects.create_calendar("Agenda2")

        tz = timezone.get_default_timezone()

        self.paris_1_month_event = Event.objects.create(
            name="Paris+1month",
            nb_id=1,
            start_time=timezone.now() + timezone.timedelta(weeks=4),
            end_time=timezone.now() + timezone.timedelta(weeks=4, hours=2),
            coordinates=Point(2.349722, 48.853056),  # ND de Paris
        )
        CalendarItem.objects.create(
            event=self.paris_1_month_event, calendar=self.calendar1
        )

        self.amiens_2_months_event = Event.objects.create(
            name="Amiens+2months",
            nb_path="/amiens_july",
            start_time=timezone.now() + timezone.timedelta(weeks=8),
            end_time=timezone.now() + timezone.timedelta(weeks=8, hours=2),
            coordinates=Point(2.301944, 49.8944),  # ND d'Amiens
        )
        CalendarItem.objects.create(
            event=self.amiens_2_months_event, calendar=self.calendar1
        )

        self.marseille_3_months_event = Event.objects.create(
            name="Marseille+3months",
            start_time=timezone.now() + timezone.timedelta(weeks=12),
            end_time=timezone.now() + timezone.timedelta(weeks=12, hours=2),
            coordinates=Point(5.36472, 43.30028),  # Saint-Marie-Majeure de Marseille
        )
        CalendarItem.objects.create(
            event=self.marseille_3_months_event, calendar=self.calendar2
        )

        self.strasbourg_yesterday = Event.objects.create(
            name="Strasbourg+yesterday",
            start_time=timezone.now() - timezone.timedelta(hours=15),
            end_time=timezone.now() - timezone.timedelta(hours=13),
            coordinates=Point(7.7779, 48.5752),  # ND de Strasbourg
        )
        CalendarItem.objects.create(
            event=self.strasbourg_yesterday, calendar=self.calendar2
        )

        self.eiffel_coordinates = [2.294444, 48.858333]

    def test_can_query_by_pk(self):
        response = self.client.get("/legacy/events/%s/" % self.paris_1_month_event.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], self.paris_1_month_event.name)

    def test_can_query_by_nb_id(self):
        response = self.client.get(
            "/legacy/events/%s/" % self.paris_1_month_event.nb_id
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["_id"], str(self.paris_1_month_event.pk))

    def test_filter_coordinates_no_results(self):
        # la tour eiffel est à plus d'un kilomètre de Notre-Dame
        filter_string = json.dumps(
            {"max_distance": 1000, "coordinates": self.eiffel_coordinates}
        )

        response = self.client.get("/legacy/events/?close_to=%s" % filter_string)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertEqual(len(response.data["_items"]), 0)

    def test_filter_coordinates_one_result(self):
        # la tour eiffel est à moins de 10 km de Notre-Dame
        filter_string = json.dumps(
            {"max_distance": 10000, "coordinates": self.eiffel_coordinates}
        )

        response = self.client.get("/legacy/events/?close_to=%s" % filter_string)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertEqual(len(response.data["_items"]), 1)
        self.assertEqual(
            response.data["_items"][0]["_id"], str(self.paris_1_month_event.pk)
        )

    def test_filter_by_path(self):
        response = self.client.get("/legacy/events/?path=/amiens_july")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertEqual(len(response.data["_items"]), 1)
        self.assertEqual(
            response.data["_items"][0]["_id"], str(self.amiens_2_months_event.pk)
        )

    def test_order_by_distance_to(self):
        response = self.client.get(
            "/legacy/events/?order_by_distance_to=%s"
            % json.dumps(self.eiffel_coordinates)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertEqual(len(response.data["_items"]), 3)
        self.assertEqual(
            [item["_id"] for item in response.data["_items"]],
            [
                str(self.paris_1_month_event.id),
                str(self.amiens_2_months_event.id),
                str(self.marseille_3_months_event.id),
            ],
        )

    def test_can_directly_retrieve_past_event(self):
        response = self.client.get("/legacy/events/%s/" % self.strasbourg_yesterday.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_id", response.data)
        self.assertEqual(response.data["_id"], str(self.strasbourg_yesterday.pk))

    def test_can_filter_by_date_after(self):
        # make sure event in progress at the "after" date are included
        response = self.client.get(
            "/legacy/events/?after=%s"
            % urlquote_plus(
                (timezone.now() + timezone.timedelta(weeks=8, hours=1)).isoformat()
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertCountEqual(
            [item["_id"] for item in response.data["_items"]],
            [str(self.amiens_2_months_event.id), str(self.marseille_3_months_event.id)],
        )

    def test_can_filter_by_date_before(self):
        response = self.client.get(
            "/legacy/events/?before=%s"
            % urlquote_plus(
                (timezone.now() + timezone.timedelta(weeks=4, hours=1)).isoformat()
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertCountEqual(
            [item["_id"] for item in response.data["_items"]],
            [str(self.strasbourg_yesterday.id), str(self.paris_1_month_event.id)],
        )

    def test_can_filter_by_calendar(self):
        response = self.client.get("/legacy/events/?calendar=%s" % self.calendar1.slug)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("_items", response.data)
        self.assertCountEqual(
            [item["_id"] for item in response.data["_items"]],
            [str(e.id) for e in Event.objects.filter(calendars=self.calendar1)],
        )


class RSVPEndpointTestCase(TestCase):
    def get_request(self, path="", data=None, **extra):
        return self.factory.get(path, data, **extra)

    def as_privileged(self, request):
        force_authenticate(request, self.privileged_user.role)
        return request

    def as_organizer(self, request):
        force_authenticate(request, self.organizer.role)
        return request

    def as_unprivileged(self, request):
        force_authenticate(request, self.unprivileged_person.role)
        return request

    def setUp(self):
        self.privileged_user = Person.objects.create_superperson("super@user.fr", None)

        self.organizer = Person.objects.create_person(email="event@event.com")

        self.unprivileged_person = Person.objects.create_person(
            email="unprivileged@event.com"
        )

        tz = timezone.get_default_timezone()

        self.event = Event.objects.create(
            name="Paris+June",
            nb_id=1,
            start_time=tz.localize(timezone.datetime(2017, 6, 15, 18)),
            end_time=tz.localize(timezone.datetime(2017, 6, 15, 22)),
            coordinates=Point(2.349722, 48.853056),  # ND de Paris
        )

        self.secondary_event = Event.objects.create(
            name="Amiens+July",
            nb_path="/amiens_july",
            start_time=tz.localize(timezone.datetime(2017, 7, 15, 18)),
            end_time=tz.localize(timezone.datetime(2017, 7, 15, 22)),
            coordinates=Point(2.301944, 49.8944),  # ND d'Amiens
        )

        self.unprivileged_rsvp = RSVP.objects.create(
            event=self.event, person=self.unprivileged_person, guests=0
        )

        self.organizer_rsvp = RSVP.objects.create(
            event=self.event, person=self.organizer, guests=1
        )

        self.other_rsvp = RSVP.objects.create(
            event=self.secondary_event, person=self.unprivileged_person
        )

        rsvp_content_type = ContentType.objects.get_for_model(RSVP)
        add_permission = Permission.objects.get(
            content_type=rsvp_content_type, codename="add_rsvp"
        )
        change_permission = Permission.objects.get(
            content_type=rsvp_content_type, codename="change_rsvp"
        )
        delete_permission = Permission.objects.get(
            content_type=rsvp_content_type, codename="delete_rsvp"
        )

        self.privileged_user.role.user_permissions.add(
            add_permission, change_permission, delete_permission
        )

        OrganizerConfig.objects.create(
            event=self.event, person=self.organizer, is_creator=True
        )

        self.factory = APIRequestFactory()

        self.rsvp_list_view = RSVPViewSet.as_view({"get": "list", "post": "create"})

        self.rsvp_detail_view = RSVPViewSet.as_view({"get"})

    def test_unauthenticated_cannot_see_any_rsvp(self):
        request = self.get_request()

        response = self.rsvp_list_view(request)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_can_see_own_rsvps(self):
        request = self.as_unprivileged(self.get_request())

        response = self.rsvp_list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        assert all(
            rsvp["person"].split("/")[-2] == str(self.unprivileged_person.id)
            for rsvp in response.data
        )
        self.assertCountEqual(
            [rsvp["event"].split("/")[-2] for rsvp in response.data],
            [str(self.event.id), str(self.secondary_event.id)],
        )

    @skip("TODO")
    def test_cannot_create_rsvp_as_unauthenticated(self):
        pass

    @skip("TODO")
    def test_can_create_rsvp_as_unprivileged(self):
        pass

    @skip("TODO")
    def test_can_modify_own_rsvp(self):
        pass


class EventWorkerTestCase(TestCase):
    def setUp(self):
        self.worker = Client.objects.create_client("worker")

        self.worker.role.groups.add(Group.objects.get(name="workers"))

        self.unpublished_event = Event.objects.create(
            name="event",
            start_time=timezone.now() + timezone.timedelta(hours=2),
            end_time=timezone.now() + timezone.timedelta(hours=4),
            visibility=Event.VISIBILITY_ADMIN,
        )

        self.past_event = Event.objects.create(
            name="event",
            start_time=timezone.now() + timezone.timedelta(days=-2),
            end_time=timezone.now() + timezone.timedelta(days=-2, hours=4),
        )

        self.client.force_login(self.worker.role)

    def test_worker_can_get_unpublished_event(self):
        response = self.client.get(
            "/legacy/events/{}/".format(self.unpublished_event.pk)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["_id"], str(self.unpublished_event.pk))

    def test_worker_can_get_past_event(self):
        response = self.client.get("/legacy/events/{}/".format(self.past_event.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["_id"], str(self.past_event.pk))
