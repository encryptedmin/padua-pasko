from django.db import migrations, models


def translate_default_event_titles(apps, schema_editor):
    Event = apps.get_model("bunutan", "Event")
    Event.objects.filter(title__in=("Family Bunutan", "Pasko ng Pamilya")).update(
        title="Family Gift Exchange"
    )


class Migration(migrations.Migration):
    dependencies = [("bunutan", "0002_reveal")]

    operations = [
        migrations.RunPython(translate_default_event_titles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="event",
            name="title",
            field=models.CharField(default="Family Gift Exchange", max_length=120),
        ),
    ]
