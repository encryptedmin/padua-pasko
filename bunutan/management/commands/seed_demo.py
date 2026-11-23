from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bunutan.models import Event, Exclusion, Participant


class Command(BaseCommand):
    help = "Create a sample family gift exchange with sample participant names."

    def handle(self, *args, **options):
        event, _ = Event.objects.get_or_create(
            pk=1,
            defaults={"title": "Family Gift Exchange", "year": timezone.localdate().year},
        )
        if event.status != Event.Status.SETUP:
            raise CommandError("The demo event can only be seeded while it is in SETUP.")
        names = [
            "Mom",
            "Dad",
            "Sister Joy",
            "Brother Migs",
            "Grandma Nena",
            "Grandpa Ben",
            "Aunt Cora",
            "Uncle Jun",
            "Cousin Bea",
            "Cousin Nico",
        ]
        participants = {}
        for name in names:
            participant, _ = Participant.objects.get_or_create(event=event, name=name)
            participants[name] = participant
        a, b = sorted((participants["Mom"], participants["Dad"]), key=lambda person: person.pk)
        Exclusion.objects.get_or_create(event=event, a=a, b=b)
        self.stdout.write(self.style.SUCCESS(f"Demo ready: {event.title} with {len(participants)} participants."))
