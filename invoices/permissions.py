from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseForbidden


def can_manage_invoices(user):
    return getattr(user, 'is_authenticated', False) and user.role in ['owner', 'admin', 'manager']


def can_view_invoice(user, invoice):
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.role in ['owner', 'admin', 'manager']:
        return True
    return invoice.assigned_to_id == user.id


def can_record_payments(user, invoice):
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.role in ['owner', 'admin', 'manager']:
        return True
    return invoice.assigned_to_id == user.id


class InvoiceManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_manage_invoices(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return HttpResponseForbidden("You don't have permission to access this page.")
        return super().handle_no_permission()


class InvoiceAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        invoice = self.get_object()
        return can_view_invoice(self.request.user, invoice)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return HttpResponseForbidden("You don't have permission to access this invoice.")
        return super().handle_no_permission()
