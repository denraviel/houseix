from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import CustomUser


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (kwargs.get('identifier') or username or '').strip()
        if not identifier or password is None:
            return None

        try:
            user = CustomUser.objects.get(Q(email__iexact=identifier) | Q(username__iexact=identifier))
        except CustomUser.DoesNotExist:
            CustomUser().set_password(password)
            return None
        except CustomUser.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
