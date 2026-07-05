from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from tasks.models import Task

from .models import Expense, ExpenseCategory, FuelLog, RecurringExpense, Vendor


class BootstrapFormMixin:
    def _apply_bootstrap(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


class ExpenseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'category',
            'vendor',
            'task',
            'amount',
            'payment_method',
            'expense_date',
            'description',
            'receipt',
            'notes',
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True).order_by('name')
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True).order_by('name')
        self.fields['vendor'].required = False
        self.fields['task'].queryset = Task.objects.select_related('room', 'assigned_to').order_by('-created_at')
        self.fields['task'].required = False
        self.fields['task'].help_text = 'Optional link to an existing task.'
        self.fields['receipt'].help_text = 'Accepted file types: PDF, JPEG, PNG.'
        self._apply_bootstrap()


class ExpenseFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, label='Search')
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses')] + list(Expense.STATUS_CHOICES))
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label='All categories',
    )
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label='All vendors',
    )
    payment_method = forms.ChoiceField(
        required=False,
        choices=[('', 'All payment methods')] + list(Expense._meta.get_field('payment_method').choices),
    )
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class ApprovalActionForm(BootstrapFormMixin, forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class ExpenseCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

    def clean_code(self):
        return (self.cleaned_data['code'] or '').strip().upper()


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['name', 'phone', 'email', 'address', 'notes', 'is_active']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class RecurringExpenseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RecurringExpense
        fields = ['category', 'vendor', 'description', 'amount', 'frequency', 'next_due_date', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True).order_by('name')
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True).order_by('name')
        self.fields['vendor'].required = False
        self._apply_bootstrap()


class FuelLogForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FuelLog
        fields = [
            'expense',
            'generator_name',
            'opening_litres',
            'purchased_litres',
            'closing_litres',
            'generator_hours',
            'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        diesel_filter = Q(category__code='DIESEL') | Q(category__name__iexact='Diesel')
        queryset = Expense.objects.filter(diesel_filter, fuel_log__isnull=True).select_related('category', 'vendor')
        if getattr(self.user, 'role', None) == 'staff':
            queryset = queryset.filter(Q(recorded_by=self.user) | Q(created_by=self.user))
        self.fields['expense'].queryset = queryset.order_by('-expense_date', '-created_at')
        self.fields['expense'].help_text = 'Select a Diesel expense that is not already linked to a fuel log.'
        self._apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data:
            return cleaned_data
        fuel_log = FuelLog(
            expense=cleaned_data.get('expense'),
            generator_name=cleaned_data.get('generator_name') or '',
            opening_litres=cleaned_data.get('opening_litres') or 0,
            purchased_litres=cleaned_data.get('purchased_litres') or 0,
            closing_litres=cleaned_data.get('closing_litres') or 0,
            generator_hours=cleaned_data.get('generator_hours') or 0,
            notes=cleaned_data.get('notes') or '',
            recorded_by=self.user,
        )
        try:
            fuel_log.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, 'message_dict'):
                for field_name, messages in exc.message_dict.items():
                    for message in messages:
                        self.add_error(field_name if field_name in self.fields else None, message)
            else:
                for message in exc.messages:
                    self.add_error(None, message)
        return cleaned_data
