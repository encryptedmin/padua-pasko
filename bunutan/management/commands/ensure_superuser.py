import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction


class Command(BaseCommand):
    help = "Create the configured organizer superuser if it does not already exist."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        if not username or not password:
            return

        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        lookup = {username_field: username}
        if user_model._default_manager.filter(**lookup).exists():
            self.stdout.write(f"Organizer '{username}' already exists; unchanged.")
            return

        create_options = {username_field: username, "password": password}
        if any(field.name == "email" for field in user_model._meta.fields):
            create_options["email"] = email
        try:
            with transaction.atomic():
                user_model._default_manager.db_manager().create_superuser(**create_options)
        except IntegrityError:
            if user_model._default_manager.filter(**lookup).exists():
                self.stdout.write(f"Organizer '{username}' already exists; unchanged.")
                return
            raise
        self.stdout.write(f"Organizer '{username}' created.")
