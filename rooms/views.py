from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RoomForm
from .models import Room


def _can_manage_rooms(user):
    return user.role in ['owner', 'admin', 'manager']


def _can_delete_rooms(user):
    return user.role in ['owner', 'admin']


@login_required
def room_list(request):
    query = (request.GET.get('q') or '').strip()
    rooms = Room.objects.all()
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query)
            | Q(room_type__icontains=query)
            | Q(status__icontains=query)
        )
    return render(request, 'rooms/room_list.html', {'rooms': rooms, 'query': query})


@login_required
def room_create(request):
    if not _can_manage_rooms(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            messages.success(request, f"Room {room.room_number} created.")
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'rooms/room_form.html', {'form': form, 'mode': 'create'})


@login_required
def room_update(request, pk):
    if not _can_manage_rooms(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            updated = form.save()
            messages.success(request, f"Room {updated.room_number} updated.")
            return redirect('room_list')
    else:
        form = RoomForm(instance=room)
    return render(request, 'rooms/room_form.html', {'form': form, 'room': room, 'mode': 'edit'})


@login_required
def room_change_status(request, pk, status):
    if not _can_manage_rooms(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    room = get_object_or_404(Room, pk=pk)
    allowed = {choice[0] for choice in Room.STATUS_CHOICES}
    if status not in allowed:
        messages.error(request, 'Invalid status.')
        return redirect('room_list')
    room.status = status
    room.save(update_fields=['status', 'updated_at'])
    messages.success(request, f"Room {room.room_number} status changed to {room.get_status_display()}.")
    return redirect('room_list')


@login_required
def room_delete(request, pk):
    if not _can_delete_rooms(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        try:
            room_number = room.room_number
            room.delete()
            messages.success(request, f"Room {room_number} deleted.")
            return redirect('room_list')
        except ProtectedError:
            messages.error(request, 'This room cannot be deleted because it has guest stay records.')
            return redirect('room_list')
    return render(request, 'rooms/room_confirm_delete.html', {'room': room})
