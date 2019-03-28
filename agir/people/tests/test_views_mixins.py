from django.test import TestCase
from rest_framework.reverse import reverse

from agir.people.models import Person


class NavsProfileMixinTestCase(TestCase):
    def setUp(self):
        super().setUp()

        self.person = Person.objects.create_person("test@test.com", is_insoumise=True)
        self.client.force_login(self.person.role)

    def test_can_see_insoumis_menue(self):
        self.person.is_insoumise = True
        self.person.save()

        response = self.client.get(reverse("profile_contact"))

        self.assertContains(response, reverse("profile_personal"))
        self.assertContains(response, reverse("profile_contact"))
        self.assertContains(response, reverse("profile_preferences"))
        self.assertContains(response, reverse("profile_skills"))
        self.assertContains(response, reverse("profile_involvement"))
        self.assertContains(response, reverse("profile_participation"))
        self.assertContains(response, reverse(("profile_privacy")))

        self.assertNotContains(response, reverse("profile_rejoin"))

    def test_can_see_not_insoumis_menue(self):
        self.person.is_insoumise = False
        self.person.save()

        response = self.client.get(reverse("profile_contact"))

        self.assertContains(response, reverse("profile_contact"))
        self.assertContains(response, reverse("profile_rejoin"))
        self.assertContains(response, reverse(("profile_privacy")))

        self.assertNotContains(response, reverse("profile_participation"))
        self.assertNotContains(response, reverse("profile_preferences"))
        self.assertNotContains(response, reverse("profile_skills"))
        self.assertNotContains(response, reverse("profile_personal"))
        self.assertNotContains(response, reverse("profile_involvement"))
