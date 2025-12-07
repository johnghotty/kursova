# bus_station/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q
from datetime import timedelta
from .models import Ticket, Trip, Route, Destination, Bus, BusModel
from .utils import (generate_ticket_number, calculate_final_ticket_price,
                    validate_seat_number, get_available_seats, get_trip_occupancy_percentage)


# ===== TICKET VIEWS =====

class TicketListView(ListView):
    model = Ticket
    template_name = 'bus_station/tickets/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def get_queryset(self):
        queryset = Ticket.objects.select_related(
            'trip__route__destination',
            'trip__bus__bus_model'
        ).order_by('-booking_time')

        # Фільтрація за статусом
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Фільтрація за датою рейсу
        trip_date = self.request.GET.get('trip_date')
        if trip_date:
            queryset = queryset.filter(trip__date=trip_date)

        return queryset


class TicketDetailView(DetailView):
    model = Ticket
    template_name = 'bus_station/tickets/ticket_detail.html'
    context_object_name = 'ticket'

    def get_queryset(self):
        return Ticket.objects.select_related(
            'trip__route__destination',
            'trip__bus__bus_model'
        )


class TicketCreateView(CreateView):
    model = Ticket
    fields = ['trip', 'seat_number']
    template_name = 'bus_station/tickets/ticket_create.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Обмежуємо вибір тільки майбутніми рейсами
        form.fields['trip'].queryset = Trip.objects.filter(
            date__gte=timezone.now().date()
        ).select_related('route__destination', 'bus__bus_model')
        return form

    def form_valid(self, form):
        with transaction.atomic():
            ticket = form.save(commit=False)
            ticket.ticket_number = generate_ticket_number(ticket.trip)
            ticket.status = 'booked'

            # Перевірка доступності місця
            is_valid, error_message = validate_seat_number(ticket.trip, ticket.seat_number)
            if not is_valid:
                form.add_error('seat_number', error_message)
                return self.form_invalid(form)

            # Розрахунок ціни
            sold_count = ticket.trip.get_sold_tickets_count()
            ticket.price = calculate_final_ticket_price(ticket.trip, sold_count)

            ticket.save()
            messages.success(self.request, f'Квиток {ticket.ticket_number} успішно заброньовано!')

        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('ticket_detail', kwargs={'pk': self.object.pk})

class TicketUpdateView(UpdateView):
    model = Ticket
    template_name = 'bus_station/tickets/ticket_update.html'
    fields = ['status']

    def form_valid(self, form):
        ticket = form.save(commit=False)

        if ticket.status == 'sold' and not ticket.sold_time:
            ticket.sold_time = timezone.now()

        ticket.save()
        messages.success(self.request, f'Статус квитка {ticket.ticket_number} оновлено!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('ticket_detail', kwargs={'pk': self.object.pk})


class GetAvailableSeatsView(View):
    def get(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id)
        available_seats = get_available_seats(trip)

        return JsonResponse({
            'available_seats': available_seats,
            'total_seats': trip.bus.bus_model.seats_count
        })


class ConfirmBookingView(View):
    def post(self, request, ticket_id):
        ticket = get_object_or_404(Ticket, id=ticket_id, status='booked')

        if ticket.is_booking_expired():
            messages.error(request, 'Бронювання прострочено!')
            return redirect('ticket_detail', pk=ticket_id)

        with transaction.atomic():
            ticket.status = 'sold'
            ticket.sold_time = timezone.now()
            ticket.save()
            messages.success(request, f'Бронювання підтверджено! Квиток {ticket.ticket_number} продано.')

        return redirect('ticket_detail', pk=ticket_id)


class CancelBookingView(View):
    def post(self, request, ticket_id):
        ticket = get_object_or_404(Ticket, id=ticket_id)

        with transaction.atomic():
            ticket.status = 'cancelled'
            ticket.save()
            messages.success(request, f'Бронювання квитка {ticket.ticket_number} скасовано.')

        return redirect('ticket_list')


# ===== ROUTE VIEWS =====

class TripListView(ListView):
    model = Trip
    template_name = 'bus_station/trips/trip_list.html'
    context_object_name = 'trips'
    paginate_by = 20

    def get_queryset(self):
        queryset = Trip.objects.select_related(
            'route__destination',
            'bus__bus_model'
        ).order_by('date', 'route__departure_time')

        # Фільтрація за датою
        date_filter = self.request.GET.get('date')
        if date_filter:
            queryset = queryset.filter(date=date_filter)
        else:
            # За замовчуванням показуємо сьогодні та майбутні рейси
            queryset = queryset.filter(date__gte=timezone.now().date())

        # Фільтрація за пунктом призначення
        destination_id = self.request.GET.get('destination')
        if destination_id:
            queryset = queryset.filter(route__destination_id=destination_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['destinations'] = Destination.objects.all()
        context['selected_date'] = self.request.GET.get('date', '')
        context['selected_destination'] = self.request.GET.get('destination', '')
        return context


class TripDetailView(DetailView):
    model = Trip
    template_name = 'bus_station/trips/trip_detail.html'
    context_object_name = 'trip'

    def get_queryset(self):
        return Trip.objects.select_related(
            'route__destination',
            'bus__bus_model'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip = self.object

        # Додаємо інформацію про вільні місця
        context['available_seats'] = get_available_seats(trip)
        context['occupancy_percentage'] = get_trip_occupancy_percentage(trip)
        context['sold_tickets_count'] = trip.get_sold_tickets_count()
        context['total_seats'] = trip.bus.bus_model.seats_count

        # Додаємо квитки цього рейсу
        context['tickets'] = trip.ticket_set.select_related().all()

        return context


class RouteListView(ListView):
    model = Route
    template_name = 'bus_station/trips/route_list.html'
    context_object_name = 'routes'

    def get_queryset(self):
        return Route.objects.select_related('destination', 'bus_model').order_by('number')


class RouteDetailView(DetailView):
    model = Route
    template_name = 'bus_station/trips/route_detail.html'
    context_object_name = 'route'

    def get_queryset(self):
        return Route.objects.select_related('destination', 'bus_model')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Додаємо майбутні рейси для цього маршруту
        context['future_trips'] = self.object.trip_set.filter(
            date__gte=timezone.now().date()
        ).select_related('bus').order_by('date')[:10]
        return context


# ===== REPORT VIEWS =====

def report_most_popular_destinations(request):
    """1. Пункти прибуття, до яких здійснено найбільше рейсів"""

    # За останній місяць
    last_month = timezone.now().date() - timedelta(days=30)

    popular_destinations = Trip.objects.filter(
        date__gte=last_month
    ).values(
        'route__destination__name'
    ).annotate(
        trip_count=Count('id')
    ).order_by('-trip_count')

    context = {
        'report_title': 'Найпопулярніші пункти прибуття',
        'destinations': popular_destinations,
        'period': 'за останній місяць'
    }
    return render(request, 'bus_station/reports/report_popular_destinations.html', context)


def report_trip_dates_coordination(request):
    """2. Узгодження дат виїзду з днями здійснення рейсів"""

    # Знаходимо рейси, де дата не відповідає дням тижня маршруту
    problematic_trips = []
    for trip in Trip.objects.select_related('route').all():
        route_days = [int(day.strip()) for day in trip.route.days_of_week.split(',')]
        trip_weekday = trip.date.isoweekday()  # 1-Понеділок, 7-Неділя

        if trip_weekday not in route_days:
            problematic_trips.append({
                'trip': trip,
                'scheduled_days': trip.route.get_days_of_week_display(),
                'actual_day': trip.date.strftime('%A')
            })

    context = {
        'report_title': 'Узгодження дат рейсів',
        'problematic_trips': problematic_trips
    }
    return render(request, 'bus_station/reports/report_trip_dates.html', context)


# bus_station/views.py

def report_average_bus_occupancy(request):
    """3. Середня наповненість автобусів по кожному рейсу за останній місяць"""

    last_month = timezone.now().date() - timedelta(days=30)

    # Отримуємо дані по рейсах за останній місяць
    trips_data = Trip.objects.filter(
        date__gte=last_month
    ).select_related('route', 'bus__bus_model').annotate(
        sold_tickets_count=Count('ticket', filter=Q(ticket__status='sold'))
    )

    # Групуємо дані вручну
    from collections import defaultdict
    route_data = defaultdict(list)

    for trip in trips_data:
        key = (trip.route.number, trip.route.destination.name, trip.bus.bus_model.name)
        route_data[key].append({
            'sold_tickets': trip.sold_tickets_count,
            'total_seats': trip.bus.bus_model.seats_count
        })

    # Обчислюємо середнє для кожної групи
    occupancy_data = []
    for key, trips in route_data.items():
        route_number, destination_name, bus_model_name = key

        total_sold = sum(trip['sold_tickets'] for trip in trips)
        total_trips = len(trips)
        avg_occupancy = total_sold / total_trips if total_trips > 0 else 0

        # Визначаємо кількість місць (беремо з першого рейсу, оскільки вони однакові для марки)
        total_seats = trips[0]['total_seats'] if trips else 0
        occupancy_percentage = (avg_occupancy / total_seats) * 100 if total_seats > 0 else 0

        occupancy_data.append({
            'route_number': route_number,
            'destination_name': destination_name,
            'bus_model_name': bus_model_name,
            'avg_occupancy': round(avg_occupancy, 1),
            'total_trips': total_trips,
            'occupancy_percentage': round(occupancy_percentage, 1)
        })

    # Сортуємо за номером рейсу
    occupancy_data.sort(key=lambda x: x['route_number'])

    context = {
        'report_title': 'Середня наповненість автобусів',
        'occupancy_data': occupancy_data,
        'period': 'за останній місяць'
    }
    return render(request, 'bus_station/reports/report_occupancy.html', context)

def report_busiest_days(request):
    """4. Дні тижня, на які припадає найбільше/найменше рейсів"""

    days_data = Trip.objects.values(
        'date__week_day'
    ).annotate(
        trip_count=Count('id')
    ).order_by('date__week_day')

    # Мапінг номерів днів тижня Django на назви
    day_names = {
        1: 'Неділя', 2: 'Понеділок', 3: 'Вівторок',
        4: 'Середа', 5: 'Четвер', 6: 'П\'ятниця', 7: 'Субота'
    }

    for day in days_data:
        day['day_name'] = day_names.get(day['date__week_day'], 'Невідомо')

    if days_data:
        busiest_day = max(days_data, key=lambda x: x['trip_count'])
        quietest_day = min(days_data, key=lambda x: x['trip_count'])
    else:
        busiest_day = quietest_day = None

    context = {
        'report_title': 'Завантаженість по днях тижня',
        'days_data': days_data,
        'busiest_day': busiest_day,
        'quietest_day': quietest_day
    }
    return render(request, 'bus_station/reports/report_busiest_days.html', context)


def report_rarest_trips(request):
    """5. Рейси, які здійснюються найрідше"""

    # Рейси з найменшою кількістю поїздок за останні 3 місяці
    three_months_ago = timezone.now().date() - timedelta(days=90)

    rare_trips = Trip.objects.filter(
        date__gte=three_months_ago
    ).values(
        'route__number',
        'route__destination__name',
        'route__days_of_week'
    ).annotate(
        trip_count=Count('id')
    ).order_by('trip_count')[:10]  # Топ-10 найрідших

    context = {
        'report_title': 'Найрідші рейси',
        'rare_trips': rare_trips,
        'period': 'за останні 3 місяці'
    }
    return render(request, 'bus_station/reports/report_rarest_trips.html', context)


# bus_station/views.py
def report_revenue_by_destination(request):
    """6. Виручка від продажу квитків по кожному пункту прибуття"""

    revenue_data = Ticket.objects.filter(
        status='sold'
    ).values(
        'trip__route__destination__name'
    ).annotate(
        total_revenue=Sum('price'),
        tickets_sold=Count('id')
    ).order_by('-total_revenue')

    # Обчислити загальні суми
    total_tickets = sum(item['tickets_sold'] for item in revenue_data)
    total_revenue = sum(float(item['total_revenue']) for item in revenue_data)

    context = {
        'report_title': 'Виручка по пунктах прибуття',
        'revenue_data': revenue_data,
        'total_tickets': total_tickets,
        'total_revenue': total_revenue,
    }
    return render(request, 'bus_station/reports/report_revenue.html', context)


def reports_dashboard(request):
    """Головна сторінка звітів"""
    return render(request, 'bus_station/reports/reports_dashboard.html')


# ===== BUS VIEWS =====

class BusListView(ListView):
    model = Bus
    template_name = 'bus_station/buses/bus_list.html'
    context_object_name = 'buses'

    def get_queryset(self):
        return Bus.objects.select_related('bus_model').order_by('bus_model__name', 'number')


class BusDetailView(DetailView):
    model = Bus
    template_name = 'bus_station/buses/bus_detail.html'
    context_object_name = 'bus'

    def get_queryset(self):
        return Bus.objects.select_related('bus_model')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Додаємо майбутні рейси для цього автобуса
        context['future_trips'] = self.object.trip_set.filter(
            date__gte=timezone.now().date()
        ).select_related('route__destination').order_by('date')[:10]
        return context


class BusModelListView(ListView):
    model = BusModel
    template_name = 'bus_station/buses/bus_model_list.html'
    context_object_name = 'bus_models'


class DestinationListView(ListView):
    model = Destination
    template_name = 'bus_station/buses/destination_list.html'
    context_object_name = 'destinations'


# ===== HOME VIEW =====

def home(request):
    """Головна сторінка системи"""
    # Статистика для головної сторінки
    today = timezone.now().date()
    today_trips = Trip.objects.filter(date=today).count()
    today_tickets = Ticket.objects.filter(trip__date=today, status='sold').count()

    context = {
        'today_trips': today_trips,
        'today_tickets': today_tickets,
        'today_date': today
    }
    return render(request, 'bus_station/home.html', context)


def handler404(request, exception):
    return render(request, 'bus_station/errors/404.html', status=404)

def handler500(request):
    return render(request, 'bus_station/errors/500.html', status=500)