from django import forms
from django.db.models import Q
from django.forms import modelformset_factory

from .models import (
    InspectionResult,
    InspectionTemplate,
    MaintenanceCategory,
    MaintenanceIssue,
    PerformanceRating,
    RoomInspectionChecklist,
    Task,
    TaskInspection,
)
from accounts.models import CustomUser
from django.utils import timezone
from .services import TaskAssignmentService


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'task_type', 'description', 'room', 'required_positions', 'assigned_to', 'priority', 'due_date', 'status', 'requires_inspection']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        required_positions = None
        if self.is_bound:
            required_position_ids = [value for value in self.data.getlist('required_positions') if value.isdigit()]
            if required_position_ids:
                self.fields['assigned_to'].queryset = TaskAssignmentService.assignment_candidates(
                    required_positions=self.fields['required_positions'].queryset.filter(pk__in=required_position_ids)
                )
            else:
                self.fields['assigned_to'].queryset = TaskAssignmentService.assignment_candidates()
        else:
            required_positions = getattr(self.instance, 'required_positions', None)
            self.fields['assigned_to'].queryset = TaskAssignmentService.assignment_candidates(required_positions=required_positions)
        self.fields['required_positions'].required = False
        self.fields['required_positions'].help_text = 'Optional. Users with at least one matching position can be assigned.'
        self.fields['assigned_to'].help_text = 'Only staff matching at least one required position can be assigned.'
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.Textarea):
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        requires_inspection = cleaned_data.get('requires_inspection')
        TaskAssignmentService.validate_assignment(
            assigned_to=cleaned_data.get('assigned_to'),
            required_positions=cleaned_data.get('required_positions'),
        )
        if status == Task.STATUS_READY_FOR_REVIEW and not requires_inspection:
            self.add_error('status', 'Only inspection-required tasks can be marked Ready for Review.')
        return cleaned_data


class StaffTaskUpdateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['status', 'completion_notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        task = self.instance
        if task.requires_inspection:
            self.fields['status'].choices = [
                (Task.STATUS_PENDING, 'Pending'),
                (Task.STATUS_IN_PROGRESS, 'In Progress'),
                (Task.STATUS_READY_FOR_REVIEW, 'Ready for Review'),
            ]
        else:
            self.fields['status'].choices = [
                (Task.STATUS_PENDING, 'Pending'),
                (Task.STATUS_IN_PROGRESS, 'In Progress'),
                (Task.STATUS_COMPLETED, 'Completed'),
            ]
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.Textarea):
                field.widget.attrs['class'] = 'form-control'

    def clean_status(self):
        status = self.cleaned_data['status']
        if self.instance.requires_inspection and status == Task.STATUS_COMPLETED:
            raise forms.ValidationError('Inspection-required tasks must be marked Ready for Review first.')
        if not self.instance.requires_inspection and status == Task.STATUS_READY_FOR_REVIEW:
            raise forms.ValidationError('This task does not require inspection.')
        return status


class RoomInspectionChecklistForm(forms.ModelForm):
    class Meta:
        model = RoomInspectionChecklist
        fields = [
            'bed_properly_made',
            'bathroom_cleaned',
            'floor_cleaned',
            'towels_replaced',
            'trash_removed',
            'room_properly_arranged'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'


class PerformanceRatingForm(forms.ModelForm):
    class Meta:
        model = PerformanceRating
        fields = ['rating', 'comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.Textarea):
                field.widget.attrs['class'] = 'form-control'


class InspectionCreateForm(forms.ModelForm):
    class Meta:
        model = TaskInspection
        fields = ['template', 'inspector_notes']

    def __init__(self, *args, **kwargs):
        task = kwargs.pop('task', None)
        super().__init__(*args, **kwargs)
        queryset = InspectionTemplate.objects.filter(is_active=True).order_by('role', 'name')
        if task and task.assigned_to_id:
            worker_position_ids = task.assigned_to.positions.values_list('pk', flat=True)
            queryset = queryset.filter(
                Q(applicable_positions__isnull=True)
                | Q(applicable_positions__in=worker_position_ids)
            ).distinct()
        self.fields['template'].queryset = queryset
        self.fields['template'].widget.attrs['class'] = 'form-select'
        self.fields['inspector_notes'].widget.attrs['class'] = 'form-control'
        self.fields['inspector_notes'].widget.attrs['rows'] = 4
        if task and task.task_type == 'room_cleaning':
            self.fields['template'].initial = InspectionTemplate.objects.filter(
                is_active=True,
                name='Cleaner Room Inspection',
            ).first()


class TaskInspectionForm(forms.ModelForm):
    class Meta:
        model = TaskInspection
        fields = ['inspector_notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inspector_notes'].widget.attrs['class'] = 'form-control'
        self.fields['inspector_notes'].widget.attrs['rows'] = 4


class InspectionResultForm(forms.ModelForm):
    passed = forms.TypedChoiceField(
        choices=((True, 'Pass'), (False, 'Fail')),
        coerce=lambda value: value == 'True',
        widget=forms.RadioSelect,
    )

    class Meta:
        model = InspectionResult
        fields = ['passed', 'comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['comment'].required = False
        self.fields['comment'].widget.attrs['class'] = 'form-control'
        self.fields['comment'].widget.attrs['rows'] = 2

    def clean_passed(self):
        passed = self.cleaned_data.get('passed')
        if passed not in [True, False]:
            raise forms.ValidationError('Select pass or fail for this checklist item.')
        return passed


class InspectionFilterForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=InspectionTemplate.objects.filter(is_active=True).order_by('role', 'name'),
        required=False,
        empty_label='All templates',
    )
    result = forms.ChoiceField(
        required=False,
        choices=[('', 'All results')] + list(TaskInspection.RESULT_CHOICES),
    )
    worker = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role='staff').order_by('full_name'),
        required=False,
        empty_label='All staff',
    )
    search = forms.CharField(required=False, max_length=100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


InspectionResultFormSet = modelformset_factory(
    InspectionResult,
    form=InspectionResultForm,
    extra=0,
)


class MaintenanceBootstrapFormMixin:
    def _apply_bootstrap(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.RadioSelect):
                continue
            else:
                field.widget.attrs['class'] = 'form-control'


class MultipleMaintenanceFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleMaintenanceFileField(forms.FileField):
    widget = MultipleMaintenanceFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        if not data:
            return []
        return [single_file_clean(data, initial)]


class MaintenanceIssueForm(MaintenanceBootstrapFormMixin, forms.ModelForm):
    photos = MultipleMaintenanceFileField(
        required=False,
        widget=MultipleMaintenanceFileInput(attrs={'multiple': True}),
        help_text='Upload one or more JPEG, PNG, or WEBP images.',
    )
    photo_captions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Optional captions, one per line, matching the upload order.',
    )

    class Meta:
        model = MaintenanceIssue
        fields = [
            'title',
            'description',
            'category',
            'priority',
            'room',
            'requires_external_vendor',
            'requires_expense',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = MaintenanceCategory.objects.filter(is_active=True).order_by('name')
        self.fields['room'].required = False
        self._apply_bootstrap()


class MaintenanceIssueFilterForm(MaintenanceBootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, label='Search')
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses')] + list(MaintenanceIssue.STATUS_CHOICES))
    priority = forms.ChoiceField(required=False, choices=[('', 'All priorities')] + list(MaintenanceIssue.PRIORITY_CHOICES))
    category = forms.ModelChoiceField(
        queryset=MaintenanceCategory.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label='All categories',
    )
    room = forms.ModelChoiceField(
        queryset=Task._meta.get_field('room').remote_field.model.objects.order_by('room_number'),
        required=False,
        empty_label='All rooms',
    )
    assigned_to = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role='staff').order_by('full_name'),
        required=False,
        empty_label='All assigned staff',
    )
    reported_by = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role__in=['owner', 'admin', 'manager']).order_by('full_name'),
        required=False,
        empty_label='All reporters',
    )
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class MaintenanceIssueAssignForm(MaintenanceBootstrapFormMixin, forms.ModelForm):
    existing_task = forms.ModelChoiceField(
        queryset=Task.objects.filter(task_type='maintenance').select_related('room', 'assigned_to').order_by('-created_at'),
        required=False,
        empty_label='Link an existing maintenance task',
    )
    create_task = forms.BooleanField(required=False)
    task_due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    task_title = forms.CharField(required=False, max_length=200)
    task_description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    class Meta:
        model = MaintenanceIssue
        fields = ['assigned_to', 'priority', 'status', 'requires_external_vendor', 'requires_expense']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category_positions = self.instance.category.assignable_positions.filter(is_active=True) if getattr(self.instance, 'category_id', None) else None
        self.fields['assigned_to'].queryset = TaskAssignmentService.assignment_candidates(required_positions=category_positions)
        self.fields['assigned_to'].required = False
        self.fields['status'].choices = [
            (MaintenanceIssue.STATUS_ACKNOWLEDGED, 'Acknowledged'),
            (MaintenanceIssue.STATUS_ASSIGNED, 'Assigned'),
            (MaintenanceIssue.STATUS_IN_PROGRESS, 'In Progress'),
            (MaintenanceIssue.STATUS_WAITING_PARTS, 'Waiting Parts'),
            (MaintenanceIssue.STATUS_WAITING_VENDOR, 'Waiting Vendor'),
            (MaintenanceIssue.STATUS_COMPLETED, 'Completed'),
            (MaintenanceIssue.STATUS_REOPENED, 'Reopened'),
        ]
        self._apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        create_task = cleaned_data.get('create_task')
        existing_task = cleaned_data.get('existing_task')
        assigned_to = cleaned_data.get('assigned_to')
        task_due_date = cleaned_data.get('task_due_date')
        status = cleaned_data.get('status')
        if create_task and existing_task:
            raise forms.ValidationError('Choose either an existing task or create a new task.')
        if create_task and not assigned_to:
            self.add_error('assigned_to', 'Assign a staff user before creating a task.')
        if create_task and not task_due_date:
            self.add_error('task_due_date', 'Provide a due date for the linked task.')
        if status == MaintenanceIssue.STATUS_ASSIGNED and not assigned_to and not existing_task:
            self.add_error('assigned_to', 'Assigned status requires an assigned staff member or linked task.')
        category_positions = self.instance.category.assignable_positions.filter(is_active=True)
        TaskAssignmentService.validate_assignment(
            assigned_to=assigned_to,
            required_positions=category_positions,
        )
        if existing_task:
            TaskAssignmentService.validate_assignment(
                assigned_to=existing_task.assigned_to,
                required_positions=category_positions,
            )
        return cleaned_data


class MaintenanceIssueEscalateForm(MaintenanceBootstrapFormMixin, forms.Form):
    target_priority = forms.ChoiceField(
        required=False,
        choices=[('', 'Keep current priority')] + list(MaintenanceIssue.PRIORITY_CHOICES),
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class MaintenanceIssueVerifyForm(MaintenanceBootstrapFormMixin, forms.Form):
    decision = forms.ChoiceField(
        choices=[
            ('verified', 'Verified'),
            ('rejected', 'Reject Repair'),
        ],
        widget=forms.RadioSelect,
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class MaintenanceCategoryForm(MaintenanceBootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
