from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser, JobPosition


class CustomLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'


class StaffForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'phone_number', 'role', 'positions']

    def __init__(self, *args, **kwargs):
        allowed_roles = kwargs.pop('allowed_roles', ['owner', 'admin', 'manager', 'staff'])
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [c for c in self.fields['role'].choices if c[0] in allowed_roles]
        self.fields['positions'].queryset = JobPosition.objects.filter(is_active=True).order_by('department', 'name')
        self.fields['positions'].required = False
        self.fields['positions'].help_text = 'Select one or more operational job positions.'
        self.fields['password1'].label = "Password"
        self.fields['password2'].label = "Confirm Password"
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'


class StaffUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'phone_number', 'role', 'positions', 'is_active']

    def __init__(self, *args, **kwargs):
        allowed_roles = kwargs.pop('allowed_roles', ['owner', 'admin', 'manager', 'staff'])
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [c for c in self.fields['role'].choices if c[0] in allowed_roles]
        self.fields['positions'].queryset = JobPosition.objects.filter(is_active=True).order_by('department', 'name')
        self.fields['positions'].required = False
        self.fields['positions'].help_text = 'Select one or more operational job positions.'
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
