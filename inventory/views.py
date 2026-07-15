from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.permissions import module_permission_required
from accounts.services import NavigationService
from .models import InventoryItem, StockMovement
from .forms import InventoryItemForm, StockMovementForm, AddStockForm


@login_required
@module_permission_required(NavigationService.MODULE_INVENTORY)
def inventory_list(request):
    if request.user.role not in ['owner', 'admin', 'manager', 'staff']:
        messages.error(request, 'You are not authorized to access inventory.')
        return redirect('employee_dashboard')
    items = InventoryItem.objects.all().order_by('-last_updated')
    # Calculate stock value for each item
    for item in items:
        item.stock_value = item.quantity * item.cost_price
    return render(request, 'inventory/inventory_list.html', {'items': items})


@login_required
@module_permission_required(NavigationService.MODULE_INVENTORY)
def inventory_item_create(request):
    if request.user.role not in ['owner', 'admin']:
        messages.error(request, 'You are not authorized to add inventory items.')
        return redirect('inventory_list')
    
    if request.method == 'POST':
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Inventory item added successfully.')
            from accounts.models import AuditLog
            AuditLog.log(request.user, 'inventory_created', f"Created inventory item {form.instance.item_name}")
            return redirect('inventory_list')
    else:
        form = InventoryItemForm()
    return render(request, 'inventory/inventory_item_form.html', {'form': form})


@login_required
@module_permission_required(NavigationService.MODULE_INVENTORY)
def inventory_item_edit(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.user.role not in ['owner', 'admin', 'manager']:
        messages.error(request, 'You are not authorized to edit inventory items.')
        return redirect('inventory_list')
    
    if request.method == 'POST':
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Inventory item updated successfully.')
            from accounts.models import AuditLog
            AuditLog.log(request.user, 'inventory_updated', f"Updated inventory item {item.item_name}")
            return redirect('inventory_list')
    else:
        form = InventoryItemForm(instance=item)
    return render(request, 'inventory/inventory_item_form.html', {'form': form})


@login_required
@module_permission_required(NavigationService.MODULE_INVENTORY)
def add_stock(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.user.role not in ['owner', 'admin', 'manager']:
        messages.error(request, 'You are not authorized to add stock.')
        return redirect('inventory_list')
    
    if request.method == 'POST':
        form = AddStockForm(request.POST)
        if form.is_valid():
            quantity_to_add = form.cleaned_data['quantity_to_add']
            item.quantity += quantity_to_add
            item.save()
            messages.success(request, f'Successfully added {quantity_to_add} {item.unit_type} to stock!')
            from accounts.models import AuditLog
            AuditLog.log(request.user, 'inventory_stock_added', f"Added {quantity_to_add} {item.unit_type} to {item.item_name}")
            return redirect('inventory_list')
    else:
        form = AddStockForm()
    return render(request, 'inventory/add_stock_form.html', {'form': form, 'item': item})


@login_required
@module_permission_required(NavigationService.MODULE_INVENTORY)
def inventory_item_delete(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.user.role not in ['owner', 'admin']:
        messages.error(request, 'You are not authorized to delete inventory items.')
        return redirect('inventory_list')
    
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Inventory item deleted successfully!')
        from accounts.models import AuditLog
        AuditLog.log(request.user, 'inventory_deleted', f"Deleted inventory item {item.item_name}")
        return redirect('inventory_list')
    return render(request, 'inventory/inventory_item_confirm_delete.html', {'item': item})


@login_required
@module_permission_required(NavigationService.MODULE_INVENTORY)
def stock_movement_create(request):
    if request.user.role not in ['owner', 'admin', 'manager', 'staff']:
        messages.error(request, 'You are not authorized to take inventory.')
        return redirect('employee_dashboard')
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.taken_by = request.user
            # Update inventory quantity
            item = movement.item
            if item.quantity < movement.quantity_taken:
                messages.error(request, 'Insufficient inventory!')
                return render(request, 'inventory/stock_movement_form.html', {'form': form})
            item.quantity -= movement.quantity_taken
            item.save()
            movement.save()
            messages.success(request, 'Stock movement recorded successfully.')
            return redirect('inventory_list')
    else:
        form = StockMovementForm()
    return render(request, 'inventory/stock_movement_form.html', {'form': form})
