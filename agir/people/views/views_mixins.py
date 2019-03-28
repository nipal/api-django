from django.urls import reverse

NAVS_PROFILE_IDENTITY = 0
NAVS_PROFILE_CONTACT = 10
NAVS_PROFILE_SKILLS = 20
NAVS_PROFILE_ACT = 30
NAVS_PROFILE_PREFERENCE = 40
NAVS_PROFILE_PARTICIPATION = 50
NAVS_PROFILE_PRIVACY = 60


class NavsProfilMixin(object):
    def get_context_data(self, **kwargs):

        menu = [
            {
                "link": reverse("profile_perso"),
                "title": "Mon identitée",
                "id": NAVS_PROFILE_IDENTITY,
            },
            {
                "link": reverse("profile_contact"),
                "title": "Contacts",
                "id": NAVS_PROFILE_CONTACT,
            },
            {
                "link": reverse("profile_skills"),
                "title": "Compétences",
                "id": NAVS_PROFILE_SKILLS,
            },
            {
                "link": reverse("profile_involvement"),
                "title": "J'agis",
                "id": NAVS_PROFILE_ACT,
            },
            {
                "link": reverse("profile_preference"),
                "title": "Preférence de contactes",
                "id": NAVS_PROFILE_PREFERENCE,
            },
            {
                "link": reverse("profile_participation"),
                "title": "Participation",
                "id": NAVS_PROFILE_PARTICIPATION,
            },
            {
                "link": reverse("delete_account"),
                "title": "Supression du compte",
                "id": NAVS_PROFILE_PRIVACY,
            },
        ]

        return super().get_context_data(navs=menu, **kwargs)
