from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bunutan.models import Event, Exclusion, Participant


class Command(BaseCommand):
    help = "Create a sample Bunutan event with Filipino family names."

    def handle(self, *args, **options):
        event, _ = Event.objects.get_or_create(
            pk=1,
            defaults={"title": "Pasko ng Pamilya", "year": timezone.localdate().year},
        )
        if event.status != Event.Status.SETUP:
            raise CommandError("The demo event can only be seeded while it is in SETUP.")
        names = [
            "Mama",
            "Papa",
            "Ate Joy",
            "Kuya Migs",
            "Lola Nena",
            "Lolo Ben",
            "Tita Cora",
            "Tito Jun",
            "Cousin Bea",
            "Cousin Nico",
        ]
        participants = {}
        for name in names:
            participant, _ = Participant.objects.get_or_create(event=event, name=name)
            participants[name] = participant
        a, b = sorted((participants["Mama"], participants["Papa"]), key=lambda person: person.pk)
        Exclusion.objects.get_or_create(event=event, a=a, b=b)
        self.stdout.write(self.style.SUCCESS(f"Demo ready: {event.title} with {len(participants)} participants."))
