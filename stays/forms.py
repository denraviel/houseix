from django import forms

from .models import GuestStay


class GuestStayForm(forms.ModelForm):
    class Meta:
        model = GuestStay
        fields = ['customer', 'room', 'check_in_date', 'check_out_date', 'status', 'daily_rate']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and getattr(user, 'role', None) == 'staff':
            self.fields.pop('status', None)
            self.fields.pop('daily_rate', None)
        if 'daily_rate' in self.fields:
            self.fields['daily_rate'].required = False
        for _, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
