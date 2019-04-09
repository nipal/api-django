import datetime
from unittest import mock

import re
from django.contrib.gis.geos import Point
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.http import base36_to_int, int_to_base36, urlencode
from phonenumber_field.phonenumber import to_python as to_phone_number
from rest_framework import status
from rest_framework.reverse import reverse

from agir.api.redis import using_redislite
from agir.events.models import Event, OrganizerConfig
from agir.groups.models import SupportGroup, Membership
from agir.lib.tests.mixins import FakeDataMixin
from agir.people.actions.validation_codes import _initialize_buckets
from agir.people.models import Person, PersonValidationSMS, generate_code
from agir.people.tasks import (
    send_confirmation_change_email,
    send_confirmation_merge_account,
)


class DashboardTestCase(FakeDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        paris_nd = Point(2.349_722, 48.853_056)  # ND de Paris

        self.person1 = Person.objects.create_person(
            "test@test.com", coordinates=paris_nd
        )
        self.person2 = Person.objects.create_person("test2@test.com")
        self.person3 = Person.objects.create_person("test3@test.com")
        now = timezone.now()
        day = timezone.timedelta(days=1)
        hour = timezone.timedelta(hours=1)
        self.event = Event.objects.create(
            name="__== test name ==__",
            start_time=now + 3 * day,
            end_time=now + 3 * day + 4 * hour,
            coordinates=paris_nd,
        )

        self.group1 = SupportGroup.objects.create(name="group1")
        Membership.objects.create(person=self.person1, supportgroup=self.group1)
        OrganizerConfig.objects.create(
            event=self.event, person=self.person2, as_group=self.group1
        )

        self.group2 = SupportGroup.objects.create(name="group2")
        Membership.objects.create(person=self.person1, supportgroup=self.group2)
        OrganizerConfig.objects.create(
            event=self.event, person=self.person3, as_group=self.group2
        )

    def test_same_event_is_not_suggested_multiple_times(self):
        self.client.force_login(self.person1.role)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, self.event.name, count=1)

    @mock.patch("agir.people.views.dashboard.geocode_person")
    def test_contains_everything(self, geocode_person):
        self.client.force_login(self.data["people"]["user2"].role)
        response = self.client.get(reverse("dashboard"))

        geocode_person.delay.assert_called_once()
        self.assertEqual(
            geocode_person.delay.call_args[0], (self.data["people"]["user2"].pk,)
        )

        # own email
        self.assertContains(response, "user2@example.com")
        # managed group
        self.assertContains(response, self.data["groups"]["user2_group"].name)
        # member groups
        self.assertContains(response, self.data["groups"]["user1_group"].name)
        # next events
        self.assertContains(response, self.data["events"]["user1_event1"].name)
        # events of group
        self.assertContains(response, self.data["events"]["user1_event2"].name)


class ProfileTestCase(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com", is_insoumise=False)
        self.person.add_email("test2@test.com")
        self.person_to_merge = Person.objects.create_person("merge@test.com")

        self.client.force_login(self.person.role)

    def test_can_load_message_preferences_page(self):
        res = self.client.get(reverse("contact"))

        # should show the current email address
        self.assertContains(res, "test@test.com")
        self.assertContains(res, "test2@test.com")

    def test_can_see_email_management(self):
        res = self.client.get(reverse("contact"))

        # should show the current email address
        self.assertContains(res, "test@test.com")
        self.assertContains(res, "test2@test.com")

    def test_can_add_delete_address(self):
        emails = list(self.person.emails.all())

        # should be possible to get the delete page for one of the two addresses, and to actually delete
        reverse("delete_email", args=[emails[1].pk])
        res = self.client.get(reverse("delete_email", args=[emails[1].pk]))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(reverse("delete_email", args=[emails[1].pk]))
        self.assertRedirects(res, reverse("contact"))

        # address should indeed be gone
        self.assertEqual(len(self.person.emails.all()), 1)
        self.assertEqual(self.person.emails.first(), emails[0])

        # both get and post should give 403 when there is only one primary address
        res = self.client.get(reverse("delete_email", args=[emails[1].pk]))
        self.assertRedirects(res, reverse("contact"))

        res = self.client.post(reverse("delete_email", args=[emails[1].pk]))
        self.assertRedirects(res, reverse("contact"))
        self.assertEqual(len(self.person.emails.all()), 1)

    @using_redislite
    @mock.patch("agir.people.forms.profile.send_confirmation_change_email")
    def test_can_add_address(self, patched_send_confirmation_change_email):
        old_mails = [e.address for e in self.person.emails.all()]
        new_mails = ["test3@test.com", "try@other.test", "TeST4@test.com"]
        regex_url = reverse("confirm_change_mail") + r'\?[^\s"]*token=[a-z0-9-]+'

        for i, email in enumerate(new_mails):
            res = self.client.post(
                reverse("manage_account"), data={"email_add_merge": email}
            )
            self.assertRedirects(
                res,
                reverse("confirm_merge_account_sent")
                + "?"
                + urlencode({"email": email, "is_merging": False}),
            )
            patched_send_confirmation_change_email.delay.assert_called_with(
                new_email=email, user_pk=str(self.person.pk)
            )

            send_confirmation_change_email(email, str(self.person.pk))
            url_confirm = re.search(regex_url, mail.outbox[i].body).group(0)
            self.assertIsNotNone(url_confirm)
            res = self.client.get(url_confirm)
            self.assertRedirects(res, reverse("contact"))
            self.assertEqual(str(self.person.emails.first()), email)

        self.assertCountEqual(
            [e.address for e in self.person.emails.all()], old_mails + new_mails
        )

    @using_redislite
    @mock.patch("agir.people.forms.profile.send_confirmation_merge_account")
    def test_merge_account_send_mail(self, patched_send_confirmation_merge_account):
        """On test que l'envoie de mail fonction lors d'une demande de fusion de compte
        """
        response = self.client.post(
            reverse("manage_account"),
            data={"email_add_merge": self.person_to_merge.email},
        )
        url_redirect = (
            reverse("confirm_merge_account_sent")
            + "?"
            + urlencode({"email": self.person_to_merge.email, "is_merging": True})
        )

        self.assertRedirects(response, url_redirect)
        patched_send_confirmation_merge_account.delay.assert_called_once()

    def test_recieve_and_click_merge_account_demand(self):
        regex_url = reverse("confirm_merge_account") + r'\?[^\s"]*token=[a-z0-9-]+'
        merge_emails = set(self.person_to_merge.emails.all())
        merge_pk = self.person_to_merge.pk

        send_confirmation_merge_account(self.person.pk, self.person_to_merge.pk)
        url_confirm = re.search(regex_url, mail.outbox[0].body).group(0)
        res = self.client.get(url_confirm)
        self.assertRedirects(res, reverse("dashboard"))
        with self.assertRaises(Person.DoesNotExist):
            Person.objects.get(pk=merge_pk)
        combined_emails = set(self.person.emails.all())
        self.assertTrue(merge_emails.issubset(combined_emails))

    def test_cannot_change_mail_if_time_expired(self):
        regex_token = r"token=(([0-9a-z]*)-([0-9a-f]*))"
        new_mail = "hello@iam.new"

        send_confirmation_change_email(new_mail, str(self.person.pk))
        match = re.search(regex_token, mail.outbox[0].body)
        ts = match.group(2)
        signature = match.group(3)
        token_expired = int_to_base36((base36_to_int(ts) - 8)) + "-" + signature
        params = {
            "new_email": new_mail,
            "user": str(self.person.pk),
            "token": token_expired,
        }
        ulr_expired = reverse("confirm_change_mail") + "?" + urlencode(params)
        res = self.client.get(ulr_expired)
        self.assertContains(res, "Il semble que celui-ci est expiré.")

    def test_cannot_change_mail_if_wrong_link(self):
        """
           Teste differente maniere de produire un liens de changement d'adresse email erroné.

           Pour que le liens les varbiable : (new_email, user, token) soient manquantes ou invalide
        """
        regex_token = r"token=(([0-9a-z]*)-([0-9a-f]*))"
        new_mail = "hello@iam.new"
        send_confirmation_change_email("new_mail", str(self.person.pk))
        match = re.search(regex_token, mail.outbox[0].body)

        # data erroné
        token = match.group(1)
        post_data = {"new_email": new_mail, "user": str(self.person.pk), "token": token}
        for key, val in post_data.items():
            wrong_data = post_data.copy()
            wrong_data.update({key: val[:-1]})
            ulr_wrong = reverse("confirm_change_mail") + "?" + urlencode(wrong_data)
            res = self.client.get(ulr_wrong)
            self.assertContains(res, "Il semble que celui-ci est invalide.")

        # data manquante
        token = match.group(1)
        post_data = {"new_email": new_mail, "user": str(self.person.pk), "token": token}
        for key, val in post_data.items():
            wrong_data = post_data.copy()
            wrong_data.pop(key)
            ulr_wrong = reverse("confirm_change_mail") + "?" + urlencode(wrong_data)
            res = self.client.get(ulr_wrong)
            self.assertContains(res, "Il semble que celui-ci est invalide.")

    def test_can_see_subscribed_field_if_insoumise(self):
        self.person.is_insoumise = True
        self.person.subscribed = False
        self.person.save()

        res = self.client.get(reverse("contact"))
        self.assertContains(res, "subscribed")

        res = self.client.post(reverse("contact"), data={"subscribed": "on"})
        self.person.refresh_from_db()
        self.assertEqual(self.person.subscribed, True)

    def test_can_stop_messages(self):
        self.person.is_insoumise = True
        self.person.subscribed = True
        self.person.subscribed_sms = True
        self.person.event_notifications = True
        self.person.group_notifications = True
        self.person.draw_notifications = True
        self.person.save()

        res = self.client.post(reverse("contact"), data={"no_mail": True})
        self.assertEqual(res.status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.subscribed, False)
        self.assertEqual(self.person.subscribed_sms, False)
        self.assertEqual(self.person.event_notifications, False)
        self.assertEqual(self.person.group_notifications, False)
        self.assertEqual(self.person.draw_participation, False)


class ProfileFormTestCase(TestCase):
    def setUp(self):
        self.sample_data = {
            "first_name": "Jean",
            "last_name": "Forgeron",
            "gender": "M",
            "location_address1": "",
            "location_address2": "",
            "location_city": "Paris",
            "location_zip": "75002",
            "location_country": "FR",
            "contact_phone": "+33612345678",
            "mandates": "[]",
        }

        self.person = Person.objects.create_person("test@test.com", **self.sample_data)
        self.client.force_login(self.person.role)

    def test_can_add_tag(self):
        response = self.client.post(
            reverse("skills"), {**self.sample_data, "info blogueur": "on"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("info blogueur", [tag.label for tag in self.person.tags.all()])

    @mock.patch("agir.people.forms.profile.geocode_person")
    def test_can_change_address(self, geocode_person):
        address_fields = {
            "location_address1": "73 boulevard Arago",
            "location_zip": "75013",
            "location_country": "FR",
            "location_city": "Paris",
        }

        response = self.client.post(
            reverse("personal_information"), {**self.sample_data, **address_fields}
        )
        self.assertRedirects(response, reverse("personal_information"))

        geocode_person.delay.assert_called_once()
        self.assertEqual(geocode_person.delay.call_args[0], (self.person.pk,))

        geocode_person.reset_mock()
        response = self.client.post(
            reverse("personal_information"),
            {
                **self.sample_data,
                "first_name": "Arthur",
                "last_name": "Cheysson",
                **address_fields,
            },
        )
        self.assertRedirects(response, reverse("personal_information"))
        geocode_person.delay.assert_not_called()

    def test_cannot_validate_form_without_country(self):
        del self.sample_data["location_country"]

        response = self.client.post(
            reverse("personal_information"), data=self.sample_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "has-error")

    def test_can_validate_without_zip_code_when_abroad(self):
        self.sample_data["location_city"] = "Berlin"
        self.sample_data["location_zip"] = ""
        self.sample_data["location_country"] = "DE"

        response = self.client.post(
            reverse("personal_information"), data=self.sample_data
        )
        self.assertNotContains(response, "Ce champ est obligatoire.", status_code=302)

    def test_cannot_validate_form_without_zip_code_when_in_france(self):
        self.sample_data["location_zip"] = ""

        response = self.client.post(
            reverse("personal_information"), data=self.sample_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "has-error")

    def test_weird_values_for_mandates_should_not_crash_the_form(self):
        del self.sample_data["mandates"]

        res = self.client.post(reverse("skills"), data=self.sample_data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        testing_values = ["", "hhfedhgyu", '"huihui"', '{"key": "value"}']

        for test_value in testing_values:
            res = self.client.post(
                reverse("skills"), data={**self.sample_data, "mandates": test_value}
            )
            self.assertEqual(
                res.status_code,
                status.HTTP_200_OK,
                msg=f"Mauvais statut pour mandates={test_value}",
            )


class ActivityAblebilityFormTestCases(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com")
        self.client.force_login(self.person.role)

    def test_form_is_displayed(self):
        url_form = reverse("skills")

        response = self.client.post(
            url_form,
            data={
                "occupation": "coucou",
                "associations": "dans la vie",
                "unions": "je",
                "party": "fait",
                "party_responsibility": "des",
                "other": "truc",
            },
            follow=True,
        )

        self.assertContains(
            response,
            "Lorsque nous cherchons des membres du mouvement avec des compétences",
        )


class InformationConfidentialityFormTestCases(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com")
        self.client.force_login(self.person.role)

    def test_form_is_displayed(self):
        url_form = reverse("personal_data")

        response = self.client.get(url_form)

        self.assertContains(response, "Attention cette action est irréversible !")


class InformationPersonalFormTestCases(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com")
        self.client.force_login(self.person.role)

    def test_form_is_displayed(self):
        url_form = reverse("personal_information")

        response = self.client.post(
            url_form,
            data={
                "first_name": "first_name",
                "last_name": "last_name",
                "gender": "M",
                "date_of_birth": "27/10/1992",
                "location_address1": "",
                "location_address2": "",
                "location_city": "",
                "location_zip": "00000",
                "location_country": "FR",
            },
            follow=True,
        )

        self.assertContains(
            response,
            "Ces informations nous permettrons de s'adresser à vous plus correctement",
        )

        self.person = Person.objects.get(pk=self.person.pk)
        self.assertEqual(self.person.first_name, "first_name")
        self.assertEqual(self.person.last_name, "last_name")
        self.assertEqual(self.person.gender, "M")
        self.assertEqual(self.person.date_of_birth, datetime.date(1992, 10, 27))
        self.assertEqual(self.person.location_address1, "")
        self.assertEqual(self.person.location_address2, "")
        self.assertEqual(self.person.location_city, "")
        self.assertEqual(self.person.location_zip, "00000")
        self.assertEqual(self.person.location_country, "FR")


class VolunteerFormTestCases(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person("test@test.com")
        self.client.force_login(self.person.role)

    def test_form_is_displayed(self):
        url_form = reverse("voluteer")

        response = self.client.post(
            url_form,
            data={
                "agir localement": "on",
                "agir listes électorales": "on",
                "volontaire_procurations": "on",
                "draw_participation": "on",
                "gender": "O",
            },
            follow=True,
        )

        self.person = Person.objects.get(pk=self.person.pk)
        self.assertTrue(self.person.draw_participation)
        self.assertEqual(self.person.gender, "O")
        self.assertContains(response, "N’attendez pas les consignes pour agir.")


class ExternalPersonPreferencesFormTestCases(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person(
            "test@test.com",
            is_insoumise=False,
            subscribed=False,
            subscribed_sms=False,
            group_notifications=False,
            event_notifications=False,
        )

    def test_form_is_displayed(self):
        self.client.force_login(self.person.role)
        url_form = reverse("become_insoumise")

        response = self.client.post(url_form, data={"is_insoumise": "on"}, follow=True)

        self.assertContains(
            response, "Ces informations nous permettrons de s'adresser à vous plus"
        )

        self.person = Person.objects.get(pk=self.person.pk)
        self.assertTrue(self.person.is_insoumise)

        # Inscription aux e-mail+sms d'informations
        self.assertTrue(self.person.subscribed)
        self.assertTrue(self.person.subscribed_sms)
        self.assertTrue(self.person.group_notifications)
        self.assertTrue(self.person.event_notifications)


class InformationContactFormTestCases(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person(
            "test@test.com",
            is_insoumise=True,
            subscribed=False,
            subscribed_sms=False,
            group_notifications=False,
            event_notifications=False,
        )
        self.client.force_login(self.person.role)

    def test_form_is_displayed(self):
        url_form = reverse("contact")

        response = self.client.post(
            url_form,
            data={
                "contact_phone": "0658985632",
                "subscribed_sms": "on",
                "subscribed": "on",
                "group_notifications": "on",
                "event_notifications": "on",
            },
            follow=True,
        )

        self.person = Person.objects.get(pk=self.person.pk)
        self.assertTrue(self.person.subscribed)
        self.assertTrue(self.person.subscribed_sms)
        self.assertTrue(self.person.group_notifications)
        self.assertTrue(self.person.event_notifications)

        self.assertContains(
            response,
            "Vous recevrez des SMS de la France insoumise comme des meeting près de chez vous ou des appels à volontaire...",
        )

        person = Person.objects.get(pk=self.person.pk)
        self.assertEqual(person.contact_phone, "0658985632")


@using_redislite
class SMSValidationTestCase(TestCase):
    def setUp(self):
        self.person = Person.objects.create_person(
            "test@example.com", contact_phone="0612345678"
        )
        self.client.force_login(self.person.role)

    def test_can_see_sms_page_when_not_validated(self):
        res = self.client.get(reverse("send_validation_sms"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_can_display_page_even_when_no_contact_phone(self):
        self.person.contact_phone = ""
        self.person.save()
        res = self.client.get(reverse("send_validation_sms"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_sms_sending_form_modify_phone_number(self):
        res = self.client.post(
            reverse("send_validation_sms"), {"contact_phone": "0687654321"}
        )
        self.assertRedirects(res, reverse("sms_code_validation"))

        self.person.refresh_from_db()
        self.assertEqual(self.person.contact_phone, to_phone_number("0687654321"))

    def test_cannot_validate_sms_form_without_number(self):
        res = self.client.post(reverse("send_validation_sms"), {})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.context_data["form"].has_error("contact_phone", "required"))

        res = self.client.post(reverse("send_validation_sms"), {"contact_phone": ""})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.context_data["form"].has_error("contact_phone", "required"))

    def test_cannot_validate_sms_form_with_fixed_number(self):
        res = self.client.post(
            reverse("send_validation_sms"), {"contact_phone": "01 42 85 68 98"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            res.context_data["form"].has_error("contact_phone", "mobile_only")
        )

    def test_cannot_validate_sms_form_with_foreign_number(self):
        res = self.client.post(
            reverse("send_validation_sms"), {"contact_phone": "+44 7554 456245"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            res.context_data["form"].has_error("contact_phone", "french_only")
        )

    def test_cannot_ask_sms_if_already_validated(self):
        self.person.contact_phone_status = Person.CONTACT_PHONE_VERIFIED
        self.person.save()

        send_sms_page = reverse("send_validation_sms")
        message_preferences_page = reverse("contact")

        response = self.client.get(send_sms_page)
        self.assertRedirects(response, message_preferences_page)

        response = self.client.post(send_sms_page)
        self.assertRedirects(response, message_preferences_page)

    def test_number_not_validated_when_changed(self):
        self.person.contact_phone_status = Person.CONTACT_PHONE_VERIFIED
        self.person.save()

        message_preferences_page = reverse("contact")

        res = self.client.post(
            message_preferences_page, {"contact_phone": "0687654321"}
        )
        self.assertRedirects(res, message_preferences_page)

        self.person.refresh_from_db()

        self.assertEqual(
            self.person.contact_phone_status, Person.CONTACT_PHONE_UNVERIFIED
        )

    @mock.patch("agir.people.forms.account.send_new_code")
    def test_can_send_sms(self, mock_send_new_code):
        send_sms_page = reverse("send_validation_sms")

        res = self.client.get(send_sms_page)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(
            send_sms_page, {"contact_phone": self.person.contact_phone.as_e164}
        )

        self.assertRedirects(res, reverse("sms_code_validation"))
        mock_send_new_code.assert_called_once()
        self.assertEqual(mock_send_new_code.call_args[0][0], self.person)

    def test_can_validate_phone_number(self):
        validate_code_page = reverse("sms_code_validation")

        validation_code = PersonValidationSMS.objects.create(
            person=self.person, phone_number=self.person.contact_phone
        )

        res = self.client.get(validate_code_page)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(validate_code_page, {"code": validation_code.code})

        self.assertRedirects(res, reverse("contact"))
        self.person.refresh_from_db()
        self.assertEqual(
            self.person.contact_phone_status, Person.CONTACT_PHONE_VERIFIED
        )

    def test_cannot_validate_with_wrong_code(self):
        validate_code_page = reverse("sms_code_validation")

        validation_code = PersonValidationSMS.objects.create(
            person=self.person, phone_number=self.person.contact_phone
        )

        other_code = validation_code.code

        while other_code == validation_code.code:
            other_code = generate_code()

        res = self.client.post(validate_code_page, {"code": other_code})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.person.refresh_from_db()
        self.assertEqual(
            self.person.contact_phone_status, Person.CONTACT_PHONE_UNVERIFIED
        )

    def test_cannot_validate_with_code_after_changing_number(self):
        validate_code_page = reverse("sms_code_validation")

        validation_code = PersonValidationSMS.objects.create(
            person=self.person, phone_number=self.person.contact_phone
        )
        self.person.contact_phone = "0687654321"
        self.person.save()

        res = self.client.post(validate_code_page, {"code": validation_code.code})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.person.refresh_from_db()
        self.assertEqual(
            self.person.contact_phone_status, Person.CONTACT_PHONE_UNVERIFIED
        )

    def test_redirects_to_next_after_validation(self):
        send_sms_page = reverse("send_validation_sms") + "?next=" + reverse("dashboard")
        res = self.client.post(
            send_sms_page, {"contact_phone": self.person.contact_phone.as_e164}
        )
        self.assertRedirects(
            res, reverse("sms_code_validation") + "?next=" + reverse("dashboard")
        )

        validate_code_page = (
            reverse("sms_code_validation") + "?next=" + reverse("dashboard")
        )
        validation_code = PersonValidationSMS.objects.create(
            person=self.person, phone_number=self.person.contact_phone
        )
        res = self.client.post(validate_code_page, {"code": validation_code.code})
        self.assertRedirects(res, reverse("dashboard"))


@using_redislite
class SMSRateLimitingTestCase(TestCase):
    def setUp(self):
        self.phone = "+33612345678"
        self.other_phone = "+33687654321"
        self.person1 = Person.objects.create_person(
            "test1@example.com", contact_phone=self.phone
        )
        self.person2 = Person.objects.create_person(
            "test2@example.com", contact_phone=self.phone
        )

    # TODO: ajouter un message d'erreur pour le rate limite des sms a moins que pas besoin...
    @override_settings(
        SMS_BUCKET_MAX=2,
        SMS_BUCKET_INTERVAL=600,
        SMS_BUCKET_IP_MAX=10,
        SMS_BUCKET_IP_INTERVAL=600,
    )
    @mock.patch("agir.lib.token_bucket.get_current_timestamp")
    def test_rate_limiting_on_sending_sms(self, current_timestamp):
        # reinitialize token buckets to make sure the change of settings is taken into account
        _initialize_buckets()

        send_sms_page = reverse("send_validation_sms")
        validate_code_page = reverse("sms_code_validation")

        data = {"contact_phone": self.phone}

        self.client.force_login(self.person1.role)

        # should work
        current_timestamp.return_value = 0
        res = self.client.post(send_sms_page, data)
        self.assertRedirects(res, validate_code_page)

        # should block with short term bucket
        current_timestamp.return_value = 10
        res = self.client.post(send_sms_page, data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            res.context_data["form"].has_error("contact_phone", "rate_limited")
        )

        # should work again
        current_timestamp.return_value = 70
        res = self.client.post(send_sms_page, data)
        self.assertRedirects(res, validate_code_page)

        # person and phone number buckets should be empty
        current_timestamp.return_value = 140
        res = self.client.post(send_sms_page, data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            res.context_data["form"].has_error("contact_phone", "rate_limited")
        )

        # should not be possible to ask for sms with other person with same number
        self.client.force_login(self.person2.role)
        current_timestamp.return_value = 210
        res = self.client.post(send_sms_page, data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            res.context_data["form"].has_error("contact_phone", "rate_limited")
        )

        # sixth try ==> but possible to try with another number
        current_timestamp.return_value = 280
        res = self.client.post(send_sms_page, {"contact_phone": self.other_phone})
        self.assertRedirects(res, validate_code_page)
