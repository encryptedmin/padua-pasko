import secrets
import string

from django.db import models
from django.db.models.functions import Lower
from django.core.exceptions import ValidationError


CODE_ALPHABET = string.ascii_uppercase.replace("I", "").replace("L", "").replace("O", "") + "23456789"


def generate_event_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(9))


class Event(models.Model):
    class Status(models.TextChoices):
        SETUP = "SETUP", "Setup"
        OPEN = "OPEN", "Open"
        REVEAL = "REVEAL", "Reveal"
        CLOSED = "CLOSED", "Closed"

    title = models.CharField(max_length=120, default="Family Bunutan")
    year = models.PositiveSmallIntegerField()
    budget_text = models.CharField(max_length=80, default="₱300–₱500")
    party_date = models.DateField(null=True, blank=True)
    code = models.CharField(max_length=9, default=generate_event_code)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.SETUP)

    def __str__(self) -> str:
        return f"{self.title} ({self.year})"


class Participant(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="participants")
    name = models.CharField(max_length=40)
    has_drawn = models.BooleanField(default=False)
    slip_taken = models.BooleanField(default=False)
    sealed_pick = models.TextField(null=True, blank=True)
    wish_list = models.TextField(blank=True, max_length=500)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), "event", name="bunutan_participant_name_ci_event_uniq"),
        ]
        ordering = ["name"]

    def clean(self) -> None:
        self.name = self.name.strip()
        super().clean()

    def save(self, *args, **kwargs) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError("Participant name cannot be empty.")
        if len(self.name) > 40:
            raise ValidationError("Participant name must be 40 characters or fewer.")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Exclusion(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="exclusions")
    a = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="exclusions_as_a")
    b = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="exclusions_as_b")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("event", "a", "b"), name="bunutan_exclusion_pair_uniq"),
        ]

    def clean(self) -> None:
        if self.a_id and self.b_id and self.a_id == self.b_id:
            raise ValidationError("A participant cannot be excluded from themselves.")
        if self.a_id and self.b_id and self.a.event_id != self.b.event_id:
            raise ValidationError("Both participants must belong to the same event.")
        if self.event_id and self.a_id and self.a.event_id != self.event_id:
            raise ValidationError("Participant A must belong to this event.")
        if self.event_id and self.b_id and self.b.event_id != self.event_id:
            raise ValidationError("Participant B must belong to this event.")

    def save(self, *args, **kwargs) -> None:
        if self.a_id and self.b_id and self.a_id > self.b_id:
            self.a_id, self.b_id = self.b_id, self.a_id
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.a} ↔ {self.b}"


class Reveal(models.Model):
    """A public pairing voluntarily shared by its giver."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reveals")
    giver = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="revealed_picks")
    receiver = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="revealed_as_receiver")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("event", "giver"), name="bunutan_reveal_giver_uniq"),
        ]

    def __str__(self) -> str:
        return f"{self.receiver} was {self.giver}'s monito/monita"
