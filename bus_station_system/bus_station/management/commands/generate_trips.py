# bus_station/management/commands/generate_trips.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from bus_station.models import Route, Trip, Bus
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Автоматичне формування рейсів на наступний день'

    def handle(self, *args, **options):
        tomorrow = timezone.now().date() + timedelta(days=1)
        tomorrow_weekday = tomorrow.isoweekday()  # 1-Понеділок, 7-Неділя

        self.stdout.write(f"Формування рейсів на {tomorrow.strftime('%d.%m.%Y')}...")

        # Знаходимо маршрути, які мають виходити завтра
        routes_to_generate = []
        for route in Route.objects.all():
            route_days = [int(day.strip()) for day in route.days_of_week.split(',')]
            if tomorrow_weekday in route_days:
                routes_to_generate.append(route)

        created_count = 0
        for route in routes_to_generate:
            # Перевіряємо, чи такий рейс вже існує
            if not Trip.objects.filter(route=route, date=tomorrow).exists():
                # Знаходимо доступний автобус відповідної марки
                available_bus = Bus.objects.filter(bus_model=route.bus_model).first()

                if available_bus:
                    try:
                        Trip.objects.create(
                            route=route,
                            bus=available_bus,
                            date=tomorrow
                        )
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Створено рейс: {route.number} - {tomorrow.strftime('%d.%m.%Y')}"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Помилка при створенні рейсу {route.number}: {e}"
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Немає доступного автобуса марки {route.bus_model} для рейсу {route.number}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Успішно створено {created_count} рейсів на {tomorrow.strftime('%d.%m.%Y')}"
            )
        )
        logger.info(f"Generated {created_count} trips for {tomorrow}")