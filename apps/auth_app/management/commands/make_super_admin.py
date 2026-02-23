"""
Management command: make_super_admin

Usage:
    python manage.py make_super_admin admin@example.com

Sets the UserProfile.role to 'super_admin' for the given email.
The user must already exist in the database (have logged in at least once,
or been pre-created during registration).
"""

from django.core.management.base import BaseCommand, CommandError
from apps.auth_app.models import UserProfile


class Command(BaseCommand):
    help = "Promote a user to super_admin role."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Email of the user to promote")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()

        try:
            profile = UserProfile.objects.get(email=email)
        except UserProfile.DoesNotExist:
            raise CommandError(
                f'No UserProfile found for "{email}". '
                "Make sure the user has registered and verified their email."
            )

        if profile.role == "super_admin":
            self.stdout.write(self.style.WARNING(f'"{email}" is already a super_admin.'))
            return

        profile.role = "super_admin"
        profile.save(update_fields=["role"])

        self.stdout.write(
            self.style.SUCCESS(f'Successfully promoted "{email}" to super_admin.')
        )
