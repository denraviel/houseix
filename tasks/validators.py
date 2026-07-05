from django.core.validators import FileExtensionValidator


ALLOWED_MAINTENANCE_PHOTO_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']

_maintenance_photo_extension_validator = FileExtensionValidator(ALLOWED_MAINTENANCE_PHOTO_EXTENSIONS)


def validate_maintenance_photo(file_obj):
    _maintenance_photo_extension_validator(file_obj)
