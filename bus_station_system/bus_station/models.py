# bus_station/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class Destination(models.Model):
    name = models.CharField(max_length=100, verbose_name="Назва пункту прибуття")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Пункт прибуття"
        verbose_name_plural = "Пункти прибуття"


class BusModel(models.Model):
    name = models.CharField(max_length=50, verbose_name="Марка автобуса")
    fuel_consumption = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Витрати пального на 100 км"
    )
    seats_count = models.PositiveIntegerField(verbose_name="Кількість місць")

    def __str__(self):
        return f"{self.name} ({self.seats_count} місць)"

    class Meta:
        verbose_name = "Марка автобуса"
        verbose_name_plural = "Марки автобусів"


class Bus(models.Model):
    bus_model = models.ForeignKey(
        BusModel,
        on_delete=models.CASCADE,
        verbose_name="Марка автобуса"
    )
    number = models.CharField(max_length=20, verbose_name="Номер автобуса")

    def __str__(self):
        return f"{self.bus_model.name} - {self.number}"

    class Meta:
        verbose_name = "Автобус"
        verbose_name_plural = "Автобуси"


class Route(models.Model):
    DAYS_OF_WEEK = [
        (1, 'Понеділок'),
        (2, 'Вівторок'),
        (3, 'Середа'),
        (4, 'Четвер'),
        (5, 'П\'ятниця'),
        (6, 'Субота'),
        (7, 'Неділя'),
    ]

    number = models.CharField(max_length=20, verbose_name="Номер рейсу")
    tariff = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Тариф рейсу")
    days_of_week = models.CharField(max_length=50, verbose_name="Дні тижня виїзду")
    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        verbose_name="Пункт прибуття"
    )
    distance = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Відстань (км)")
    departure_time = models.TimeField(verbose_name="Час відправлення")
    arrival_time = models.TimeField(verbose_name="Час прибуття")
    bus_model = models.ForeignKey(
        BusModel,
        on_delete=models.CASCADE,
        verbose_name="Марка автобуса"
    )

    def get_days_of_week_display(self):
        days = [int(day.strip()) for day in self.days_of_week.split(',')]
        return ', '.join([dict(self.DAYS_OF_WEEK).get(day, '') for day in days])

    def __str__(self):
        return f"Рейс {self.number} - {self.destination.name}"

    class Meta:
        verbose_name = "Маршрут"
        verbose_name_plural = "Маршрути"


class FuelPrice(models.Model):
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Ціна пального")
    date_updated = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    def __str__(self):
        return f"Пальне: {self.price} (оновлено {self.date_updated.strftime('%d.%m.%Y %H:%M')})"

    class Meta:
        verbose_name = "Ціна пального"
        verbose_name_plural = "Ціни пального"


class Trip(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, verbose_name="Маршрут")
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, verbose_name="Автобус")
    date = models.DateField(verbose_name="Дата виїзду")

    def calculate_ticket_price(self, sold_tickets_count=0):
        """Розрахунок вартості квитка з урахуванням знижок"""
        try:
            fuel_price = FuelPrice.objects.latest('date_updated')
        except FuelPrice.DoesNotExist:
            fuel_price = None

        if not fuel_price:
            return Decimal('0')

        # Базова ціна за формулою
        base_price = (
                self.route.tariff * self.route.distance / Decimal('100') +
                self.route.bus_model.fuel_consumption * fuel_price.price
        )

        # Знижка за відстанню
        discount = Decimal('0')
        if self.route.distance <= Decimal('25'):
            discount += Decimal('0.15')  # 15% знижка

        # Знижка за наповненістю
        if sold_tickets_count >= 50:
            discount += Decimal('0.50')
        elif sold_tickets_count >= 40:
            discount += Decimal('0.40')
        elif sold_tickets_count >= 30:
            discount += Decimal('0.30')
        elif sold_tickets_count >= 20:
            discount += Decimal('0.20')
        elif sold_tickets_count >= 10:
            discount += Decimal('0.10')

        # Застосовуємо знижку
        final_price = base_price * (Decimal('1') - discount)
        return max(final_price, Decimal('0'))  # Ціна не може бути від'ємною

    def get_sold_tickets_count(self):
        return self.ticket_set.filter(status='sold').count()

    def clean(self):
        # Перевірка, що автобус відповідає марці маршруту
        if self.bus.bus_model != self.route.bus_model:
            raise ValidationError("Автобус повинен бути тієї ж марки, що вказана в маршруті")

    def __str__(self):
        return f"{self.route.number} - {self.date}"

    class Meta:
        verbose_name = "Рейс"
        verbose_name_plural = "Рейси"
        unique_together = ['route', 'date']


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('booked', 'Заброньовано'),
        ('sold', 'Продано'),
        ('cancelled', 'Скасовано'),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, verbose_name="Рейс")
    ticket_number = models.CharField(max_length=20, unique=True, verbose_name="№ квитка")
    seat_number = models.PositiveIntegerField(verbose_name="№ місця")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='booked',
        verbose_name="Статус"
    )
    booking_time = models.DateTimeField(auto_now_add=True, verbose_name="Дата та час бронювання")
    sold_time = models.DateTimeField(null=True, blank=True, verbose_name="Дата та час продажу")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сума, сплачена за квиток"
    )

    def is_booking_expired(self):
        """Перевірка чи минула 1 година з моменту бронювання"""
        if self.status == 'booked':
            time_passed = timezone.now() - self.booking_time
            return time_passed.total_seconds() > 3600  # 1 година
        return False

    def clean(self):
        # Перевірка, що місце не перевищує кількість місць в автобусі
        if self.seat_number > self.trip.bus.bus_model.seats_count:
            raise ValidationError(
                f"Номер місця не може бути більшим за {self.trip.bus.bus_model.seats_count}"
            )

        # Перевірка, що місце не зайняте в цьому рейсі
        existing_ticket = Ticket.objects.filter(
            trip=self.trip,
            seat_number=self.seat_number
        ).exclude(pk=self.pk).exclude(status='cancelled').first()

        if existing_ticket:
            raise ValidationError(f"Місце {self.seat_number} вже зайняте")

    def save(self, *args, **kwargs):
        # Автоматичне встановлення sold_time при зміні статусу на 'sold'
        if self.status == 'sold' and not self.sold_time:
            self.sold_time = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Квиток {self.ticket_number} - {self.trip}"

    class Meta:
        verbose_name = "Квиток"
        verbose_name_plural = "Квитки"