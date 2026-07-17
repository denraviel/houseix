from django.shortcuts import render

# Create your views here.

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView

from .forms import (
    ApprovalActionForm,
    ExpenseCategoryForm,
    ExpenseFilterForm,
    ExpenseForm,
    FuelLogForm,
    RecurringExpenseForm,
    VendorForm,
)
from .models import Expense, ExpenseCategory, FuelLog, RecurringExpense, Vendor
from .permissions import (
    ExpenseAccessMixin,
    ExpenseManagementMixin,
    ExpenseModuleAccessMixin,
    can_approve_expense,
    can_create_expense,
    can_delete_expense,
    can_edit_expense,
    can_submit_expense,
)
from .selectors import accessible_expenses_queryset, expense_dashboard_snapshot, recurring_due_queryset
from .services import ExpenseApprovalService, ExpenseService, FuelLogService, RecurringExpenseService


class ExpenseDashboardView(ExpenseModuleAccessMixin, TemplateView):
    template_name = 'expenses/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(expense_dashboard_snapshot(self.request.user))
        return context


class ExpenseListView(ExpenseModuleAccessMixin, ListView):
    model = Expense
    template_name = 'expenses/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20

    def get_queryset(self):
        queryset = accessible_expenses_queryset(self.request.user)
        self.filter_form = ExpenseFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            query = (self.filter_form.cleaned_data.get('q') or '').strip()
            status = self.filter_form.cleaned_data.get('status')
            category = self.filter_form.cleaned_data.get('category')
            vendor = self.filter_form.cleaned_data.get('vendor')
            payment_method = self.filter_form.cleaned_data.get('payment_method')
            start_date = self.filter_form.cleaned_data.get('start_date')
            end_date = self.filter_form.cleaned_data.get('end_date')
            if query:
                queryset = queryset.filter(
                    Q(expense_number__icontains=query)
                    | Q(description__icontains=query)
                    | Q(category__name__icontains=query)
                    | Q(vendor__name__icontains=query)
                    | Q(task__title__icontains=query)
                )
            if status:
                queryset = queryset.filter(status=status)
            if category:
                queryset = queryset.filter(category=category)
            if vendor:
                queryset = queryset.filter(vendor=vendor)
            if payment_method:
                queryset = queryset.filter(payment_method=payment_method)
            if start_date:
                queryset = queryset.filter(expense_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(expense_date__lte=end_date)
        return queryset.order_by('-expense_date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        return context


class ExpenseDetailView(ExpenseAccessMixin, DetailView):
    model = Expense
    template_name = 'expenses/expense_detail.html'
    context_object_name = 'expense'

    def get_queryset(self):
        return accessible_expenses_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expense = self.object
        context['audit_logs'] = expense.audit_logs.select_related('user', 'fuel_log', 'recurring_expense')[:20]
        context['can_edit'] = can_edit_expense(self.request.user, expense)
        context['can_delete'] = can_delete_expense(self.request.user, expense)
        context['can_submit'] = can_submit_expense(self.request.user, expense)
        context['can_approve'] = can_approve_expense(self.request.user, expense)
        context['approval_form'] = ApprovalActionForm()
        return context


class ExpenseCreateView(ExpenseModuleAccessMixin, FormView):
    template_name = 'expenses/expense_form.html'
    form_class = ExpenseForm

    def dispatch(self, request, *args, **kwargs):
        if not can_create_expense(request.user):
            return HttpResponseForbidden("You don't have permission to create expenses.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        category_id = self.request.GET.get('category')
        task_id = self.request.GET.get('task')
        description = (self.request.GET.get('description') or '').strip()
        notes = (self.request.GET.get('notes') or '').strip()
        if category_id:
            try:
                initial['category'] = ExpenseCategory.objects.get(pk=category_id)
            except ExpenseCategory.DoesNotExist:
                pass
        if task_id:
            try:
                from tasks.models import Task
                initial['task'] = Task.objects.get(pk=task_id)
            except Task.DoesNotExist:
                pass
        if description:
            initial['description'] = description
        if notes:
            initial['notes'] = notes
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'create'
        context['maintenance_issue_id'] = self.request.GET.get('maintenance_issue', '')
        return context

    def form_valid(self, form):
        try:
            expense = ExpenseService.create_expense(cleaned_data=form.cleaned_data, user=self.request.user)
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        maintenance_issue_id = self.request.GET.get('maintenance_issue')
        if maintenance_issue_id:
            from tasks.models import MaintenanceIssue
            from tasks.services import MaintenanceWorkflowService
            try:
                issue = MaintenanceIssue.objects.get(pk=maintenance_issue_id)
                MaintenanceWorkflowService.link_expense(issue=issue, expense=expense, user=self.request.user)
            except MaintenanceIssue.DoesNotExist:
                pass
        messages.success(self.request, f'Expense {expense.expense_number} created successfully.')
        return redirect(expense.get_absolute_url())


class ExpenseUpdateView(ExpenseModuleAccessMixin, FormView):
    template_name = 'expenses/expense_form.html'
    form_class = ExpenseForm

    def dispatch(self, request, *args, **kwargs):
        self.expense = get_object_or_404(accessible_expenses_queryset(request.user), pk=kwargs['pk'])
        if not can_edit_expense(request.user, self.expense):
            return HttpResponseForbidden("You don't have permission to edit this expense.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.expense
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'edit'
        context['expense'] = self.expense
        return context

    def form_valid(self, form):
        try:
            expense = ExpenseService.update_expense(
                expense=self.expense,
                cleaned_data=form.cleaned_data,
                user=self.request.user,
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, f'Expense {expense.expense_number} updated successfully.')
        return redirect(expense.get_absolute_url())


class ExpenseDeleteView(ExpenseModuleAccessMixin, DetailView):
    model = Expense
    template_name = 'expenses/expense_confirm_delete.html'
    context_object_name = 'expense'

    def get_queryset(self):
        return accessible_expenses_queryset(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not can_delete_expense(request.user, self.object):
            return HttpResponseForbidden("You don't have permission to delete this expense.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            expense_number = ExpenseService.delete_expense(expense=self.object, user=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect(self.object.get_absolute_url())
        messages.success(request, f'Expense {expense_number} deleted successfully.')
        return redirect('expense_list')


class ExpenseApprovalView(ExpenseModuleAccessMixin, View):
    def post(self, request, pk):
        expense = get_object_or_404(accessible_expenses_queryset(request.user), pk=pk)
        action = (request.POST.get('action') or '').strip()
        notes = (request.POST.get('notes') or '').strip()
        try:
            if action == 'submit':
                if not can_submit_expense(request.user, expense):
                    return HttpResponseForbidden("You don't have permission to submit this expense.")
                ExpenseService.submit_for_approval(expense=expense, user=request.user, notes=notes)
                messages.success(request, f'Expense {expense.expense_number} submitted for approval.')
            elif action == 'approve':
                if not can_approve_expense(request.user, expense):
                    return HttpResponseForbidden("You don't have permission to approve this expense.")
                ExpenseApprovalService.approve_expense(expense=expense, user=request.user, notes=notes)
                messages.success(request, f'Expense {expense.expense_number} approved successfully.')
            elif action == 'reject':
                if not can_approve_expense(request.user, expense):
                    return HttpResponseForbidden("You don't have permission to reject this expense.")
                ExpenseApprovalService.reject_expense(expense=expense, user=request.user, notes=notes)
                messages.success(request, f'Expense {expense.expense_number} rejected.')
            else:
                messages.error(request, 'Unsupported approval action.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        return redirect(expense.get_absolute_url())


class ExpenseCategoryListView(ExpenseManagementMixin, ListView):
    model = ExpenseCategory
    template_name = 'expenses/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        return ExpenseCategory.objects.order_by('name')


class ExpenseCategoryCreateView(ExpenseManagementMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expense_category_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.updated_by = self.request.user
        self.object.save()
        messages.success(self.request, 'Expense category created successfully.')
        return redirect(self.success_url)


class VendorListView(ExpenseManagementMixin, ListView):
    model = Vendor
    template_name = 'expenses/vendor_list.html'
    context_object_name = 'vendors'
    paginate_by = 20

    def get_queryset(self):
        return Vendor.objects.order_by('name')


class VendorCreateView(ExpenseManagementMixin, CreateView):
    model = Vendor
    form_class = VendorForm
    template_name = 'expenses/vendor_form.html'
    success_url = reverse_lazy('vendor_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.updated_by = self.request.user
        self.object.save()
        messages.success(self.request, 'Vendor created successfully.')
        return redirect(self.success_url)


class RecurringExpenseListView(ExpenseManagementMixin, ListView):
    model = RecurringExpense
    template_name = 'expenses/recurring_list.html'
    context_object_name = 'recurring_expenses'
    paginate_by = 20

    def get_queryset(self):
        return RecurringExpense.objects.select_related('category', 'vendor', 'created_by').order_by('next_due_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['due_recurring_expenses'] = recurring_due_queryset()[:10]
        return context


class RecurringExpenseCreateView(ExpenseManagementMixin, CreateView):
    model = RecurringExpense
    form_class = RecurringExpenseForm
    template_name = 'expenses/recurring_form.html'
    success_url = reverse_lazy('recurring_expense_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.updated_by = self.request.user
        self.object.save()
        messages.success(self.request, 'Recurring expense schedule created successfully.')
        return redirect(self.success_url)


class RecurringExpenseGenerateView(ExpenseManagementMixin, View):
    def post(self, request, *args, **kwargs):
        generated = RecurringExpenseService.generate_due_expenses(user=request.user)
        messages.success(request, f'Generated {len(generated)} expense record(s) from recurring schedules.')
        return redirect('recurring_expense_list')


class FuelLogListView(ExpenseModuleAccessMixin, ListView):
    model = FuelLog
    template_name = 'expenses/fuel_log_list.html'
    context_object_name = 'fuel_logs'
    paginate_by = 20

    def get_queryset(self):
        queryset = FuelLog.objects.select_related('expense', 'expense__category', 'expense__vendor', 'recorded_by')
        if self.request.user.role == 'staff':
            queryset = queryset.filter(Q(expense__recorded_by=self.request.user) | Q(expense__created_by=self.request.user))
        return queryset.order_by('-created_at')


class FuelLogCreateView(ExpenseModuleAccessMixin, FormView):
    template_name = 'expenses/fuel_log_form.html'
    form_class = FuelLogForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            fuel_log = FuelLogService.create_fuel_log(cleaned_data=form.cleaned_data, user=self.request.user)
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, f'Fuel log for {fuel_log.generator_name} created successfully.')
        return redirect('fuel_log_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'create'
        return context