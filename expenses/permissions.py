from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseForbidden

from .models import Expense


def can_access_expenses(user):
    return getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) in [
        'owner',
        'admin',
        'manager',
        'staff',
    ]


def can_manage_reference_data(user):
    return getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) in ['owner', 'admin', 'manager']


def can_create_expense(user):
    return can_access_expenses(user)


def can_view_expense(user, expense):
    if not can_access_expenses(user):
        return False
    if user.role in ['owner', 'admin', 'manager']:
        return True
    return expense.recorded_by_id == user.id or expense.created_by_id == user.id


def can_edit_expense(user, expense):
    if not can_view_expense(user, expense):
        return False
    if user.role in ['owner', 'admin']:
        return expense.status != Expense.STATUS_APPROVED
    if user.role == 'manager':
        return expense.recorded_by_id == user.id and expense.status in [Expense.STATUS_DRAFT, Expense.STATUS_REJECTED]
    return expense.recorded_by_id == user.id and expense.status == Expense.STATUS_DRAFT


def can_delete_expense(user, expense):
    if not can_view_expense(user, expense):
        return False
    if expense.status == Expense.STATUS_APPROVED:
        return False
    if user.role in ['owner', 'admin']:
        return True
    if user.role == 'manager':
        return expense.recorded_by_id == user.id and expense.status in [Expense.STATUS_DRAFT, Expense.STATUS_REJECTED]
    return expense.recorded_by_id == user.id and expense.status == Expense.STATUS_DRAFT


def can_submit_expense(user, expense):
    if not can_view_expense(user, expense):
        return False
    if expense.status not in [Expense.STATUS_DRAFT, Expense.STATUS_REJECTED]:
        return False
    if user.role in ['owner', 'admin']:
        return True
    if user.role == 'manager':
        return expense.recorded_by_id == user.id
    return False


def can_approve_expense(user, expense):
    return (
        getattr(user, 'is_authenticated', False)
        and getattr(user, 'role', None) in ['owner', 'admin']
        and expense.status == Expense.STATUS_PENDING_APPROVAL
    )


class ExpenseAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_view_expense(self.request.user, self.get_object())

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return HttpResponseForbidden("You don't have permission to access this expense.")
        return super().handle_no_permission()


class ExpenseModuleAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_access_expenses(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return HttpResponseForbidden("You don't have permission to access the expense module.")
        return super().handle_no_permission()


class ExpenseManagementMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_manage_reference_data(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return HttpResponseForbidden("You don't have permission to manage this expense resource.")
        return super().handle_no_permission()
