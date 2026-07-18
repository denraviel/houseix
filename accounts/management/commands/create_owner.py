from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from getpass import getpass

User = get_user_model()


class Command(BaseCommand):
    help = "Create the initial HouseIX owner account."

    def handle(self, *args, **options):

        if User.objects.filter(role="owner").exists():
            self.stdout.write(
                self.style.WARNING("An owner account already exists.")
            )
            return

        email = input("Owner Email: ").strip()
        username = input("Username: ").strip()
        full_name = input("Full Name: ").strip()
        phone = input("Phone Number: ").strip()

        while True:
            password = getpass("Password: ")
            password2 = getpass("Confirm Password: ")

            if password != password2:
                self.stdout.write(
                    self.style.ERROR("Passwords do not match.")
                )
                continue

            break

        owner = User.objects.create_superuser(
            email=email,
            username=username,
            password=password,
        )

        owner.role = "owner"

        if hasattr(owner, "full_name"):
            owner.full_name = full_name

        if hasattr(owner, "phone_number"):
            owner.phone_number = phone

        if hasattr(owner, "first_login_required"):
            owner.first_login_required = False

        owner.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nOwner account created successfully!\nEmail: {email}"
            )
        )