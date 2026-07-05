from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .models import Sale
from .forms import SaleForm
from accounts.views import AdminRequiredMixin, OwnerRequiredMixin
from django.views.generic import ListView, CreateView, DeleteView
from django.urls import reverse_lazy


class SaleListView(AdminRequiredMixin, ListView):
    model = Sale
    template_name = 'sales/sales_list.html'
    context_object_name = 'sales'
    ordering = ['-created_at']

    def get_queryset(self):
        return Sale.objects.select_related('product', 'recorded_by', 'customer', 'room', 'stay').order_by('-created_at')


class SaleCreateView(LoginRequiredMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = 'sales/sale_form.html'
    
    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        if self.request.user.role in ['owner', 'admin']:
            return reverse_lazy('sales_list')
        else:
            return reverse_lazy('employee_dashboard')


class SaleDeleteView(OwnerRequiredMixin, DeleteView):
    model = Sale
    template_name = 'sales/sale_confirm_delete.html'
    success_url = reverse_lazy('sales_list')
    context_object_name = 'sale'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Sale record deleted successfully!')
        return super().delete(request, *args, **kwargs)


@login_required
def sale_create(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.recorded_by = request.user
            sale.save()
            messages.success(request, 'Sale recorded successfully!')
            if request.user.role in ['owner', 'admin', 'manager']:
                return redirect('sales_list')
            else:
                return redirect('employee_dashboard')
    else:
        form = SaleForm()
    return render(request, 'sales/sale_form.html', {'form': form})
