from accounts.models import CustomUser
CustomUser.objects.create_user(
    email='newuser@example.com',
    password='password123',
    full_name='New User',
    phone_number='1234567890',
    role='staff'  # or 'admin' or 'owner'
)