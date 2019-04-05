from django.urls import reverse

NAVS_PROFILE_IDENTITY = 0
NAVS_PROFILE_CONTACT = 10
NAVS_PROFILE_SKILLS = 20
NAVS_PROFILE_ACT = 30
NAVS_PROFILE_PREFERENCES = 40
NAVS_PROFILE_PARTICIPATION = 50
NAVS_PROFILE_BECOME_INSOUMISE = 60
NAVS_PROFILE_CONFIDENTIALITY = 70


class NavsProfileMixin(object):
    def get_context_data(self, **kwargs):

        is_insoumise = self.request.user.person.is_insoumise

        menu = []

        if is_insoumise:
            menu.extend(
                [
                    {
                        "title": "Mon identitée",
                        "link": reverse("personal_informations"),
                        "id": NAVS_PROFILE_IDENTITY,
                    }
                ]
            )

        menu.extend(
            [
                {
                    "title": "Contacts",
                    "link": reverse("profile_contact"),
                    "id": NAVS_PROFILE_CONTACT,
                }
            ]
        )

        if is_insoumise:
            menu.extend(
                [
                    {
                        "title": "Preférence de contacts",
                        "link": reverse("contact_preferences"),
                        "id": NAVS_PROFILE_PREFERENCES,
                    },
                    {
                        "title": "Compétences",
                        "link": reverse("skills"),
                        "id": NAVS_PROFILE_SKILLS,
                    },
                    {
                        "title": "J'agis",
                        "link": reverse("voluteer"),
                        "id": NAVS_PROFILE_ACT,
                    },
                    {
                        "title": "Participation",
                        "link": reverse("participation"),
                        "id": NAVS_PROFILE_PARTICIPATION,
                    },
                ]
            )

        if not is_insoumise:
            menu.extend(
                [
                    {
                        "title": "Devenir insoumis⋅e",
                        "link": reverse("become_insoumise"),
                        "id": NAVS_PROFILE_BECOME_INSOUMISE,
                    }
                ]
            )

        menu.extend(
            [
                {
                    "title": "Données personnelles",
                    "link": reverse("personal_data"),
                    "id": NAVS_PROFILE_CONFIDENTIALITY,
                }
            ]
        )

        return super().get_context_data(navs=menu, **kwargs)
