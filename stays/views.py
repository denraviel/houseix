from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import ActivityLog
from accounts.permissions import module_permission_required
from accounts.services import NavigationService
from .forms import GuestStayForm
from .models import GuestStay


def _can_create_stays(user):
    return user.role in ['owner', 'admin', 'manager', 'staff']


def _can_edit_stays(user):
    return user.role in ['owner', 'admin', 'manager']


@login_required
@module_permission_required(NavigationService.MODULE_STAYS)
def stay_list(request):
    query = (request.GET.get('q') or '').strip()
    stays = GuestStay.objects.select_related('customer', 'room').all()
    if query:
        stays = stays.filter(
            Q(customer__full_name__icontains=query)
            | Q(customer__phone_number__icontains=query)
            | Q(room__room_number__icontains=query)
            | Q(status__icontains=query)
        )
    return render(request, 'stays/stay_list.html', {'stays': stays, 'query': query})


@login_required
@module_permission_required(NavigationService.MODULE_STAYS)
def stay_detail(request, pk):
    stay = get_object_or_404(GuestStay.objects.select_related('customer', 'room'), pk=pk)
    return render(request, 'stays/stay_detail.html', {'stay': stay})


@login_required
@module_permission_required(NavigationService.MODULE_STAYS)
def stay_create(request):
    if not _can_create_stays(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    if request.method == 'POST':
        form = GuestStayForm(request.POST, user=request.user)
        if form.is_valid():
            stay = form.save(commit=False)
            stay.created_by_user = request.user
            stay.created_by_full_name = request.user.full_name
            stay.created_by_username = request.user.email
            stay.created_by_role = request.user.role
            if stay.daily_rate is None and stay.room_id:
                stay.daily_rate = stay.room.daily_rate
            now = timezone.now()
            if request.user.role == 'staff':
                stay.status = GuestStay.STATUS_CHECKED_IN
            if stay.status == GuestStay.STATUS_CHECKED_IN and not stay.checked_in_at:
                stay.checked_in_by_user = request.user
                stay.checked_in_at = now
                stay.checked_in_by_full_name = request.user.full_name
                stay.checked_in_by_username = request.user.email
                stay.checked_in_by_role = request.user.role
            if stay.status == GuestStay.STATUS_CHECKED_OUT and not stay.checked_out_at:
                stay.checked_out_by_user = request.user
                stay.checked_out_at = now
                stay.checked_out_by_full_name = request.user.full_name
                stay.checked_out_by_username = request.user.email
                stay.checked_out_by_role = request.user.role
            stay.save()
            ActivityLog.log(
                request.user,
                'booking_created',
                customer=stay.customer,
                booking=stay,
                notes=f"Created booking for {stay.customer.full_name} in Room {stay.room.room_number}.",
            )
            if stay.status == GuestStay.STATUS_CHECKED_IN:
                ActivityLog.log(
                    request.user,
                    'guest_checked_in',
                    customer=stay.customer,
                    booking=stay,
                    notes=f"Checked {stay.customer.full_name} into Room {stay.room.room_number}.",
                )
            if stay.status == GuestStay.STATUS_CHECKED_OUT:
                ActivityLog.log(
                    request.user,
                    'guest_checked_out',
                    customer=stay.customer,
                    booking=stay,
                    notes=f"Checked {stay.customer.full_name} out of Room {stay.room.room_number}.",
                )
            messages.success(request, 'Guest stay created.')
            return redirect('stay_detail', pk=stay.pk)
    else:
        form = GuestStayForm(user=request.user)
    return render(request, 'stays/stay_form.html', {'form': form, 'mode': 'create'})


@login_required
@module_permission_required(NavigationService.MODULE_STAYS)
def stay_update(request, pk):
    if not _can_edit_stays(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    stay = get_object_or_404(GuestStay, pk=pk)
    old_status = stay.status
    if request.method == 'POST':
        form = GuestStayForm(request.POST, instance=stay, user=request.user)
        if form.is_valid():
            updated = form.save(commit=False)
            if old_status in GuestStay.CLOSED_STATUSES and updated.status in GuestStay.ACTIVE_STATUSES:
                form.add_error('status', 'This stay is already closed. Create a new booking for a new check-in.')
                return render(request, 'stays/stay_form.html', {'form': form, 'stay': stay, 'mode': 'edit'})
            now = timezone.now()
            if updated.daily_rate is None and updated.room_id:
                updated.daily_rate = updated.room.daily_rate
            if updated.status == GuestStay.STATUS_CHECKED_IN and old_status != GuestStay.STATUS_CHECKED_IN:
                if not updated.checked_in_at:
                    updated.checked_in_by_user = request.user
                    updated.checked_in_at = now
                    updated.checked_in_by_full_name = request.user.full_name
                    updated.checked_in_by_username = request.user.email
                    updated.checked_in_by_role = request.user.role
            if updated.status == GuestStay.STATUS_CHECKED_OUT and old_status != GuestStay.STATUS_CHECKED_OUT:
                if not updated.checked_out_at:
                    updated.checked_out_by_user = request.user
                    updated.checked_out_at = now
                    updated.checked_out_by_full_name = request.user.full_name
                    updated.checked_out_by_username = request.user.email
                    updated.checked_out_by_role = request.user.role
            updated.save()
            ActivityLog.log(
                request.user,
                'booking_edited',
                customer=updated.customer,
                booking=updated,
                notes=f"Edited booking for {updated.customer.full_name} in Room {updated.room.room_number}.",
            )
            if updated.status == GuestStay.STATUS_CHECKED_IN and old_status != GuestStay.STATUS_CHECKED_IN:
                ActivityLog.log(
                    request.user,
                    'guest_checked_in',
                    customer=updated.customer,
                    booking=updated,
                    notes=f"Checked {updated.customer.full_name} into Room {updated.room.room_number}.",
                )
            if updated.status == GuestStay.STATUS_CHECKED_OUT and old_status != GuestStay.STATUS_CHECKED_OUT:
                ActivityLog.log(
                    request.user,
                    'guest_checked_out',
                    customer=updated.customer,
                    booking=updated,
                    notes=f"Checked {updated.customer.full_name} out of Room {updated.room.room_number}.",
                )
            messages.success(request, 'Guest stay updated.')
            return redirect('stay_detail', pk=updated.pk)
    else:
        form = GuestStayForm(instance=stay, user=request.user)
    return render(request, 'stays/stay_form.html', {'form': form, 'stay': stay, 'mode': 'edit'})


@login_required
@module_permission_required(NavigationService.MODULE_STAYS)
def stay_status_update(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden("Invalid request.")

    stay = get_object_or_404(GuestStay, pk=pk)
    old_status = stay.status
    new_status = (request.POST.get('status') or '').strip()

    if request.user.role not in ['owner', 'admin', 'manager', 'staff']:
        return HttpResponseForbidden("You don't have permission to access this page.")

    allowed = {choice[0] for choice in GuestStay.STATUS_CHOICES}
    if new_status not in allowed:
        messages.error(request, 'Invalid status.')
        return redirect('stay_detail', pk=stay.pk)

    if request.user.role == 'staff' and new_status not in [GuestStay.STATUS_CHECKED_IN, GuestStay.STATUS_CHECKED_OUT]:
        return HttpResponseForbidden("You don't have permission to set this status.")
    if old_status in GuestStay.CLOSED_STATUSES and new_status in GuestStay.ACTIVE_STATUSES:
        messages.error(request, 'This stay is already closed. Create a new booking before checking the guest in again.')
        return redirect('stay_detail', pk=stay.pk)

    now = timezone.now()
    stay.status = new_status
    if new_status == GuestStay.STATUS_CHECKED_IN and old_status != GuestStay.STATUS_CHECKED_IN:
        if not stay.checked_in_at:
            stay.checked_in_by_user = request.user
            stay.checked_in_at = now
            stay.checked_in_by_full_name = request.user.full_name
            stay.checked_in_by_username = request.user.email
            stay.checked_in_by_role = request.user.role
    if new_status == GuestStay.STATUS_CHECKED_OUT and old_status != GuestStay.STATUS_CHECKED_OUT:
        if not stay.checked_out_at:
            stay.checked_out_by_user = request.user
            stay.checked_out_at = now
            stay.checked_out_by_full_name = request.user.full_name
            stay.checked_out_by_username = request.user.email
            stay.checked_out_by_role = request.user.role
    stay.save()

    if new_status != old_status:
        if new_status == GuestStay.STATUS_CHECKED_IN:
            ActivityLog.log(
                request.user,
                'guest_checked_in',
                customer=stay.customer,
                booking=stay,
                notes=f"Checked {stay.customer.full_name} into Room {stay.room.room_number}.",
            )
        if new_status == GuestStay.STATUS_CHECKED_OUT:
            ActivityLog.log(
                request.user,
                'guest_checked_out',
                customer=stay.customer,
                booking=stay,
                notes=f"Checked {stay.customer.full_name} out of Room {stay.room.room_number}.",
            )
        messages.success(request, f"Status changed to {stay.get_status_display()}.")
    return redirect('stay_detail', pk=stay.pk)
