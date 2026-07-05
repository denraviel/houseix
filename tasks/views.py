from collections import OrderedDict
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from accounts.models import AuditLog, CustomUser
from expenses.models import ExpenseCategory

from .forms import (
    InspectionCreateForm,
    InspectionFilterForm,
    InspectionResultFormSet,
    MaintenanceCategoryForm,
    MaintenanceIssueAssignForm,
    MaintenanceIssueEscalateForm,
    MaintenanceIssueFilterForm,
    MaintenanceIssueForm,
    MaintenanceIssueVerifyForm,
    PerformanceRatingForm,
    StaffTaskUpdateForm,
    TaskForm,
    TaskInspectionForm,
)
from .models import (
    InspectionTemplateItem,
    MaintenanceActivity,
    MaintenanceCategory,
    MaintenanceIssue,
    PerformanceRating,
    Task,
    TaskInspection,
)
from .permissions import (
    MaintenanceAdminAccessMixin,
    MaintenanceModuleAccessMixin,
    can_create_maintenance_issue,
    can_edit_maintenance_issue,
    can_escalate_maintenance_issue,
    can_record_maintenance_expense,
    can_verify_maintenance_issue,
    can_view_maintenance_issue,
)
from .selectors import (
    accessible_maintenance_activities_queryset,
    accessible_maintenance_issues_queryset,
)
from .services import (
    InspectionCalculationService,
    InspectionWorkflowService,
    MaintenanceIssueService,
    MaintenanceReportService,
    MaintenanceWorkflowService,
)


@login_required
def task_list(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    tasks = Task.objects.select_related('room', 'assigned_to', 'created_by', 'previous_task').prefetch_related(
        'ratings',
        'assigned_to__positions',
        'required_positions',
    )
    total = tasks.count()
    pending = tasks.filter(status=Task.STATUS_PENDING).count()
    in_progress = tasks.filter(status=Task.STATUS_IN_PROGRESS).count()
    ready_for_review = tasks.filter(status=Task.STATUS_READY_FOR_REVIEW).count()
    completed = tasks.filter(status=Task.STATUS_COMPLETED).count()
    reopened = tasks.filter(status=Task.STATUS_REOPENED).count()
    overdue = tasks.filter(
        status__in=[Task.STATUS_PENDING, Task.STATUS_IN_PROGRESS, Task.STATUS_READY_FOR_REVIEW],
        due_date__lt=timezone.now().date(),
    ).count()
    context = {
        'tasks': tasks,
        'total': total,
        'pending': pending,
        'in_progress': in_progress,
        'ready_for_review': ready_for_review,
        'completed': completed,
        'reopened': reopened,
        'overdue': overdue,
        'show_audit_actions': request.user.role in ['owner', 'admin', 'manager'],
    }
    return render(request, 'tasks/task_list.html', context)


@login_required
def task_create(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if task.status in [Task.STATUS_COMPLETED, Task.STATUS_READY_FOR_REVIEW] and task.completed_at is None:
                task.completed_at = timezone.now()
            task.save()
            AuditLog.log(request.user, 'task_assigned', f"Assigned task {task.title} to {task.assigned_to.email}")
            messages.success(request, 'Task created successfully.')
            return redirect('task_list')
    else:
        form = TaskForm()
    return render(request, 'tasks/task_form.html', {'form': form})


@login_required
def task_update(request, pk):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            updated_task = form.save(commit=False)
            if updated_task.status in [Task.STATUS_COMPLETED, Task.STATUS_READY_FOR_REVIEW] and updated_task.completed_at is None:
                updated_task.completed_at = timezone.now()
            updated_task.save()
            AuditLog.log(request.user, 'task_updated', f"Updated task {task.title}")
            messages.success(request, 'Task updated successfully.')
            return redirect('task_list')
    else:
        form = TaskForm(instance=task)
    return render(request, 'tasks/task_form.html', {'form': form, 'task': task})


@login_required
def task_delete(request, pk):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        AuditLog.log(request.user, 'task_deleted', f"Deleted task {task.title}")
        task.delete()
        messages.success(request, 'Task deleted successfully.')
        return redirect('task_list')
    return render(request, 'tasks/task_confirm_delete.html', {'task': task})


@login_required
def my_tasks(request):
    if request.user.role != 'staff':
        return HttpResponseForbidden("You don't have permission to access this page.")
    base_queryset = Task.objects.select_related('room').prefetch_related('required_positions').filter(assigned_to=request.user)
    pending_tasks = base_queryset.filter(status=Task.STATUS_PENDING)
    in_progress_tasks = base_queryset.filter(status=Task.STATUS_IN_PROGRESS)
    ready_for_review_tasks = base_queryset.filter(status=Task.STATUS_READY_FOR_REVIEW)
    completed_tasks = base_queryset.filter(status=Task.STATUS_COMPLETED)
    context = {
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'ready_for_review_tasks': ready_for_review_tasks,
        'completed_tasks': completed_tasks,
    }
    return render(request, 'tasks/my_tasks.html', context)


@login_required
def my_performance(request):
    if request.user.role != 'staff':
        return HttpResponseForbidden("You don't have permission to access this page.")
    return redirect('staff_performance_detail', pk=request.user.pk)


@login_required
def staff_task_start(request, pk):
    if request.user.role != 'staff':
        return HttpResponseForbidden("You don't have permission to access this page.")
    if request.method != 'POST':
        return HttpResponseForbidden("Invalid request.")
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    if task.status == Task.STATUS_PENDING:
        task.status = Task.STATUS_IN_PROGRESS
        task.save(update_fields=['status'])
    return redirect('my_tasks')


@login_required
def staff_task_complete(request, pk):
    if request.user.role != 'staff':
        return HttpResponseForbidden("You don't have permission to access this page.")
    if request.method != 'POST':
        return HttpResponseForbidden("Invalid request.")
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    target_status = Task.STATUS_READY_FOR_REVIEW if task.requires_inspection else Task.STATUS_COMPLETED
    if task.status != target_status:
        task.status = target_status
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at'])
    if target_status == Task.STATUS_READY_FOR_REVIEW:
        messages.success(request, 'Task marked Ready for Review. A manager can now audit it.')
    else:
        messages.success(request, 'Task marked completed.')
    return redirect('staff_task_update', pk=task.pk)


@login_required
def staff_task_update(request, pk):
    if request.user.role != 'staff':
        return HttpResponseForbidden("You don't have permission to access this page.")
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    if request.method == 'POST':
        form = StaffTaskUpdateForm(request.POST, instance=task)
        if form.is_valid():
            updated_task = form.save(commit=False)
            if updated_task.status in [Task.STATUS_COMPLETED, Task.STATUS_READY_FOR_REVIEW] and task.status != updated_task.status:
                updated_task.completed_at = timezone.now()
            updated_task.save()
            messages.success(request, 'Task update saved.')
            return redirect('my_tasks')
    else:
        form = StaffTaskUpdateForm(instance=task)
    return render(request, 'tasks/staff_task_form.html', {'form': form, 'task': task})


@login_required
def performance_rating_create(request, pk):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    task = get_object_or_404(Task, pk=pk)
    if task.status != Task.STATUS_COMPLETED:
        return HttpResponseForbidden("You can only rate completed tasks.")
    if task.ratings.exists():
        return HttpResponseForbidden("This task has already been rated.")
    if request.method == 'POST':
        rating_form = PerformanceRatingForm(request.POST)
        if rating_form.is_valid():
            rating = rating_form.save(commit=False)
            rating.staff = task.assigned_to
            rating.task = task
            rating.task_type = task.get_task_type_display()
            rating.task_description = task.description
            rating.rated_by = request.user
            rating.save()
            AuditLog.log(request.user, 'staff_rated', f"Rated {task.assigned_to.email} for task {task.title} ({rating.rating})")
            messages.success(request, 'Performance rating recorded successfully.')
            return redirect('task_list')
    else:
        rating_form = PerformanceRatingForm()
    return render(request, 'tasks/performance_rating_form.html', {
        'rating_form': rating_form,
        'task': task
    })


@login_required
def performance_dashboard(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    staff_list = CustomUser.objects.filter(role='staff')
    staff_performance = []
    for staff in staff_list:
        tasks = Task.objects.filter(assigned_to=staff)
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status=Task.STATUS_COMPLETED).count()
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        ratings = PerformanceRating.objects.filter(staff=staff)
        total_ratings = ratings.count()
        avg_rating = ratings.aggregate(Avg('rating'))['rating__avg'] or 0
        staff_performance.append({
            'staff': staff,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': completion_rate,
            'total_ratings': total_ratings,
            'avg_rating': avg_rating
        })
    staff_performance_sorted = sorted(staff_performance, key=lambda x: x['avg_rating'], reverse=True)
    context = {
        'staff_performance': staff_performance_sorted
    }
    return render(request, 'tasks/performance_dashboard.html', context)


@login_required
def staff_performance_detail(request, pk):
    staff = get_object_or_404(CustomUser, pk=pk)
    if request.user.role not in ['owner', 'admin', 'manager'] and request.user != staff:
        return HttpResponseForbidden("You don't have permission to access this page.")
    tasks = Task.objects.filter(assigned_to=staff)
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status=Task.STATUS_COMPLETED).count()
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    ratings = PerformanceRating.objects.filter(staff=staff)
    total_ratings = ratings.count()
    avg_rating = ratings.aggregate(Avg('rating'))['rating__avg'] or 0
    now = timezone.now()
    recent_start = now - timedelta(days=30)
    previous_start = now - timedelta(days=60)
    recent_avg = ratings.filter(date_rated__gte=recent_start).aggregate(Avg('rating'))['rating__avg'] or 0
    previous_avg = ratings.filter(date_rated__gte=previous_start, date_rated__lt=recent_start).aggregate(Avg('rating'))['rating__avg'] or 0
    if recent_avg > previous_avg:
        trend = 'Up'
    elif recent_avg < previous_avg:
        trend = 'Down'
    else:
        trend = 'Flat'
    rating_counts = {
        1: ratings.filter(rating=1).count(),
        2: ratings.filter(rating=2).count(),
        3: ratings.filter(rating=3).count(),
        4: ratings.filter(rating=4).count(),
        5: ratings.filter(rating=5).count(),
    }
    if avg_rating >= 4.5:
        category = '⭐ Excellent Performer'
    elif avg_rating >= 3.5:
        category = '✅ Good Performer'
    elif avg_rating >= 2.5:
        category = '⚠ Needs Improvement'
    else:
        category = '🚨 Performance Concern'
    context = {
        'staff': staff,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'completion_rate': completion_rate,
        'total_ratings': total_ratings,
        'avg_rating': avg_rating,
        'recent_avg': recent_avg,
        'previous_avg': previous_avg,
        'trend': trend,
        'rating_count_1': rating_counts[1],
        'rating_count_2': rating_counts[2],
        'rating_count_3': rating_counts[3],
        'rating_count_4': rating_counts[4],
        'rating_count_5': rating_counts[5],
        'category': category,
        'ratings': ratings
    }
    return render(request, 'tasks/staff_performance_detail.html', context)


@login_required
def performance_reports(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return HttpResponseForbidden("You don't have permission to access this page.")

    period = request.GET.get('period', 'monthly')
    today = timezone.now().date()

    if period == 'daily':
        start_date = today
        end_date = today
    elif period == 'weekly':
        start_date = today - timedelta(days=6)
        end_date = today
    elif period == 'custom':
        start_date_str = request.GET.get('start_date') or today.replace(day=1).isoformat()
        end_date_str = request.GET.get('end_date') or today.isoformat()
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today.replace(day=1)
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
    else:
        start_date = today.replace(day=1)
        end_date = today

    task_qs = Task.objects.all()
    rating_qs = PerformanceRating.objects.all()

    task_qs = task_qs.filter(date_assigned__gte=start_date, date_assigned__lte=end_date)
    rating_qs = rating_qs.filter(date_rated__date__gte=start_date, date_rated__date__lte=end_date)

    staff_list = CustomUser.objects.filter(role='staff')
    rows = []
    for staff in staff_list:
        staff_tasks = task_qs.filter(assigned_to=staff)
        tasks_assigned = staff_tasks.count()
        tasks_completed = staff_tasks.filter(status=Task.STATUS_COMPLETED).count()
        completion_rate = (tasks_completed / tasks_assigned * 100) if tasks_assigned else 0
        staff_ratings = rating_qs.filter(staff=staff)
        avg_rating_period = staff_ratings.aggregate(Avg('rating'))['rating__avg'] or 0
        rows.append({
            'staff': staff,
            'tasks_assigned': tasks_assigned,
            'tasks_completed': tasks_completed,
            'completion_rate': completion_rate,
            'avg_rating': avg_rating_period,
        })

    rows_sorted = sorted(rows, key=lambda r: (r['avg_rating'], r['completion_rate'], r['tasks_completed']), reverse=True)
    for idx, row in enumerate(rows_sorted, start=1):
        row['rank'] = idx

    context = {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'rows': rows_sorted,
    }
    return render(request, 'tasks/performance_reports.html', context)


def _group_inspection_results(inspection):
    sections = OrderedDict(
        (key, {'key': key, 'label': label, 'items': []})
        for key, label in InspectionTemplateItem.SECTION_CHOICES
    )
    for result in inspection.results.select_related('template_item').order_by('template_item__display_order', 'id'):
        section_key = result.template_item.section
        sections.setdefault(section_key, {'key': section_key, 'label': result.template_item.get_section_display(), 'items': []})
        sections[section_key]['items'].append(result)
    return [section for section in sections.values() if section['items']]


def _build_results_data(formset):
    data = {}
    for form in formset.forms:
        result = form.instance
        data[result] = {
            'passed': form.cleaned_data['passed'],
            'comment': form.cleaned_data.get('comment', ''),
        }
    return data


class InspectionManagementMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['owner', 'admin', 'manager']:
            return HttpResponseForbidden("You don't have permission to inspect tasks.")
        return super().dispatch(request, *args, **kwargs)


class InspectionReadMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        inspection = self.get_object() if hasattr(self, 'get_object') else None
        if request.user.role in ['owner', 'admin', 'manager']:
            return super().dispatch(request, *args, **kwargs)
        if inspection and inspection.worker_id == request.user.id:
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden("You don't have permission to view this inspection.")


class InspectionListView(InspectionManagementMixin, ListView):
    model = TaskInspection
    template_name = 'tasks/inspection/list.html'
    context_object_name = 'inspections'
    paginate_by = 25

    def get_queryset(self):
        queryset = TaskInspection.objects.select_related('task', 'task__room', 'worker', 'inspector', 'template').order_by('-created_at')
        self.filter_form = InspectionFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            template = self.filter_form.cleaned_data.get('template')
            result = self.filter_form.cleaned_data.get('result')
            worker = self.filter_form.cleaned_data.get('worker')
            search = self.filter_form.cleaned_data.get('search')
            if template:
                queryset = queryset.filter(template=template)
            if result:
                queryset = queryset.filter(result=result)
            if worker:
                queryset = queryset.filter(worker=worker)
            if search:
                queryset = queryset.filter(task__title__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = getattr(self, 'filter_form', InspectionFilterForm())
        return context


class InspectionHistoryView(InspectionManagementMixin, TemplateView):
    template_name = 'tasks/inspection/history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = InspectionFilterForm(self.request.GET or None)
        inspections = TaskInspection.objects.select_related('task', 'task__room', 'worker', 'inspector', 'template').filter(locked=True).order_by('-submitted_at', '-created_at')
        if form.is_valid():
            template = form.cleaned_data.get('template')
            result = form.cleaned_data.get('result')
            worker = form.cleaned_data.get('worker')
            search = form.cleaned_data.get('search')
            if template:
                inspections = inspections.filter(template=template)
            if result:
                inspections = inspections.filter(result=result)
            if worker:
                inspections = inspections.filter(worker=worker)
            if search:
                inspections = inspections.filter(task__title__icontains=search)
        context['filter_form'] = form
        context['inspections'] = inspections
        return context


class InspectionDetailView(InspectionReadMixin, DetailView):
    model = TaskInspection
    template_name = 'tasks/inspection/detail.html'
    context_object_name = 'inspection'

    def get_queryset(self):
        return TaskInspection.objects.select_related('task', 'task__room', 'worker', 'inspector', 'template').prefetch_related('results__template_item')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sections'] = _group_inspection_results(self.object)
        context['can_edit'] = self.request.user.role in ['owner', 'admin', 'manager'] and not self.object.locked
        return context


class InspectionCreateView(InspectionManagementMixin, View):
    template_name = 'tasks/inspection/create.html'

    def get_task(self):
        return get_object_or_404(Task.objects.select_related('room', 'assigned_to'), pk=self.kwargs['task_id'])

    def get(self, request, *args, **kwargs):
        task = self.get_task()
        if hasattr(task, 'inspection'):
            return redirect('inspection_update', pk=task.inspection.pk)
        form = InspectionCreateForm(task=task)
        return render(request, self.template_name, {'task': task, 'form': form})

    def post(self, request, *args, **kwargs):
        task = self.get_task()
        if hasattr(task, 'inspection'):
            return redirect('inspection_update', pk=task.inspection.pk)
        form = InspectionCreateForm(request.POST, task=task)
        if form.is_valid():
            try:
                inspection = InspectionWorkflowService.create_inspection(
                    task=task,
                    template=form.cleaned_data['template'],
                    inspector=request.user,
                    notes=form.cleaned_data.get('inspector_notes', ''),
                )
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, 'Inspection started. Complete the checklist and submit it when ready.')
                return redirect('inspection_update', pk=inspection.pk)
        return render(request, self.template_name, {'task': task, 'form': form})


class InspectionUpdateView(InspectionManagementMixin, View):
    template_name = 'tasks/inspection/audit.html'

    def get_object(self):
        return get_object_or_404(
            TaskInspection.objects.select_related('task', 'task__room', 'worker', 'inspector', 'template').prefetch_related('results__template_item'),
            pk=self.kwargs['pk'],
        )

    def _build_context(self, inspection, inspection_form, result_formset):
        preview_deductions = sum(
            form.instance.template_item.deduction_points
            for form in result_formset.forms
            if form.is_bound and form.is_valid() and form.cleaned_data.get('passed') is False
        )
        if not result_formset.is_bound:
            preview_deductions = sum(result.deduction_applied for result in inspection.results.all())
        preview_score = max(inspection.starting_score - preview_deductions, 0)
        if preview_score >= 95:
            preview_result = 'Excellent'
        elif preview_score >= 85:
            preview_result = 'Pass'
        else:
            preview_result = 'Fail'
        return {
            'inspection': inspection,
            'task': inspection.task,
            'inspection_form': inspection_form,
            'result_formset': result_formset,
            'sections': _group_inspection_results(inspection),
            'preview_deductions': preview_deductions,
            'preview_score': preview_score,
            'preview_result': preview_result,
        }

    def get(self, request, *args, **kwargs):
        inspection = self.get_object()
        if inspection.locked:
            return redirect('inspection_detail', pk=inspection.pk)
        inspection_form = TaskInspectionForm(instance=inspection)
        result_formset = InspectionResultFormSet(queryset=inspection.results.select_related('template_item').order_by('template_item__display_order', 'id'))
        return render(request, self.template_name, self._build_context(inspection, inspection_form, result_formset))

    def post(self, request, *args, **kwargs):
        inspection = self.get_object()
        if inspection.locked:
            return redirect('inspection_detail', pk=inspection.pk)
        inspection_form = TaskInspectionForm(request.POST, instance=inspection)
        result_formset = InspectionResultFormSet(
            request.POST,
            queryset=inspection.results.select_related('template_item').order_by('template_item__display_order', 'id'),
        )
        if inspection_form.is_valid() and result_formset.is_valid():
            try:
                InspectionWorkflowService.save_draft(
                    inspection=inspection,
                    inspector_notes=inspection_form.cleaned_data.get('inspector_notes', ''),
                    results_data=_build_results_data(result_formset),
                    user=request.user,
                )
            except Exception as exc:
                inspection_form.add_error(None, str(exc))
            else:
                messages.success(request, 'Inspection draft saved.')
                return redirect('inspection_update', pk=inspection.pk)
        return render(request, self.template_name, self._build_context(inspection, inspection_form, result_formset))


class InspectionSubmitView(InspectionManagementMixin, View):
    def post(self, request, *args, **kwargs):
        inspection = get_object_or_404(
            TaskInspection.objects.select_related('task', 'task__room', 'worker', 'inspector', 'template').prefetch_related('results__template_item'),
            pk=self.kwargs['pk'],
        )
        if inspection.locked:
            messages.info(request, 'This inspection has already been submitted.')
            return redirect('inspection_detail', pk=inspection.pk)
        inspection_form = TaskInspectionForm(request.POST, instance=inspection)
        result_formset = InspectionResultFormSet(
            request.POST,
            queryset=inspection.results.select_related('template_item').order_by('template_item__display_order', 'id'),
        )
        if inspection_form.is_valid() and result_formset.is_valid():
            try:
                updated_inspection, follow_up_task = InspectionWorkflowService.submit_inspection(
                    inspection=inspection,
                    inspector_notes=inspection_form.cleaned_data.get('inspector_notes', ''),
                    results_data=_build_results_data(result_formset),
                    user=request.user,
                )
            except Exception as exc:
                inspection_form.add_error(None, str(exc))
            else:
                if follow_up_task:
                    messages.warning(
                        request,
                        f'Inspection failed. Task reopened and follow-up task "{follow_up_task.title}" was created.',
                    )
                else:
                    messages.success(request, f'Inspection submitted with result: {updated_inspection.get_result_display()}.')
                return redirect('inspection_detail', pk=inspection.pk)
        return render(
            request,
            'tasks/inspection/audit.html',
            InspectionUpdateView()._build_context(inspection, inspection_form, result_formset),
        )


class MaintenanceIssueAccessMixin(LoginRequiredMixin):
    def load_issue(self, request, **kwargs):
        if not hasattr(self, 'issue'):
            self.issue = get_object_or_404(
                accessible_maintenance_issues_queryset(request.user),
                pk=kwargs['pk'],
            )
        return self.issue

    def dispatch(self, request, *args, **kwargs):
        issue = self.load_issue(request, **kwargs)
        if not can_view_maintenance_issue(request.user, issue):
            return HttpResponseForbidden("You don't have permission to view this maintenance issue.")
        return super().dispatch(request, *args, **kwargs)


class MaintenanceDashboardView(MaintenanceModuleAccessMixin, TemplateView):
    template_name = 'tasks/maintenance/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(MaintenanceReportService.dashboard_snapshot(self.request.user))
        context['can_create_issue'] = can_create_maintenance_issue(self.request.user)
        context['can_manage_categories'] = self.request.user.role in ['owner', 'admin']
        return context


class MaintenanceIssueListView(MaintenanceModuleAccessMixin, ListView):
    model = MaintenanceIssue
    template_name = 'tasks/maintenance/issue_list.html'
    context_object_name = 'issues'
    paginate_by = 20

    def get_queryset(self):
        queryset = accessible_maintenance_issues_queryset(self.request.user)
        self.filter_form = MaintenanceIssueFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            query = (self.filter_form.cleaned_data.get('q') or '').strip()
            status = self.filter_form.cleaned_data.get('status')
            priority = self.filter_form.cleaned_data.get('priority')
            category = self.filter_form.cleaned_data.get('category')
            room = self.filter_form.cleaned_data.get('room')
            assigned_to = self.filter_form.cleaned_data.get('assigned_to')
            reported_by = self.filter_form.cleaned_data.get('reported_by')
            start_date = self.filter_form.cleaned_data.get('start_date')
            end_date = self.filter_form.cleaned_data.get('end_date')
            if query:
                queryset = queryset.filter(
                    Q(issue_number__icontains=query)
                    | Q(title__icontains=query)
                    | Q(description__icontains=query)
                    | Q(room__room_number__icontains=query)
                )
            if status:
                queryset = queryset.filter(status=status)
            if priority:
                queryset = queryset.filter(priority=priority)
            if category:
                queryset = queryset.filter(category=category)
            if room:
                queryset = queryset.filter(room=room)
            if assigned_to:
                queryset = queryset.filter(assigned_to=assigned_to)
            if reported_by:
                queryset = queryset.filter(reported_by=reported_by)
            if start_date:
                queryset = queryset.filter(created_at__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['can_create_issue'] = can_create_maintenance_issue(self.request.user)
        return context


class MaintenanceIssueDetailView(MaintenanceIssueAccessMixin, DetailView):
    model = MaintenanceIssue
    template_name = 'tasks/maintenance/issue_detail.html'
    context_object_name = 'issue'

    def get_object(self, queryset=None):
        return self.issue

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        issue = self.object
        context['activities'] = issue.activities.select_related('performed_by')[:30]
        context['photos'] = issue.photos.select_related('uploaded_by').order_by('uploaded_at', 'id')
        context['can_edit'] = can_edit_maintenance_issue(self.request.user, issue)
        context['can_escalate'] = can_escalate_maintenance_issue(self.request.user, issue)
        context['can_verify'] = can_verify_maintenance_issue(self.request.user) and issue.status == MaintenanceIssue.STATUS_COMPLETED
        context['can_record_expense'] = can_record_maintenance_expense(self.request.user) and not issue.expense_id
        context['can_manage_categories'] = self.request.user.role in ['owner', 'admin']
        return context


class MaintenanceIssueCreateView(MaintenanceModuleAccessMixin, FormView):
    template_name = 'tasks/maintenance/issue_form.html'
    form_class = MaintenanceIssueForm

    def dispatch(self, request, *args, **kwargs):
        if not can_create_maintenance_issue(request.user):
            return HttpResponseForbidden("You don't have permission to report maintenance issues.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'create'
        return context

    def form_valid(self, form):
        try:
            issue = MaintenanceIssueService.create_issue(
                cleaned_data=form.cleaned_data,
                user=self.request.user,
                uploaded_files=self.request.FILES.getlist('photos'),
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, f'Maintenance issue {issue.issue_number} reported successfully.')
        return redirect(issue.get_absolute_url())


class MaintenanceIssueUpdateView(MaintenanceIssueAccessMixin, FormView):
    template_name = 'tasks/maintenance/issue_form.html'
    form_class = MaintenanceIssueForm

    def dispatch(self, request, *args, **kwargs):
        if not can_edit_maintenance_issue(request.user, self.issue):
            return HttpResponseForbidden("You don't have permission to edit this maintenance issue.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.issue
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'edit'
        context['issue'] = self.issue
        return context

    def form_valid(self, form):
        try:
            issue = MaintenanceIssueService.update_issue(
                issue=self.issue,
                cleaned_data=form.cleaned_data,
                user=self.request.user,
                uploaded_files=self.request.FILES.getlist('photos'),
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, f'Maintenance issue {issue.issue_number} updated successfully.')
        return redirect(issue.get_absolute_url())


class MaintenanceIssueAssignView(MaintenanceAdminAccessMixin, FormView):
    template_name = 'tasks/maintenance/assign_issue.html'
    form_class = MaintenanceIssueAssignForm

    def dispatch(self, request, *args, **kwargs):
        self.issue = get_object_or_404(MaintenanceIssue.objects.select_related('room', 'reported_by', 'assigned_to', 'task'), pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.issue
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['issue'] = self.issue
        return context

    def form_valid(self, form):
        try:
            issue = MaintenanceWorkflowService.assign_issue(
                issue=self.issue,
                cleaned_data=form.cleaned_data,
                user=self.request.user,
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, f'Maintenance issue {issue.issue_number} updated successfully.')
        return redirect(issue.get_absolute_url())


class MaintenanceIssueEscalateView(MaintenanceIssueAccessMixin, FormView):
    template_name = 'tasks/maintenance/escalate_issue.html'
    form_class = MaintenanceIssueEscalateForm

    def dispatch(self, request, *args, **kwargs):
        issue = self.load_issue(request, **kwargs)
        if not can_escalate_maintenance_issue(request.user, issue):
            return HttpResponseForbidden("You don't have permission to escalate this maintenance issue.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['issue'] = self.issue
        context['mode'] = 'escalate'
        return context

    def form_valid(self, form):
        try:
            issue = MaintenanceWorkflowService.escalate_issue(
                issue=self.issue,
                user=self.request.user,
                notes=form.cleaned_data.get('notes', ''),
                target_priority=form.cleaned_data.get('target_priority', ''),
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, f'Maintenance issue {issue.issue_number} escalated successfully.')
        return redirect(issue.get_absolute_url())


class MaintenanceIssueVerifyView(MaintenanceIssueAccessMixin, FormView):
    template_name = 'tasks/maintenance/verify_issue.html'
    form_class = MaintenanceIssueVerifyForm

    def dispatch(self, request, *args, **kwargs):
        if not can_verify_maintenance_issue(request.user):
            return HttpResponseForbidden("You don't have permission to verify maintenance issues.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['issue'] = self.issue
        return context

    def form_valid(self, form):
        try:
            issue = MaintenanceWorkflowService.verify_issue(
                issue=self.issue,
                decision=form.cleaned_data['decision'],
                user=self.request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        if issue.status == MaintenanceIssue.STATUS_VERIFIED:
            messages.success(self.request, f'Maintenance issue {issue.issue_number} verified successfully.')
        else:
            messages.warning(self.request, f'Maintenance issue {issue.issue_number} was reopened after failed verification.')
        return redirect(issue.get_absolute_url())


class MaintenanceCategoryListView(MaintenanceAdminAccessMixin, ListView):
    model = MaintenanceCategory
    template_name = 'tasks/maintenance/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        return MaintenanceCategory.objects.order_by('name')


class MaintenanceCategoryCreateView(MaintenanceAdminAccessMixin, CreateView):
    model = MaintenanceCategory
    form_class = MaintenanceCategoryForm
    template_name = 'tasks/maintenance/category_form.html'
    success_url = reverse_lazy('maintenance_category_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.updated_by = self.request.user
        self.object.save()
        messages.success(self.request, 'Maintenance category created successfully.')
        return redirect(self.success_url)


class MaintenanceActivityListView(MaintenanceModuleAccessMixin, ListView):
    model = MaintenanceActivity
    template_name = 'tasks/maintenance/activity_list.html'
    context_object_name = 'activities'
    paginate_by = 30

    def get_queryset(self):
        queryset = accessible_maintenance_activities_queryset(self.request.user)
        issue_id = self.request.GET.get('issue')
        if issue_id:
            queryset = queryset.filter(issue_id=issue_id)
        return queryset.order_by('-created_at')


class MaintenanceRecordExpenseRedirectView(MaintenanceIssueAccessMixin, View):
    def get(self, request, *args, **kwargs):
        if not can_record_maintenance_expense(request.user):
            return HttpResponseForbidden("You don't have permission to record maintenance expenses.")
        issue = self.issue
        category = (
            ExpenseCategory.objects.filter(name__iexact='Maintenance').first()
            or ExpenseCategory.objects.filter(name__iexact='Repairs').first()
        )
        room_reference = f'Room {issue.room.room_number} ' if issue.room_id else ''
        query_params = {
            'description': f'Repair {room_reference}{issue.title}'.strip(),
            'notes': f'Linked to maintenance issue {issue.issue_number}.',
            'maintenance_issue': issue.pk,
        }
        if category:
            query_params['category'] = category.pk
        if issue.task_id:
            query_params['task'] = issue.task_id
        return redirect(f"{reverse('expense_create')}?{urlencode(query_params)}")
