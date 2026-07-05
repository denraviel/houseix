from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator


ALLOWED_RECEIPT_EXTENSIONS = ('pdf', 'jpg', 'jpeg', 'png')

validate_category_code = RegexValidator(
    regex=r'^[A-Z0-9_]+$',
    message='Code must contain only uppercase letters, numbers, and underscores.',
)

_receipt_extension_validator = FileExtensionValidator(ALLOWED_RECEIPT_EXTENSIONS)


def validate_receipt_file(value):
    if not value:
        return
    _receipt_extension_validator(value)


def validate_positive_value(value):
    if value is None or value <= 0:
        raise ValidationError('Value must be greater than zero.')
