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

        response = self.client.get(reverse("contact"))

        self.assertContains(response, reverse("personal_information"))
        self.assertContains(response, reverse("contact"))
        self.assertContains(response, reverse("skills"))
        self.assertContains(response, reverse("voluteer"))
        self.assertContains(response, reverse(("personal_data")))

        self.assertNotContains(response, reverse("become_insoumise"))

    def test_can_see_not_insoumis_menue(self):
        self.person.is_insoumise = False
        self.person.save()

        response = self.client.get(reverse("contact"))

        self.assertContains(response, reverse("contact"))
        self.assertContains(response, reverse("become_insoumise"))
        self.assertContains(response, reverse(("personal_data")))

        self.assertNotContains(response, reverse("skills"))
        self.assertNotContains(response, reverse("personal_information"))
        self.assertNotContains(response, reverse("voluteer"))
