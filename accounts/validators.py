from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    def validate(self, password, user=None):
        if not any(character.isupper() for character in password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not any(character.islower() for character in password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not any(character.isdigit() for character in password):
            raise ValidationError('Password must contain at least one number.')
        if password.isalnum():
            raise ValidationError('Password must contain at least one special character.')

    def get_help_text(self):
        return 'Your password must include uppercase, lowercase, numeric, and special characters.'
