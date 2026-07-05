
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import authenticate
from accounts.models import CustomUser

def main():
    print("Testing login test for staff@example.com:")
    user = authenticate(email='staff@example.com', password='staff123')

    if user:
        print("SUCCESS: Logged in as {}".format(user.full_name))
        print("Role: {}".format(user.role))
    else:
        print("FAILED: Authentication failed")
        print("Checking if user exists:")
        try:
            user_obj = CustomUser.objects.get(email='staff@example.com')
            print("User exists: {}".format(user_obj.email))
            print("Is active: {}".format(user_obj.is_active))
        except Exception as e:
            print("User doesn't exist: {}".format(e))


if __name__ == '__main__':
    main()
