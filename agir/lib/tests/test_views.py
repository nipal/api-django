from pathlib import Path

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agir.events.models import Event, OrganizerConfig
from agir.groups.models import SupportGroup, Membership
from agir.people.models import Person

IMG_TEST_DIR = Path(__file__).parent / "data"


class ImageSizeWarningTestCase(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test_other.com")
        self.role = self.person.role
        self.group = SupportGroup.objects.create(name="Group name")
        Membership.objects.create(
            supportgroup=self.group, person=self.person, is_manager=True
        )

        self.now = now = timezone.now().astimezone(timezone.get_default_timezone())
        self.day = day = timezone.timedelta(days=1)

        self.organized_event = Event.objects.create(
            name="Organized event", start_time=now + day, end_time=now + 2 * day
        )
        OrganizerConfig.objects.create(
            event=self.organized_event, person=self.person, is_creator=True
        )

        self.past_event = Event.objects.create(
            name="past Event",
            # subtype=self.subtype,
            start_time=now - 2 * day,
            end_time=now - 1 * day,
        )
        OrganizerConfig.objects.create(
            event=self.past_event, person=self.person, is_creator=True
        )
        self.person.save()

    def test_image_size_warning_dimension(self):
        """
        Test ImageSizeWarningMixin dans des vues.

        Les test sur chaque vue sont:
            - pas de problème si aucun fichier n'est uploadé
            - un message notifie l'utilisateur en cas de mauvaise dimension de l'image
            - pas de message si les dimensions sont bonne
        :return:
        """

        def functional_test_on_view(url_from, url_to, data, image_field):
            """
            La fonction qui effectue les teste sur une vue

            :param url_from: l'url de la vue contenant le formulaire
            :param url_to: l'url de la vue atteinte après le formulaire
            :param data: les champ du formulaire sous forme de dictionnaire
            :param image_field: le nom du champ de l'image dans le formulaire
            :return:
            """
            # test sans fichier
            response = self.client.post(url_from, data)
            self.assertRedirects(response, url_to)

            # test mauvaise dimensions
            with open(IMG_TEST_DIR / "wrong_dimension.jpg", "rb") as f:
                data.update({image_field: f})
                response = self.client.post(url_from, data, follow=True)
            self.assertContains(response, "Attention, les dimensions de l")

            # test mauvaise dimensions
            with open(IMG_TEST_DIR / "right_dimension.png", "rb") as f:
                data.update({image_field: f})
                response = self.client.post(url_from, data, follow=True)
            self.assertNotContains(response, "Attention, les dimensions de l")

        self.client.force_login(self.person.role)

        start_str = self.organized_event.start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_str = self.organized_event.end_time.strftime("%Y-%m-%d %H:%M:%S")
        event_post_data = {
            "name": "enter event name here",
            "start_time": start_str,
            "end_time": end_str,
            "contact_email": "a@ziefzji.fr",
            "contact_phone": "06 06 06 06 06",
            "location_name": "somewhere",
            "location_address1": "over",
            "location_zip": "the",
            "location_city": "rainbow",
            "location_country": "FR",
            "image_accept_license": True,
        }
        post_data = {"accept_license": True}

        edit_event_url = reverse("edit_event", args=[self.organized_event.pk])
        manage_event_url = reverse("manage_event", args=[self.organized_event.pk])

        edit_report_event_url = reverse("edit_event_report", args=[self.past_event.pk])
        manage_report_event_url = reverse("manage_event", args=[self.past_event.pk])

        functional_test_on_view(
            edit_event_url, manage_event_url, event_post_data, "image"
        )
        functional_test_on_view(
            edit_report_event_url, manage_report_event_url, post_data, "report_image"
        )
