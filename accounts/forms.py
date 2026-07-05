from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from .models import JobPosition
from .services import AccountProfileService


CustomUser = get_user_model()


class BootstrapFormMixin:
    def _apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'form-check-input'
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs['class'] = 'form-select'
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs['class'] = 'form-control'
            else:
                widget.attrs['class'] = 'form-control'


class CustomLoginForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(
        label='Identifier',
        help_text='Enter your username or email address.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].help_text = ''
        self._apply_bootstrap()


class StaffForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'display_name', 'username', 'email', 'phone_number', 'role', 'positions']

    def __init__(self, *args, **kwargs):
        allowed_roles = kwargs.pop('allowed_roles', ['owner', 'admin', 'manager', 'staff'])
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [choice for choice in self.fields['role'].choices if choice[0] in allowed_roles]
        self.fields['positions'].queryset = JobPosition.objects.filter(is_active=True).order_by('department', 'name')
        self.fields['positions'].required = False
        self.fields['username'].required = True
        self.fields['positions'].help_text = 'Select one or more operational job positions.'
        self.fields['username'].help_text = 'Temporary username. The user can change it on first login.'
        self.fields['email'].help_text = 'Temporary or personal email address.'
        self.fields['password1'].label = 'Temporary Password'
        self.fields['password2'].label = 'Confirm Temporary Password'
        self._apply_bootstrap()

    def clean_username(self):
        return AccountProfileService.validate_username(username=self.cleaned_data.get('username'))

    def clean_email(self):
        return AccountProfileService.validate_email(email=self.cleaned_data.get('email'))


class StaffUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'display_name', 'username', 'email', 'phone_number', 'role', 'positions', 'is_active']

    def __init__(self, *args, **kwargs):
        allowed_roles = kwargs.pop('allowed_roles', ['owner', 'admin', 'manager', 'staff'])
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [choice for choice in self.fields['role'].choices if choice[0] in allowed_roles]
        self.fields['positions'].queryset = JobPosition.objects.filter(is_active=True).order_by('department', 'name')
        self.fields['positions'].required = False
        self.fields['username'].required = True
        self._apply_bootstrap()

    def clean_username(self):
        return AccountProfileService.validate_username(username=self.cleaned_data.get('username'), user=self.instance)

    def clean_email(self):
        return AccountProfileService.validate_email(email=self.cleaned_data.get('email'), user=self.instance)


class FirstLoginSetupForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(label='Personal Email Address')
    username = forms.CharField(label='Username', max_length=150)
    new_password1 = forms.CharField(label='New Password', widget=forms.PasswordInput)
    new_password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    phone_number = forms.CharField(label='Phone Number', max_length=20, required=False)
    profile_photo = forms.ImageField(label='Profile Photo', required=False)
    display_name = forms.CharField(label='Display Name', max_length=255, required=False)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

    def clean_username(self):
        return AccountProfileService.validate_username(username=self.cleaned_data.get('username'), user=self.user)

    def clean_email(self):
        return AccountProfileService.validate_email(email=self.cleaned_data.get('email'), user=self.user)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password1') != cleaned_data.get('new_password2'):
            self.add_error('new_password2', 'Password confirmation does not match.')
        return cleaned_data


class ProfileUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['display_name', 'phone_number', 'profile_photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class ChangeUsernameForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(max_length=150)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

    def clean_username(self):
        return AccountProfileService.validate_username(username=self.cleaned_data.get('username'), user=self.user)


class ChangeEmailForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(label='Email Address')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

    def clean_email(self):
        return AccountProfileService.validate_email(email=self.cleaned_data.get('email'), user=self.user)


class CustomPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class AdminResetPasswordForm(forms.Form):
    confirm_reset = forms.BooleanField(
        label='Generate a new temporary password and require first-login setup',
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['confirm_reset'].widget.attrs['class'] = 'form-check-input'
