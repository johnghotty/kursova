# bus_station/management/commands/cancel_expired_bookings.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from bus_station.models import Ticket
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Автоматичне скасування прострочених бронювань'

    def handle(self, *args, **options):
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)

        self.stdout.write("Пошук прострочених бронювань...")

        # Знаходимо всі заброньовані квитки, де бронь старша за 1 годину
        expired_bookings = Ticket.objects.filter(
            status='booked',
            booking_time__lte=one_hour_ago
        )

        expired_count = expired_bookings.count()

        if expired_count == 0:
            self.stdout.write(self.style.SUCCESS("Прострочених бронювань не знайдено"))
            return

        self.stdout.write(f"Знайдено {expired_count} прострочених бронювань")

        # Скасовуємо кожне прострочене бронювання
        cancelled_count = 0
        for booking in expired_bookings:
            try:
                booking.status = 'cancelled'
                booking.save()
                cancelled_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Скасовано бронювання {booking.ticket_number} "
                        f"(заброньовано {booking.booking_time.strftime('%H:%M')})"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Помилка при скасуванні бронювання {booking.ticket_number}: {e}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Успішно скасовано {cancelled_count} прострочених бронювань"
            )
        )
        logger.info(f"Cancelled {cancelled_count} expired bookings at {now}")

        # Додаткова інформація про скасування
        if cancelled_count < expired_count:
            self.stdout.write(
                self.style.WARNING(
                    f"Не вдалося скасувати {expired_count - cancelled_count} бронювань"
                )
            )