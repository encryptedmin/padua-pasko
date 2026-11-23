import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bunutan", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Reveal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reveals", to="bunutan.event")),
                ("giver", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revealed_picks", to="bunutan.participant")),
                ("receiver", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revealed_as_receiver", to="bunutan.participant")),
            ],
        ),
        migrations.AddConstraint(
            model_name="reveal",
            constraint=models.UniqueConstraint(fields=("event", "giver"), name="bunutan_reveal_giver_uniq"),
        ),
    ]
