from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.management import BaseCommand
from django.utils import timezone

from agir.events.models import Event, OrganizerConfig
from agir.groups.models import SupportGroup
from agir.people.models import Person

LOREM_IPSUM = """
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore
et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut
aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
culpa qui officia deserunt mollit anim id est laborum.
"""


class Command(BaseCommand):
    help = 'Fill the database with fake data. All passwords are "incredible password"'

    def handle(self, *args, **options):
        load_some_events()


def remove_jour_event():
    Event.objects.filter(name__startswith="jour ").delete()

    # for event in events:


def load_some_events():
    remove_jour_event()
    people = {
        "user1": Person.objects.get(email="user1@example.com"),
        "user2": Person.objects.get(email="user2@example.com"),
    }

    group1 = SupportGroup.objects.get(name="Groupe géré par user1")

    events = [
        Event.objects.create(
            name="jour 1",
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            coordinates=Point(5.36472, 43.30028),  # Saint-Marie-Majeure de Marseille
        ),
        Event.objects.create(
            name="jour 1 +6h",
            start_time=timezone.now() + timedelta(days=1, hours=6),
            end_time=timezone.now() + timedelta(days=1, hours=7),
            coordinates=Point(2.301944, 49.8944),  # ND d'Amiens
        ),
        Event.objects.create(
            name="jour 2",
            start_time=timezone.now() + timedelta(days=2),
            end_time=timezone.now() + timedelta(days=2, hours=1),
            coordinates=Point(7.7779, 48.5752),  # ND de Strasbourg
            report_content=LOREM_IPSUM,
        ),
        Event.objects.create(
            name="jour 2 +6h",
            start_time=timezone.now() + timedelta(days=2, hours=6),
            end_time=timezone.now() + timedelta(days=2, hours=7),
            coordinates=Point(7.7779, 48.5752),  # ND de Strasbourg
            report_content=LOREM_IPSUM,
        ),
        Event.objects.create(
            name="jour 4",
            start_time=timezone.now() + timedelta(days=4),
            end_time=timezone.now() + timedelta(days=4, hours=1),
            coordinates=Point(2.294444, 48.858333),  # Tour Eiffel
        ),
        Event.objects.create(
            name="jour 5",
            start_time=timezone.now() + timedelta(days=5),
            end_time=timezone.now() + timedelta(days=5, hours=1),
            coordinates=Point(5.36472, 43.30028),  # Saint-Marie-Majeure de Marseille
        ),
        Event.objects.create(
            name="jour 5 +6h",
            start_time=timezone.now() + timedelta(days=5, hours=6),
            end_time=timezone.now() + timedelta(days=5, hours=7),
            coordinates=Point(2.301944, 49.8944),  # ND d'Amiens
        ),
        Event.objects.create(
            name="jour 5 +9h",
            start_time=timezone.now() + timedelta(days=5, hours=9),
            end_time=timezone.now() + timedelta(days=5, hours=10),
            coordinates=Point(7.7779, 48.5752),  # ND de Strasbourg
            report_content=LOREM_IPSUM,
        ),
        Event.objects.create(
            name="jour 6",
            start_time=timezone.now() + timedelta(days=6),
            end_time=timezone.now() + timedelta(days=6, hours=1),
            coordinates=Point(5.36472, 43.30028),  # Saint-Marie-Majeure de Marseille
        ),
        Event.objects.create(
            name="jour 6 +3h",
            start_time=timezone.now() + timedelta(days=6, hours=3),
            end_time=timezone.now() + timedelta(days=6, hours=5),
            coordinates=Point(2.301944, 49.8944),  # ND d'Amiens
        ),
        Event.objects.create(
            name="jour 7 +1h",
            start_time=timezone.now() + timedelta(days=7, hours=1),
            end_time=timezone.now() + timedelta(days=7, hours=2),
            coordinates=Point(7.7779, 48.5752),  # ND de Strasbourg
            report_content=LOREM_IPSUM,
        ),
        Event.objects.create(
            name="jour 7 +1h",
            start_time=timezone.now() + timedelta(days=7, hours=1),
            end_time=timezone.now() + timedelta(days=7, hours=3),
            coordinates=Point(7.7779, 48.5752),  # ND de Strasbourg
            report_content=LOREM_IPSUM,
        ),
        Event.objects.create(
            name="jour 7 +3h",
            start_time=timezone.now() + timedelta(days=7, hours=3),
            end_time=timezone.now() + timedelta(days=7, hours=7),
            coordinates=Point(7.7779, 48.5752),  # ND de Strasbourg
            report_content=LOREM_IPSUM,
        ),
        Event.objects.create(
            name="jour 8",
            start_time=timezone.now() + timedelta(days=8),
            end_time=timezone.now() + timedelta(days=8, hours=3),
            coordinates=Point(2.294444, 48.858333),  # Tour Eiffel
        ),
    ]

    [
        OrganizerConfig.objects.create(
            event=event, person=people["user1"], is_creator=True, as_group=group1
        )
        for event in events
    ]
