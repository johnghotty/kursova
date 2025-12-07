# bus_station/utils.py
from django.utils import timezone
from decimal import Decimal
from .models import FuelPrice, Trip, Ticket
import logging

logger = logging.getLogger(__name__)


def get_current_fuel_price():
    """
    Отримати поточну ціну пального
    """
    try:
        return FuelPrice.objects.latest('date_updated')
    except FuelPrice.DoesNotExist:
        logger.error("Ціна пального не встановлена")
        return None


def calculate_base_price(route, fuel_price_obj):
    """
    Розрахунок базової ціни квитка за формулою
    тариф × відстань / 100 + витрати пального × ціна пального
    """
    if not fuel_price_obj:
        return Decimal('0')

    base_price = (
            route.tariff * route.distance / Decimal('100') +
            route.bus_model.fuel_consumption * fuel_price_obj.price
    )
    return base_price


def calculate_distance_discount(distance):
    """
    Розрахунок знижки за відстанню
    15% знижка для відстаней до 25 км включно
    """
    if distance <= Decimal('25'):
        return Decimal('0.15')
    return Decimal('0')


def calculate_occupancy_discount(sold_tickets_count):
    """
    Розрахунок знижки за наповненістю автобуса
    """
    if sold_tickets_count >= 50:
        return Decimal('0.50')
    elif sold_tickets_count >= 40:
        return Decimal('0.40')
    elif sold_tickets_count >= 30:
        return Decimal('0.30')
    elif sold_tickets_count >= 20:
        return Decimal('0.20')
    elif sold_tickets_count >= 10:
        return Decimal('0.10')
    return Decimal('0')


def calculate_final_ticket_price(trip, sold_tickets_count=None):
    """
    Розрахунок фінальної ціни квитка з урахуванням всіх знижок
    """
    if sold_tickets_count is None:
        sold_tickets_count = trip.get_sold_tickets_count()

    fuel_price = get_current_fuel_price()
    base_price = calculate_base_price(trip.route, fuel_price)

    # Розраховуємо знижки
    distance_discount = calculate_distance_discount(trip.route.distance)
    occupancy_discount = calculate_occupancy_discount(sold_tickets_count)

    # Сумарна знижка
    total_discount = distance_discount + occupancy_discount

    # Застосовуємо знижку
    final_price = base_price * (Decimal('1') - total_discount)

    # Ціна не може бути від'ємною
    return max(final_price, Decimal('0'))


def generate_ticket_number(trip):
    """
    Генерація унікального номера квитка
    Формат: РЕЙС_ДАТА_ЧАС
    """
    timestamp = timezone.now().strftime("%H%M%S")
    return f"{trip.route.number}_{trip.date.strftime('%d%m%Y')}_{timestamp}"


def get_available_seats(trip):
    """
    Отримати список вільних місць для рейсу
    """
    total_seats = trip.bus.bus_model.seats_count

    # Місця, які вже зайняті (продані або заброньовані)
    occupied_seats = Ticket.objects.filter(
        trip=trip
    ).exclude(
        status='cancelled'
    ).values_list('seat_number', flat=True)

    # Всі можливі місця
    all_seats = list(range(1, total_seats + 1))

    # Вільні місця
    available_seats = [seat for seat in all_seats if seat not in occupied_seats]

    return available_seats


def is_seat_available(trip, seat_number):
    """
    Перевірити, чи вільне місце
    """
    return not Ticket.objects.filter(
        trip=trip,
        seat_number=seat_number
    ).exclude(status='cancelled').exists()


def get_trip_occupancy_percentage(trip):
    """
    Отримати відсоток заповненості автобуса
    """
    sold_count = trip.get_sold_tickets_count()
    total_seats = trip.bus.bus_model.seats_count

    if total_seats == 0:
        return 0

    return (sold_count / total_seats) * 100


def cancel_expired_bookings():
    """
    Скасувати всі прострочені бронювання
    Повертає кількість скасованих бронювань
    """
    expired_bookings = Ticket.objects.filter(
        status='booked'
    )

    cancelled_count = 0
    for booking in expired_bookings:
        if booking.is_booking_expired():
            booking.status = 'cancelled'
            booking.save()
            cancelled_count += 1
            logger.info(f"Скасовано прострочене бронювання {booking.ticket_number}")

    return cancelled_count


def get_trips_for_tomorrow():
    """
    Отримати список рейсів на наступний день
    """
    tomorrow = timezone.now().date() + timezone.timedelta(days=1)
    return Trip.objects.filter(date=tomorrow)


def validate_seat_number(trip, seat_number):
    """
    Валідація номера місця для рейсу
    """
    if seat_number < 1 or seat_number > trip.bus.bus_model.seats_count:
        return False, f"Номер місця має бути від 1 до {trip.bus.bus_model.seats_count}"

    if not is_seat_available(trip, seat_number):
        return False, f"Місце {seat_number} вже зайняте"

    return True, "Місце доступне"


def get_ticket_history(ticket_number):
    """
    Отримати повну історію квитка
    """
    try:
        ticket = Ticket.objects.select_related(
            'trip__route__destination',
            'trip__bus__bus_model'
        ).get(ticket_number=ticket_number)

        history = {
            'ticket': ticket,
            'trip_info': {
                'route': ticket.trip.route.number,
                'destination': ticket.trip.route.destination.name,
                'date': ticket.trip.date,
                'departure_time': ticket.trip.route.departure_time,
                'bus': f"{ticket.trip.bus.bus_model.name} - {ticket.trip.bus.number}"
            },
            'price_calculation': {
                'base_price': calculate_base_price(ticket.trip.route, get_current_fuel_price()),
                'final_price': ticket.price,
                'status': ticket.get_status_display()
            }
        }
        return history
    except Ticket.DoesNotExist:
        return None


# bus_station/utils.py (доповнення)
def get_tomorrow_trips():
    """Отримати рейси на завтра"""
    from django.utils import timezone
    tomorrow = timezone.now().date() + timezone.timedelta(days=1)
    return Trip.objects.filter(date=tomorrow).select_related('route__destination', 'bus__bus_model')

def get_today_trips():
    """Отримати рейси на сьогодні"""
    from django.utils import timezone
    today = timezone.now().date()
    return Trip.objects.filter(date=today).select_related('route__destination', 'bus__bus_model')

def get_revenue_for_period(start_date, end_date):
    """Отримати виручку за період"""
    return Ticket.objects.filter(
        status='sold',
        sold_time__date__range=[start_date, end_date]
    ).aggregate(total_revenue=Sum('price'))['total_revenue'] or 0