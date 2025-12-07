# bus_station/urls.py
from django.urls import path
from . import views

# app_name = 'bus_station'

urlpatterns = [
    # Головна сторінка
    path('', views.home, name='home'),

    # Квитки
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/create/', views.TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    path('tickets/<int:pk>/update/', views.TicketUpdateView.as_view(), name='ticket_update'),
    path('tickets/<int:ticket_id>/confirm/', views.ConfirmBookingView.as_view(), name='confirm_booking'),
    path('tickets/<int:ticket_id>/cancel/', views.CancelBookingView.as_view(), name='cancel_booking'),
    path('tickets/get-available-seats/<int:trip_id>/', views.GetAvailableSeatsView.as_view(),
         name='get_available_seats'),

    # Рейси
    path('trips/', views.TripListView.as_view(), name='trip_list'),
    path('trips/<int:pk>/', views.TripDetailView.as_view(), name='trip_detail'),

    # Маршрути
    path('routes/', views.RouteListView.as_view(), name='route_list'),
    path('routes/<int:pk>/', views.RouteDetailView.as_view(), name='route_detail'),

    # Автобуси
    path('buses/', views.BusListView.as_view(), name='bus_list'),
    path('buses/<int:pk>/', views.BusDetailView.as_view(), name='bus_detail'),
    path('bus-models/', views.BusModelListView.as_view(), name='bus_model_list'),
    path('destinations/', views.DestinationListView.as_view(), name='destination_list'),

    # Звіти
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/popular-destinations/', views.report_most_popular_destinations,
         name='report_most_popular_destinations'),
    path('reports/trip-dates/', views.report_trip_dates_coordination, name='report_trip_dates_coordination'),
    path('reports/occupancy/', views.report_average_bus_occupancy, name='report_average_bus_occupancy'),
    path('reports/busiest-days/', views.report_busiest_days, name='report_busiest_days'),
    path('reports/rarest-trips/', views.report_rarest_trips, name='report_rarest_trips'),
    path('reports/revenue/', views.report_revenue_by_destination, name='report_revenue_by_destination'),
]