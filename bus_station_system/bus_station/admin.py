# bus_station/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    Destination, BusModel, Bus, Route,
    FuelPrice, Trip, Ticket
)


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(BusModel)
class BusModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'fuel_consumption', 'seats_count']
    list_filter = ['name']
    search_fields = ['name']


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ['bus_model', 'number']
    list_filter = ['bus_model']
    search_fields = ['number', 'bus_model__name']


class TripInline(admin.TabularInline):
    model = Trip
    extra = 0
    fields = ['date', 'bus']
    readonly_fields = ['date', 'bus']
    can_delete = False
    max_num = 0


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'destination', 'distance',
        'departure_time', 'arrival_time', 'bus_model'
    ]
    list_filter = ['destination', 'bus_model', 'days_of_week']
    search_fields = ['number', 'destination__name']
    inlines = [TripInline]

    def get_days_display(self, obj):
        return obj.get_days_of_week_display()

    get_days_display.short_description = 'Дні тижня'


@admin.register(FuelPrice)
class FuelPriceAdmin(admin.ModelAdmin):
    list_display = ['price', 'date_updated']
    readonly_fields = ['date_updated']

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        # Дозволити тільки одну запис ціни палива
        return FuelPrice.objects.count() == 0


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    fields = ['ticket_number', 'seat_number', 'status', 'price']
    readonly_fields = ['ticket_number', 'seat_number', 'status', 'price']
    can_delete = False
    max_num = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = [
        'route', 'date', 'bus', 'sold_tickets_count',
        'seats_available', 'trip_status'
    ]
    list_filter = ['date', 'route__destination', 'bus__bus_model']
    search_fields = ['route__number', 'bus__number']
    readonly_fields = ['sold_tickets_count_display', 'seats_available_display']
    inlines = [TicketInline]

    def sold_tickets_count(self, obj):
        return obj.get_sold_tickets_count()

    sold_tickets_count.short_description = 'Продано квитків'

    def seats_available(self, obj):
        sold = obj.get_sold_tickets_count()
        total = obj.bus.bus_model.seats_count
        return f"{sold}/{total}"

    seats_available.short_description = 'Місць (продано/всього)'

    def trip_status(self, obj):
        sold = obj.get_sold_tickets_count()
        total = obj.bus.bus_model.seats_count
        if sold == total:
            return format_html('<span style="color: red;">Повний</span>')
        elif sold > total * 0.8:
            return format_html('<span style="color: orange;">Майже повний</span>')
        else:
            return format_html('<span style="color: green;">Є місця</span>')

    trip_status.short_description = 'Статус'

    def sold_tickets_count_display(self, obj):
        return obj.get_sold_tickets_count()

    sold_tickets_count_display.short_description = 'Кількість проданих квитків'

    def seats_available_display(self, obj):
        sold = obj.get_sold_tickets_count()
        total = obj.bus.bus_model.seats_count
        return f"{total - sold} з {total}"

    seats_available_display.short_description = 'Вільних місць'

    fieldsets = (
        ('Основна інформація', {
            'fields': ('route', 'bus', 'date')
        }),
        ('Статистика', {
            'fields': ('sold_tickets_count_display', 'seats_available_display')
        }),
    )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'trip', 'seat_number',
        'status', 'price', 'booking_time', 'is_expired_display'
    ]
    list_filter = ['status', 'trip__date', 'trip__route']
    search_fields = ['ticket_number', 'trip__route__number']
    readonly_fields = ['booking_time', 'sold_time', 'is_expired_display']

    def is_expired_display(self, obj):
        if obj.status == 'booked' and obj.is_booking_expired():
            return format_html('<span style="color: red;">ТЕРМІН ДІЇ ЗАКІНЧИВСЯ</span>')
        elif obj.status == 'booked':
            return format_html('<span style="color: orange;">ДІЙСНИЙ</span>')
        else:
            return '-'

    is_expired_display.short_description = 'Статус бронювання'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'trip__route', 'trip__bus'
        )

    fieldsets = (
        ('Основна інформація', {
            'fields': ('ticket_number', 'trip', 'seat_number', 'status', 'price')
        }),
        ('Час', {
            'fields': ('booking_time', 'sold_time', 'is_expired_display')
        }),
    )

    actions = ['cancel_expired_bookings']

    def cancel_expired_bookings(self, request, queryset):
        # Скасування прострочених бронювань
        expired_count = 0
        for ticket in queryset:
            if ticket.status == 'booked' and ticket.is_booking_expired():
                ticket.status = 'cancelled'
                ticket.save()
                expired_count += 1

        self.message_user(
            request,
            f"Скасовано {expired_count} прострочених бронювань."
        )

    cancel_expired_bookings.short_description = "Скасувати прострочені бронювання"


# Додамо кастомну головну сторінку адмінки
admin.site.site_header = "Система обліку продажу квитків на автовокзалі"
admin.site.site_title = "Автовокзал"
admin.site.index_title = "Управління даними"