from unittest import skip, mock

from django.core.exceptions import ValidationError
from django.contrib import messages
from django.test import TestCase
from django.utils import timezone, formats
from django.utils.http import urlencode

from rest_framework.reverse import reverse
from rest_framework import status

from agir.authentication.subscription import subscription_confirmation_token_generator
from agir.events.actions import legal
from agir.groups.models import SupportGroup, Membership
from agir.payments.actions import complete_payment
from agir.payments.models import Payment
from agir.people.models import Person, PersonForm, PersonFormSubmission, PersonTag

from ..forms import EventForm
from ..models import Event, Calendar, RSVP, OrganizerConfig, CalendarItem, EventSubtype
from ..views import notification_listener as event_notification_listener


class OrganizerAsGroupTestCase(TestCase):
    def setUp(self):
        self.start_time = timezone.now()
        self.end_time = self.start_time + timezone.timedelta(hours=2)
        self.calendar = Calendar.objects.create_calendar(
            "calendar", user_contributed=True
        )
        self.person = Person.objects.create(email="test@example.com")
        self.event = Event.objects.create(
            name="Event test", start_time=self.start_time, end_time=self.end_time
        )
        self.group1 = SupportGroup.objects.create(name="Nom")
        Membership.objects.create(
            person=self.person, supportgroup=self.group1, is_manager=True
        )
        self.group2 = SupportGroup.objects.create(name="Nom")
        Membership.objects.create(person=self.person, supportgroup=self.group2)

        self.organizer_config = OrganizerConfig(
            person=self.person, event=self.event, is_creator=True
        )

    def test_can_add_group_as_organizer(self):
        self.organizer_config.as_group = self.group1
        self.organizer_config.full_clean()

    def test_cannot_add_group_as_organizer_if_not_manager(self):
        self.organizer_config.as_group = self.group2
        with self.assertRaises(ValidationError):
            self.organizer_config.full_clean()


class EventPagesTestCase(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com")
        self.other_person = Person.objects.create_person("other@test.fr")
        self.group = SupportGroup.objects.create(name="Group name")
        Membership.objects.create(
            supportgroup=self.group, person=self.person, is_manager=True
        )

        self.now = now = timezone.now().astimezone(timezone.get_default_timezone())
        day = timezone.timedelta(days=1)
        hour = timezone.timedelta(hours=1)

        self.subtype = EventSubtype.objects.create(
            label="subtype", description="subtype"
        )

        self.organized_event = Event.objects.create(
            name="Organized event",
            subtype=self.subtype,
            start_time=now + day,
            end_time=now + day + 4 * hour,
            legal={legal.QUESTION_SALLE: True, legal.QUESTION_MATERIEL_CAMPAGNE: True},
        )

        OrganizerConfig.objects.create(
            event=self.organized_event, person=self.person, is_creator=True
        )

        self.rsvped_event = Event.objects.create(
            name="RSVPed event",
            subtype=self.subtype,
            start_time=now + 2 * day,
            end_time=now + 2 * day + 2 * hour,
            allow_guests=True,
        )

        RSVP.objects.create(person=self.person, event=self.rsvped_event)

        self.other_event = Event.objects.create(
            name="Other event",
            subtype=self.subtype,
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
        )

        self.other_rsvp1 = RSVP.objects.create(
            person=self.other_person, event=self.rsvped_event
        )

        self.other_rsvp2 = RSVP.objects.create(
            person=self.other_person, event=self.other_event
        )

        self.past_event = Event.objects.create(
            name="past Event",
            subtype=self.subtype,
            start_time=now - 2 * day,
            end_time=now - 2 * day + 2 * hour,
            report_content="Ceci est un compt rendu de l'evenement",
            report_summary_sent=False,
        )

        self.futur_event = Event.objects.create(
            name="past Event",
            subtype=self.subtype,
            start_time=now + 2 * day,
            end_time=now + 2 * day + 2 * hour,
            report_content="Ceci est un compt rendu de l'evenement",
            report_summary_sent=False,
        )

        self.no_report_event = Event.objects.create(
            name="no report event",
            subtype=self.subtype,
            start_time=now + 2 * day,
            end_time=now + 2 * day + 2 * hour,
            report_content="",
            report_summary_sent=False,
        )

        self.all_ready_sent_event = Event.objects.create(
            name="all ready sent event",
            subtype=self.subtype,
            start_time=now + 2 * day,
            end_time=now + 2 * day + 2 * hour,
            report_content="",
            report_summary_sent=True,
        )

        OrganizerConfig.objects.create(
            event=self.past_event, person=self.person, is_creator=True
        )
        OrganizerConfig.objects.create(
            event=self.futur_event, person=self.person, is_creator=True
        )
        OrganizerConfig.objects.create(
            event=self.no_report_event, person=self.person, is_creator=True
        )
        OrganizerConfig.objects.create(
            event=self.all_ready_sent_event, person=self.person, is_creator=True
        )

        self.the_rsvp = RSVP.objects.create(person=self.person, event=self.past_event)

    def test_can_see_public_event(self):
        res = self.client.get(
            reverse("view_event", kwargs={"pk": self.organized_event.pk})
        )

        self.assertContains(res, self.organized_event.name)

    def test_cannot_see_private_event_only_if_organizer(self):
        self.organized_event.visibility = Event.VISIBILITY_ORGANIZER
        self.organized_event.save()

        self.client.force_login(self.other_person.role)
        res = self.client.get(
            reverse("view_event", kwargs={"pk": self.organized_event.pk})
        )
        self.assertNotContains(res, self.organized_event.name, status_code=404)

        self.client.force_login(self.person.role)
        res = self.client.get(
            reverse("view_event", kwargs={"pk": self.organized_event.pk})
        )
        self.assertContains(res, self.organized_event.name)

    def test_cannot_see_admin_event(self):
        self.organized_event.visibility = Event.VISIBILITY_ADMIN
        self.organized_event.save()

        self.client.force_login(self.person.role)
        res = self.client.get(
            reverse("view_event", kwargs={"pk": self.organized_event.pk})
        )
        self.assertNotContains(res, self.organized_event.name, status_code=404)

    @mock.patch.object(EventForm, "geocoding_task")
    @mock.patch("agir.events.forms.send_event_changed_notification")
    def test_can_modify_organized_event(
        self, patched_send_notification, patched_geocode
    ):
        self.client.force_login(self.person.role)
        response = self.client.get(
            reverse("edit_event", kwargs={"pk": self.organized_event.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            reverse("edit_event", kwargs={"pk": self.organized_event.pk}),
            data={
                "name": "New Name",
                "start_time": formats.localize_input(
                    self.now + timezone.timedelta(hours=2), "%d/%m/%Y %H:%M"
                ),
                "end_time": formats.localize_input(
                    self.now + timezone.timedelta(hours=4), "%d/%m/%Y %H:%M"
                ),
                "contact_name": "Arthur",
                "contact_email": "a@ziefzji.fr",
                "contact_phone": "06 06 06 06 06",
                "location_name": "somewhere",
                "location_address1": "over",
                "location_zip": "the",
                "location_city": "rainbow",
                "location_country": "FR",
                "description": "New description",
                "notify": "on",
                "as_group": self.group.pk,
            },
        )

        # the form redirects to the event manage page on success
        self.assertRedirects(
            response, reverse("manage_event", kwargs={"pk": self.organized_event.pk})
        )

        # accessing the messages: see https://stackoverflow.com/a/14909727/1122474
        messages = list(response.wsgi_request._messages)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level_tag, "success")

        # send_support_group_changed_notification.delay should have been called once, with the pk of the group as
        # first argument, and the changes as the second
        patched_send_notification.delay.assert_called_once()
        args = patched_send_notification.delay.call_args[0]

        self.assertEqual(args[0], self.organized_event.pk)
        self.assertCountEqual(args[1], ["contact", "location", "timing", "information"])

        patched_geocode.delay.assert_called_once()
        args = patched_geocode.delay.call_args[0]

        self.assertEqual(args[0], self.organized_event.pk)
        self.assertIn(self.group, self.organized_event.organizers_groups.all())

    def test_cannot_modify_rsvp_event(self):
        self.client.force_login(self.person.role)

        # manage_page
        response = self.client.get(
            reverse("manage_event", kwargs={"pk": self.rsvped_event.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # get edit page
        response = self.client.get(
            reverse("edit_event", kwargs={"pk": self.rsvped_event.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # post edit page
        response = self.client.post(
            reverse("edit_event", kwargs={"pk": self.rsvped_event.pk}),
            data={
                "name": "New Name",
                "start_time": formats.localize_input(
                    timezone.now() + timezone.timedelta(hours=2), "%d/%m/%Y %H:%M"
                ),
                "end_time": formats.localize_input(
                    timezone.now() + timezone.timedelta(hours=4), "%d/%m/%Y %H:%M"
                ),
                "contact_name": "Arthur",
                "contact_email": "a@ziefzji.fr",
                "contact_phone": "06 06 06 06 06",
                "location_name": "somewhere",
                "location_address1": "over",
                "location_zip": "the",
                "location_city": "rainbow",
                "location_country": "FR",
                "description": "New description",
                "notify": "on",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # add organizer
        response = self.client.post(
            reverse("manage_event", kwargs={"pk": self.rsvped_event.pk}),
            data={"organizer": str(self.other_rsvp1.pk)},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_modify_other_event(self):
        self.client.force_login(self.person.role)

        # manage_page
        response = self.client.get(
            reverse("manage_event", kwargs={"pk": self.other_event.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # get edit page
        response = self.client.get(
            reverse("edit_event", kwargs={"pk": self.other_event.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # post edit page
        response = self.client.post(
            reverse("edit_event", kwargs={"pk": self.other_event.pk}),
            data={
                "name": "New Name",
                "start_time": formats.localize_input(
                    timezone.now() + timezone.timedelta(hours=2), "%d/%m/%Y %H:%M"
                ),
                "end_time": formats.localize_input(
                    timezone.now() + timezone.timedelta(hours=4), "%d/%m/%Y %H:%M"
                ),
                "contact_name": "Arthur",
                "contact_email": "a@ziefzji.fr",
                "contact_phone": "06 06 06 06 06",
                "location_name": "somewhere",
                "location_address1": "over",
                "location_zip": "the",
                "location_city": "rainbow",
                "location_country": "FR",
                "description": "New description",
                "notify": "on",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # add organizer
        response = self.client.post(
            reverse("manage_event", kwargs={"pk": self.other_event.pk}),
            data={"organizer": str(self.other_rsvp2.pk)},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @skip("Redo with new creation form")
    def test_can_create_event(self):
        pass

    def test_can_edit_legal_fields(self):
        self.client.force_login(self.person.role)
        res = self.client.get(
            reverse("event_legal_form", args=[self.organized_event.pk])
        )

        self.assertContains(res, "Salle")
        self.assertNotContains(res, "Hébergement militant")

        self.client.post(
            reverse("event_legal_form", args=[self.organized_event.pk]),
            data={"salle": "gratuite", "salle_name": "Nom de la salle"},
        )
        self.organized_event.refresh_from_db()
        self.assertEqual(self.organized_event.legal["documents_salle"], "gratuite")
        self.assertEqual(
            self.organized_event.legal["documents_salle_name"], "Nom de la salle"
        )
        res = self.client.get(
            reverse("event_legal_form", args=[self.organized_event.pk])
        )
        self.assertContains(res, "Nom de la salle")

    def test_excluded_fields_are_not_in_form(self):
        self.subtype.config = {"excluded_fields": ["name"]}
        self.subtype.save()

        self.client.force_login(self.person.role)

        response = self.client.get(
            reverse("edit_event", kwargs={"pk": self.organized_event.pk})
        )

        self.assertNotContains(response, "Nom de l'événement")

        response = self.client.post(
            reverse("edit_event", kwargs={"pk": self.organized_event.pk}),
            data={
                "name": "New Name",
                "start_time": formats.localize_input(
                    self.now + timezone.timedelta(hours=2), "%d/%m/%Y %H:%M"
                ),
                "end_time": formats.localize_input(
                    self.now + timezone.timedelta(hours=4), "%d/%m/%Y %H:%M"
                ),
                "contact_name": "Arthur",
                "contact_email": "a@ziefzji.fr",
                "contact_phone": "06 06 06 06 06",
                "location_name": "somewhere",
                "location_address1": "over",
                "location_zip": "the",
                "location_city": "rainbow",
                "location_country": "FR",
                "description": "New description",
                "notify": "on",
                "as_group": self.group.pk,
            },
        )

        # the form redirects to the event manage page on success
        self.assertRedirects(
            response, reverse("manage_event", kwargs={"pk": self.organized_event.pk})
        )

        self.organized_event.refresh_from_db()
        self.assertEqual(self.organized_event.name, "Organized event")

    @mock.patch("agir.events.views.event_views.send_event_report")
    def test_can_send_event_report_if_its_possible(self, send_event_report):
        """ Si les conditions sont réunies, on peut envoyer le résumé par mail.

        Les conditions sont : le mail n'a jamais été envoyé, l'événement est passé, le compte-rendu n'est pas vide."""
        self.client.force_login(self.person.role)
        session = self.client.session

        response = self.client.post(
            reverse("send_event_report", kwargs={"pk": self.past_event.pk})
        )
        self.assertRedirects(
            response, reverse("manage_event", kwargs={"pk": self.past_event.pk})
        )
        send_event_report.delay.assert_called_once()

        # # on simule le fait que le compte-rendu a bien été envoyé
        self.past_event.report_summary_sent = True
        self.past_event.save()
        response = self.client.get(
            reverse("manage_event", kwargs={"pk": self.past_event.pk})
        )
        self.assertContains(response, "Ce compte-rendu a déjà été envoyé")

    @mock.patch("agir.events.views.event_views.send_event_report")
    def test_report_is_sent_in_event_manage(self, send_event_report):
        """
        Test si le template affiche bien le fait que le compte-rendu à été envoyé la première fois que l'on retourne sur la page, mais pas les fois suivantes.
        """
        self.client.force_login(self.person.role)

        self.client.post(
            reverse("send_event_report", kwargs={"pk": self.past_event.pk})
        )

        response = self.client.get(
            reverse("manage_event", kwargs={"pk": self.past_event.pk})
        )
        # la tache `send event_report` n'est pas appeler. Mais une variable de session temporaire est utliser pour informer que le mail à été envoyé
        self.assertContains(response, "Ce compte-rendu a déjà été envoyé.")

        response = self.client.get(
            reverse("manage_event", kwargs={"pk": self.past_event.pk})
        )
        # la deuxième fois la variable de session n'existe plus
        self.assertNotContains(response, "Ce compte-rendu a déjà été envoyé")

    @mock.patch("agir.events.views.event_views.send_event_report")
    def test_can_not_send_event_report_when_nocondition(self, send_event_report):
        """ Si les conditions une des condition manque, l'envoi du mail ne se fait pas.

        Les conditions sont : le mail n'a jamais été envoyé, l'événement est passé,
        le compte-rendu n'est pas vide."""
        self.client.force_login(self.person.role)
        response = self.client.post(
            reverse("send_event_report", kwargs={"pk": self.no_report_event.pk})
        )
        send_event_report.delay.assert_not_called()
        response = self.client.post(
            reverse("send_event_report", kwargs={"pk": self.futur_event.pk})
        )
        send_event_report.delay.assert_not_called()
        response = self.client.post(
            reverse("send_event_report", kwargs={"pk": self.all_ready_sent_event.pk})
        )
        send_event_report.delay.assert_not_called()


class RSVPTestCase(TestCase):
    # TODO: refactor this test case... too big
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com")
        self.already_rsvped = Person.objects.create_person("test2@test.com")

        self.now = now = timezone.now().astimezone(timezone.get_default_timezone())
        day = timezone.timedelta(days=1)
        hour = timezone.timedelta(hours=1)

        self.simple_event = Event.objects.create(
            name="Simple Event",
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
        )

        self.subscription_form = PersonForm.objects.create(
            title="Formulaire événement",
            slug="formulaire-evenement",
            description="Ma description complexe",
            confirmation_note="Ma note de fin",
            main_question="QUESTION PRINCIPALE",
            custom_fields=[
                {
                    "title": "Détails",
                    "fields": [
                        {
                            "id": "custom-field",
                            "type": "short_text",
                            "label": "Mon label",
                            "person_field": True,
                        },
                        {
                            "id": "price",
                            "type": "integer",
                            "label": "Prix",
                            "required": False,
                        },
                    ],
                }
            ],
        )

        self.form_event = Event.objects.create(
            name="Other event",
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
            subscription_form=self.subscription_form,
        )

        self.simple_paying_event = Event.objects.create(
            name="Paying event",
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
            payment_parameters={"price": 1000},
        )

        self.form_paying_event = Event.objects.create(
            name="Paying event",
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
            payment_parameters={"price": 1000},
            subscription_form=self.subscription_form,
        )

        RSVP.objects.create(person=self.already_rsvped, event=self.simple_event)
        RSVP.objects.create(
            person=self.already_rsvped,
            event=self.form_event,
            form_submission=PersonFormSubmission.objects.create(
                person=self.already_rsvped,
                form=self.subscription_form,
                data={"custom-field": "custom value"},
            ),
        )
        RSVP.objects.create(person=self.already_rsvped, event=self.simple_paying_event)
        RSVP.objects.create(
            person=self.already_rsvped,
            event=self.form_paying_event,
            form_submission=PersonFormSubmission.objects.create(
                person=self.already_rsvped,
                form=self.subscription_form,
                data={"custom-field": "custom value"},
            ),
        )

        self.billing_information = {
            "first_name": "Marc",
            "last_name": "Frank",
            "location_address1": "4 rue de Chaume",
            "location_address2": "",
            "location_zip": "33000",
            "location_city": "Bordeaux",
            "location_country": "FR",
            "contact_phone": "06 45 78 98 45",
        }

    @mock.patch("agir.events.actions.rsvps.send_rsvp_notification")
    def test_can_rsvp_to_simple_event_and_quit(self, rsvp_notification):
        self.client.force_login(self.person.role)

        url = reverse("view_event", kwargs={"pk": self.simple_event.pk})

        # can see the form
        response = self.client.get(url)
        self.assertIn("Participer à cet événement", response.content.decode())

        # can actually post the form
        response = self.client.post(
            reverse("rsvp_event", kwargs={"pk": self.simple_event.pk})
        )
        self.assertRedirects(response, url)
        self.assertIn(self.person, self.simple_event.attendees.all())
        self.assertEqual(2, self.simple_event.participants)

        rsvp_notification.delay.assert_called_once()

        rsvp = RSVP.objects.get(person=self.person, event=self.simple_event)
        self.assertEqual(rsvp_notification.delay.call_args[0][0], rsvp.pk)

        res = self.client.post(
            reverse("quit_event", kwargs={"pk": self.simple_event.pk})
        )
        self.assertRedirects(res, reverse("dashboard"))
        self.assertNotIn(self.person, self.simple_event.attendees.all())
        self.assertEqual(1, self.simple_event.participants)

    def test_can_view_rsvp(self):
        self.client.force_login(self.already_rsvped.role)

        url = reverse("view_event", kwargs={"pk": self.simple_event.pk})
        response = self.client.get(url)
        self.assertIn("Inscription confirmée", response.content.decode())
        self.assertEqual(1, self.simple_event.participants)

    def test_cannot_rsvp_if_max_participants_reached(self):
        self.client.force_login(self.person.role)

        self.simple_event.max_participants = 1
        self.simple_event.save()

        url = reverse("view_event", kwargs={"pk": self.simple_event.pk})

        # cannot view the RSVP button
        response = self.client.get(url)
        self.assertNotContains(response, "Participer à cet événement")

        # cannot rsvp even when posting the form
        response = self.client.post(
            reverse("rsvp_event", kwargs={"pk": self.simple_event.pk})
        )
        self.assertRedirects(response, url)
        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].level, messages.ERROR)
        self.assertIn("complet.", msgs[0].message)

        self.assertEqual(1, self.simple_event.participants)

    @mock.patch("agir.events.actions.rsvps.send_guest_confirmation")
    def test_can_add_guest_to_simple_event(self, guest_notification):
        self.client.force_login(self.already_rsvped.role)
        self.simple_event.allow_guests = True
        self.simple_event.save()

        response = self.client.post(
            reverse("rsvp_event", kwargs={"pk": self.simple_event.pk}),
            data={"guests": 1},
        )
        self.assertRedirects(
            response, reverse("view_event", kwargs={"pk": self.simple_event.pk})
        )
        self.assertEqual(2, self.simple_event.participants)

        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.SUCCESS)

        guest_notification.delay.assert_called_once()

        rsvp = RSVP.objects.get(person=self.already_rsvped, event=self.simple_event)
        self.assertEqual(guest_notification.delay.call_args[0][0], rsvp.pk)

    def test_cannot_add_guest_if_forbidden_for_event(self):
        self.client.force_login(self.already_rsvped.role)

        response = self.client.post(
            reverse("rsvp_event", kwargs={"pk": self.simple_event.pk}),
            data={"guests": 1},
        )

        self.assertRedirects(
            response, reverse("view_event", kwargs={"pk": self.simple_event.pk})
        )
        self.assertEqual(1, self.simple_event.participants)

        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.ERROR)

    def test_cannot_add_guest_for_simple_event_if_max_participants_reached(self):
        self.client.force_login(self.already_rsvped.role)

        self.simple_event.allow_guests = True
        self.simple_event.max_participants = 1
        self.simple_event.save()

        response = self.client.post(
            reverse("rsvp_event", kwargs={"pk": self.simple_event.pk}),
            data={"guests": 1},
        )

        self.assertRedirects(
            response, reverse("view_event", kwargs={"pk": self.simple_event.pk})
        )
        self.assertEqual(1, self.simple_event.participants)

        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.ERROR)

    @mock.patch("agir.events.actions.rsvps.send_rsvp_notification")
    def test_can_rsvp_to_form_event(self, rsvp_notification):
        self.client.force_login(self.person.role)

        event_url = reverse("view_event", kwargs={"pk": self.form_event.pk})
        rsvp_url = reverse("rsvp_event", kwargs={"pk": self.form_event.pk})

        response = self.client.get(rsvp_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            rsvp_url, data={"custom-field": "another custom value"}
        )
        self.assertRedirects(response, event_url)
        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.SUCCESS)

        self.person.refresh_from_db()
        self.assertIn(self.person, self.form_event.attendees.all())
        self.assertEqual(self.person.meta["custom-field"], "another custom value")
        self.assertEqual(2, self.form_event.participants)

        rsvp_notification.delay.assert_called_once()

        rsvp = RSVP.objects.get(person=self.person, event=self.form_event)
        self.assertEqual(rsvp_notification.delay.call_args[0][0], rsvp.pk)

    def test_can_edit_rsvp_form(self):
        self.client.force_login(self.person.role)

        rsvp_url = reverse("rsvp_event", kwargs={"pk": self.form_event.pk})
        self.client.post(rsvp_url, data={"custom-field": "another custom value"})

        res = self.client.get(rsvp_url)
        self.assertNotContains(res, "Modifier mon inscription")

        self.form_event.subscription_form.editable = True
        self.form_event.subscription_form.save()
        res = self.client.get(rsvp_url)
        self.assertContains(res, "Modifier ces informations")

    @mock.patch("agir.events.actions.rsvps.send_guest_confirmation")
    def test_can_add_guest_to_form_event(self, guest_confirmation):
        self.form_event.allow_guests = True
        self.form_event.save()

        self.client.force_login(self.already_rsvped.role)

        event_url = reverse("view_event", kwargs={"pk": self.form_event.pk})
        rsvp_url = reverse("rsvp_event", kwargs={"pk": self.form_event.pk})

        response = self.client.get(rsvp_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            rsvp_url, data={"custom-field": "another custom value", "is_guest": "yes"}
        )
        self.assertRedirects(response, event_url)
        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.SUCCESS)

        self.assertEqual(2, self.form_event.participants)

        guest_confirmation.delay.assert_called_once()

        rsvp = RSVP.objects.get(person=self.already_rsvped, event=self.form_event)
        self.assertEqual(guest_confirmation.delay.call_args[0][0], rsvp.pk)

    def test_cannot_add_guest_to_form_event_if_forbidden(self):
        self.client.force_login(self.already_rsvped.role)

        event_url = reverse("view_event", kwargs={"pk": self.form_event.pk})
        rsvp_url = reverse("rsvp_event", kwargs={"pk": self.form_event.pk})

        response = self.client.post(
            rsvp_url, data={"custom-field": "another custom value", "is_guest": "yes"}
        )
        self.assertRedirects(response, event_url)
        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.ERROR)

        self.assertEqual(1, self.form_event.participants)

    @mock.patch("agir.events.actions.rsvps.send_rsvp_notification")
    def test_can_rsvp_to_simple_paying_event(self, rsvp_notification):
        self.client.force_login(self.person.role)

        response = self.client.post(
            reverse("rsvp_event", args=[self.simple_paying_event.pk])
        )
        self.assertRedirects(response, reverse("pay_event"))

        response = self.client.get(reverse("pay_event"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(
            response, f'name="event" value="{self.simple_paying_event.pk}"'
        )
        self.assertContains(response, 'name="submission"')
        self.assertNotContains(response, 'name="submission" value')
        self.assertContains(response, f'name="is_guest" value="False"')

        response = self.client.post(
            reverse("pay_event"),
            data={
                "event": self.simple_paying_event.pk,
                "payment_mode": "check",
                **self.billing_information,
            },
        )

        payment = Payment.objects.get()
        self.assertRedirects(response, reverse("payment_page", args=(payment.pk,)))

        # fake payment confirmation
        complete_payment(payment)
        event_notification_listener(payment)

        self.assertIn(self.person, self.simple_paying_event.attendees.all())

        rsvp_notification.delay.assert_called_once()
        rsvp = RSVP.objects.get(person=self.person, event=self.simple_paying_event)
        self.assertEqual(rsvp_notification.delay.call_args[0][0], rsvp.pk)

    @mock.patch("agir.events.actions.rsvps.send_guest_confirmation")
    def test_can_add_guest_to_simple_paying_event(self, guest_confirmation):
        self.simple_paying_event.allow_guests = True
        self.simple_paying_event.save()
        self.client.force_login(self.already_rsvped.role)
        session = self.client.session

        response = self.client.post(
            reverse("rsvp_event", args=[self.simple_paying_event.pk])
        )
        # check that the guest status is well transfered
        self.assertEqual(session["is_guest"], True)
        self.assertRedirects(response, reverse("pay_event"))

        response = self.client.get(reverse("pay_event"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(
            response, f'name="event" value="{self.simple_paying_event.pk}"'
        )
        self.assertContains(response, 'name="submission"')
        self.assertNotContains(response, 'name="submission" value')
        self.assertContains(response, f'name="is_guest" value="True"')

        response = self.client.post(
            reverse("pay_event"),
            data={
                "event": self.simple_paying_event.pk,
                "payment_mode": "check",
                "is_guest": "yes",
                **self.billing_information,
            },
        )

        payment = Payment.objects.get()
        self.assertRedirects(response, reverse("payment_page", args=(payment.pk,)))

        complete_payment(payment)
        event_notification_listener(payment)

        guest_confirmation.delay.assert_called_once()

        rsvp = RSVP.objects.get(
            person=self.already_rsvped, event=self.simple_paying_event
        )
        self.assertEqual(guest_confirmation.delay.call_args[0][0], rsvp.pk)

    @mock.patch("agir.events.actions.rsvps.send_rsvp_notification")
    def test_can_rsvp_to_form_paying_event(self, rsvp_notification):
        self.client.force_login(self.person.role)

        response = self.client.get(
            reverse("rsvp_event", args=[self.form_paying_event.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            reverse("rsvp_event", args=[self.form_paying_event.pk]),
            data={"custom-field": "my own custom value"},
        )
        self.assertRedirects(response, reverse("pay_event"))

        submission = PersonFormSubmission.objects.get(
            person=self.person, form=self.subscription_form
        )

        response = self.client.get(reverse("pay_event"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(
            response, f'name="event" value="{self.form_paying_event.pk}"'
        )
        self.assertContains(response, f'name="submission" value="{submission.pk}"')
        self.assertContains(response, f'name="is_guest" value="False"')

        response = self.client.post(
            reverse("pay_event"),
            data={
                "event": self.form_paying_event.pk,
                "submission": submission.pk,
                "payment_mode": "check",
                **self.billing_information,
            },
        )

        payment = Payment.objects.get()
        self.assertRedirects(response, reverse("payment_page", args=(payment.pk,)))

        # fake payment confirmation
        complete_payment(payment)
        event_notification_listener(payment)

        self.assertIn(self.person, self.form_paying_event.attendees.all())

        rsvp_notification.delay.assert_called_once()
        rsvp = RSVP.objects.get(person=self.person, event=self.form_paying_event)
        self.assertEqual(rsvp_notification.delay.call_args[0][0], rsvp.pk)

        response = self.client.get(
            reverse("rsvp_event", args=[self.form_paying_event.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "my own custom value")

    @mock.patch("agir.events.actions.rsvps.send_guest_confirmation")
    def test_can_add_guest_to_form_paying_event(self, guest_confirmation):
        self.form_paying_event.allow_guests = True
        self.form_paying_event.save()
        self.client.force_login(self.already_rsvped.role)
        session = self.client.session

        response = self.client.get(
            reverse("rsvp_event", args=[self.form_paying_event.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            reverse("rsvp_event", args=[self.form_paying_event.pk]),
            data={"custom-field": "my guest custom value", "is_guest": "yes"},
        )
        self.assertRedirects(response, reverse("pay_event"))

        submission = PersonFormSubmission.objects.filter(
            person=self.already_rsvped
        ).latest("created")

        response = self.client.get(reverse("pay_event"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(
            response, f'name="event" value="{self.form_paying_event.pk}"'
        )
        self.assertContains(response, f'name="submission" value="{submission.pk}"')
        self.assertContains(response, f'name="is_guest" value="True"')

        response = self.client.post(
            reverse("pay_event"),
            data={
                "event": self.form_paying_event.pk,
                "submission": submission.pk,
                "payment_mode": "check",
                "is_guest": "yes",
                **self.billing_information,
            },
        )

        payment = Payment.objects.get()
        self.assertRedirects(response, reverse("payment_page", args=(payment.pk,)))

        complete_payment(payment)
        event_notification_listener(payment)

        self.assertEqual(2, self.form_paying_event.participants)

        guest_confirmation.delay.assert_called_once()

        rsvp = RSVP.objects.get(
            person=self.already_rsvped, event=self.form_paying_event
        )
        self.assertEqual(guest_confirmation.delay.call_args[0][0], rsvp.pk)

        response = self.client.get(
            reverse("rsvp_event", args=[self.form_paying_event.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "my guest custom value")

    def test_can_retry_payment_on_rsvp(self):
        self.client.force_login(self.person.role)

        self.client.post(reverse("rsvp_event", args=[self.simple_paying_event.pk]))
        response = self.client.post(
            reverse("pay_event"),
            data={
                "event": self.simple_paying_event.pk,
                "payment_mode": "system_pay",
                **self.billing_information,
            },
        )

        payment = Payment.objects.get()
        self.assertRedirects(response, reverse("payment_page", args=[payment.pk]))

        response = self.client.get(reverse("payment_retry", args=[payment.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_rsvp_if_not_authorized_for_form(self):
        tag = PersonTag.objects.create(label="tag")
        self.subscription_form.required_tags.add(tag)
        self.subscription_form.unauthorized_message = "SENTINEL"
        self.subscription_form.save()

        self.client.force_login(self.person.role)

        event_url = reverse("view_event", kwargs={"pk": self.form_event.pk})
        rsvp_url = reverse("rsvp_event", kwargs={"pk": self.form_event.pk})

        response = self.client.get(rsvp_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "SENTINEL")

        response = self.client.post(
            rsvp_url, data={"custom-field": "another custom value"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("form", response.context_data)

    @mock.patch("agir.events.actions.rsvps.send_rsvp_notification")
    def test_can_rsvp_if_authorized_for_form(self, rsvp_notification):
        tag = PersonTag.objects.create(label="tag")
        self.person.tags.add(tag)
        self.subscription_form.required_tags.add(tag)
        self.subscription_form.unauthorized_message = "SENTINEL"
        self.subscription_form.save()

        self.client.force_login(self.person.role)

        event_url = reverse("view_event", kwargs={"pk": self.form_event.pk})
        rsvp_url = reverse("rsvp_event", kwargs={"pk": self.form_event.pk})

        response = self.client.get(rsvp_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotContains(response, "SENTINEL")
        self.assertIn("form", response.context_data)

        response = self.client.post(
            rsvp_url, data={"custom-field": "another custom value"}
        )
        self.assertRedirects(response, event_url)
        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.SUCCESS)

        self.person.refresh_from_db()
        self.assertIn(self.person, self.form_event.attendees.all())
        self.assertEqual(self.person.meta["custom-field"], "another custom value")
        self.assertEqual(2, self.form_event.participants)

        rsvp_notification.delay.assert_called_once()

        rsvp = RSVP.objects.get(person=self.person, event=self.form_event)
        self.assertEqual(rsvp_notification.delay.call_args[0][0], rsvp.pk)

    def test_cannot_rsvp_if_form_is_closed(self):
        self.client.force_login(self.person.role)
        self.form_event.subscription_form.end_time = timezone.now() - timezone.timedelta(
            days=1
        )
        self.form_event.subscription_form.save()

        res = self.client.get(reverse("rsvp_event", kwargs={"pk": self.form_event.pk}))
        self.assertContains(res, "Ce formulaire est maintenant fermé.")

        res = self.client.post(
            reverse("rsvp_event", kwargs={"pk": self.form_event.pk}),
            data={"custom-field": "another custom value"},
        )
        self.assertContains(res, "Ce formulaire est maintenant fermé.")

    def test_cannot_rsvp_if_external(self):
        self.person.is_insoumise = False
        self.person.save()
        self.client.force_login(self.person.role)

        url = reverse("view_event", kwargs={"pk": self.simple_event.pk})

        # cannot see the form
        response = self.client.get(url)
        self.assertNotIn("Participer à cet événement", response.content.decode())

        # cannot actually post the form
        self.client.post(reverse("rsvp_event", kwargs={"pk": self.simple_event.pk}))
        self.assertNotIn(self.person, self.simple_event.attendees.all())

    def test_cannot_rsvp_if_form_is_yet_to_open(self):
        self.client.force_login(self.person.role)
        self.form_event.subscription_form.start_time = timezone.now() + timezone.timedelta(
            days=1
        )
        self.form_event.subscription_form.save()

        res = self.client.get(reverse("rsvp_event", kwargs={"pk": self.form_event.pk}))
        self.assertContains(res, "est pas encore ouvert.")

        res = self.client.post(
            reverse("rsvp_event", kwargs={"pk": self.form_event.pk}),
            data={"custom-field": "another custom value"},
        )
        self.assertContains(res, "est pas encore ouvert.")

    @mock.patch("agir.events.actions.rsvps.send_rsvp_notification")
    def test_not_billed_if_free_pricing_to_zero(self, rsvp_notification):
        self.client.force_login(self.person.role)

        self.form_event.payment_parameters = {"free_pricing": "price"}
        self.form_event.save()

        event_url = reverse("view_event", kwargs={"pk": self.form_event.pk})
        rsvp_url = reverse("rsvp_event", kwargs={"pk": self.form_event.pk})

        response = self.client.get(rsvp_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            rsvp_url, data={"custom-field": "another custom value", "price": "0"}
        )
        self.assertRedirects(response, event_url)
        msgs = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(msgs[0].level, messages.SUCCESS)

        self.person.refresh_from_db()
        self.assertIn(self.person, self.form_event.attendees.all())
        self.assertEqual(self.person.meta["custom-field"], "another custom value")
        self.assertEqual(2, self.form_event.participants)

        rsvp_notification.delay.assert_called_once()

        rsvp = RSVP.objects.get(person=self.person, event=self.form_event)
        self.assertEqual(rsvp_notification.delay.call_args[0][0], rsvp.pk)


class PricingTestCase(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com")

        self.now = now = timezone.now().astimezone(timezone.get_default_timezone())
        day = timezone.timedelta(days=1)
        hour = timezone.timedelta(hours=1)

        self.event = Event.objects.create(
            name="Simple Event",
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
        )

    def test_pricing_display(self):
        self.assertEqual(self.event.get_price_display(), None)

        self.event.payment_parameters = {"price": 1000}
        self.assertEqual(self.event.get_price_display(), "10,00 €")

        self.event.payment_parameters = {"free_pricing": "value"}
        self.assertEqual(self.event.get_price_display(), "Prix libre")

        self.event.payment_parameters = {
            "mappings": [
                {
                    "mapping": [
                        {"values": ["A"], "price": 100},
                        {"values": ["B"], "price": 200},
                    ],
                    "fields": ["f"],
                }
            ]
        }
        self.assertEqual(self.event.get_price_display(), "de 1,00 à 2,00 €")

        self.event.payment_parameters["price"] = 1000
        self.assertEqual(self.event.get_price_display(), "de 11,00 à 12,00 €")

        self.event.payment_parameters["free_pricing"] = "value"
        self.assertEqual(
            self.event.get_price_display(), "de 11,00 à 12,00 € + montant libre"
        )

    def test_simple_pricing_event(self):
        self.event.payment_parameters = {"price": 1000}
        self.assertEqual(self.event.get_price(), 1000)

        self.event.payment_parameters["mappings"] = [
            {
                "mapping": [
                    {"values": ["A"], "price": 100},
                    {"values": ["B"], "price": 200},
                ],
                "fields": ["mapping_field"],
            }
        ]
        sub = PersonFormSubmission()

        sub.data = {"mapping_field": "A"}
        self.assertEqual(self.event.get_price(sub.data), 1100)
        sub.data = {"mapping_field": "B"}
        self.assertEqual(self.event.get_price(sub.data), 1200)

        self.event.payment_parameters["free_pricing"] = "price_field"

        sub.data = {"mapping_field": "A", "price_field": 5}
        self.assertEqual(self.event.get_price(sub.data), 1600)
        sub.data = {"mapping_field": "B", "price_field": 15}
        self.assertEqual(self.event.get_price(sub.data), 2700)


class CalendarPageTestCase(TestCase):
    def setUp(self):
        self.calendar = Calendar.objects.create(name="My calendar", slug="my_calendar")

        now = timezone.now()
        day = timezone.timedelta(days=1)
        hour = timezone.timedelta(hours=1)

        for i in range(20):
            e = Event.objects.create(
                name="Event {}".format(i),
                calendar=self.calendar,
                start_time=now + i * day,
                end_time=now + i * day + hour,
            )
            CalendarItem.objects.create(event=e, calendar=self.calendar)

    def can_view_page(self):
        # can show first page
        res = self.client.get("/agenda/my_calendar/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # there's a next button
        self.assertContains(res, '<li class="next">')
        self.assertContains(res, 'href="?page=2"')

        # there's no previous button
        self.assertNotContains(res, '<li class="previous">')

        # can display second page
        res = self.client.get("/agenda/my_calendar/?page=2")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # there's a next button
        self.assertNotContains(res, '<li class="next">')

        # there's no previous button
        self.assertContains(res, '<li class="previous">')
        self.assertContains(res, 'href="?page=1"')


class ExternalRSVPTestCase(TestCase):
    def setUp(self):
        self.now = now = timezone.now().astimezone(timezone.get_default_timezone())
        day = timezone.timedelta(days=1)
        hour = timezone.timedelta(hours=1)
        self.person = Person.objects.create_person("test@test.com", is_insoumise=False)
        self.subtype = EventSubtype.objects.create(
            type=EventSubtype.TYPE_PUBLIC_ACTION, allow_external=True
        )
        self.event = Event.objects.create(
            name="Simple Event",
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
            subtype=self.subtype,
        )

    def test_cannot_external_rsvp_if_does_not_allow_external(self):
        self.subtype.allow_external = False
        self.subtype.save()
        subscription_token = subscription_confirmation_token_generator.make_token(
            email="test1@test.com"
        )
        query_args = {"email": "test1@test.com", "token": subscription_token}
        self.client.get(
            reverse("external_rsvp_event", args=[self.event.pk])
            + "?"
            + urlencode(query_args)
        )

        with self.assertRaises(Person.DoesNotExist):
            Person.objects.get(email="test1@test.com")

    def test_can_rsvp(self):
        res = self.client.get(reverse("view_event", args=[self.event.pk]))
        self.assertNotContains(res, "Se connecter pour")
        self.assertContains(res, "Participer à cet événement")

        self.client.post(
            reverse("external_rsvp_event", args=[self.event.pk]),
            data={"email": self.person.email},
        )
        self.assertEqual(self.person.rsvps.all().count(), 0)

        subscription_token = subscription_confirmation_token_generator.make_token(
            email=self.person.email
        )
        query_args = {"email": self.person.email, "token": subscription_token}
        self.client.get(
            reverse("external_rsvp_event", args=[self.event.pk])
            + "?"
            + urlencode(query_args)
        )

        self.assertEqual(self.person.rsvps.first().event, self.event)

    def test_can_rsvp_without_account(self):
        self.client.post(
            reverse("external_rsvp_event", args=[self.event.pk]),
            data={"email": "test1@test.com"},
        )

        with self.assertRaises(Person.DoesNotExist):
            Person.objects.get(email="test1@test.com")

        subscription_token = subscription_confirmation_token_generator.make_token(
            email="test1@test.com"
        )
        query_args = {"email": "test1@test.com", "token": subscription_token}
        self.client.get(
            reverse("external_rsvp_event", args=[self.event.pk])
            + "?"
            + urlencode(query_args)
        )

        self.assertEqual(
            Person.objects.get(email="test1@test.com").rsvps.first().event, self.event
        )
        self.assertEqual(Person.objects.get(email="test1@test.com").is_insoumise, False)
