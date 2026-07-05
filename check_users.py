
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import CustomUser

def main():
    users = CustomUser.objects.all()
    print("All Users:")
    print("-" * 50)
    for user in users:
        print(f"Email: {user.email}")
        print(f"Full Name: {user.full_name}")
        print(f"Role: {user.role}")
        print(f"Is Active: {user.is_active}")
        print(f"Is Staff: {user.is_staff}")
        print("-" * 50)


if __name__ == '__main__':
    main()
