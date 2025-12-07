# bus_station/forms.py
from django import forms
from .models import Ticket, Trip, FuelPrice


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['trip', 'seat_number']
        widgets = {
            'trip': forms.Select(attrs={'class': 'form-select'}),
            'seat_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def clean_seat_number(self):
        seat_number = self.cleaned_data['seat_number']
        trip = self.cleaned_data.get('trip')

        if trip and seat_number:
            if seat_number > trip.bus.bus_model.seats_count:
                raise forms.ValidationError(
                    f"Місце {seat_number} не існує. Максимальний номер: {trip.bus.bus_model.seats_count}"
                )

            # Перевірка чи місце вже зайняте
            from .utils import is_seat_available
            if not is_seat_available(trip, seat_number):
                raise forms.ValidationError(f"Місце {seat_number} вже зайняте")

        return seat_number


class FuelPriceForm(forms.ModelForm):
    class Meta:
        model = FuelPrice
        fields = ['price']
        widgets = {
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        labels = {
            'price': 'Ціна пального (грн/л)',
        }