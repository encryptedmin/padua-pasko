# Generated for the initial Bunutan data model.
import bunutan.models
import django.db.models.functions.text
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="Family Bunutan", max_length=120)),
                ("year", models.PositiveSmallIntegerField()),
                ("budget_text", models.CharField(default="₱300–₱500", max_length=80)),
                ("party_date", models.DateField(blank=True, null=True)),
                ("code", models.CharField(default=bunutan.models.generate_event_code, max_length=9)),
                ("status", models.CharField(choices=[("SETUP", "Setup"), ("OPEN", "Open"), ("REVEAL", "Reveal"), ("CLOSED", "Closed")], default="SETUP", max_length=8)),
            ],
        ),
        migrations.CreateModel(
            name="Participant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=40)),
                ("has_drawn", models.BooleanField(default=False)),
                ("slip_taken", models.BooleanField(default=False)),
                ("sealed_pick", models.TextField(blank=True, null=True)),
                ("wish_list", models.TextField(blank=True, max_length=500)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="bunutan.event")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Exclusion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("a", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exclusions_as_a", to="bunutan.participant")),
                ("b", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exclusions_as_b", to="bunutan.participant")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exclusions", to="bunutan.event")),
            ],
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower("name"), "event", name="bunutan_participant_name_ci_event_uniq"),
        ),
        migrations.AddConstraint(
            model_name="exclusion",
            constraint=models.UniqueConstraint(fields=("event", "a", "b"), name="bunutan_exclusion_pair_uniq"),
        ),
    ]
