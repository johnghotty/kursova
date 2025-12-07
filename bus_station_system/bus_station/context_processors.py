# bus_station/context_processors.py
from django.utils import timezone
from .models import Trip, Ticket

def station_stats(request):
    today = timezone.now().date()
    return {
        'today_trips_count': Trip.objects.filter(date=today).count(),
        'today_tickets_count': Ticket.objects.filter(trip__date=today, status='sold').count(),
    }