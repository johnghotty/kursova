# bus_station/apps.py
from django.apps import AppConfig

class BusStationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bus_station'
    verbose_name = 'Система автовокзалу'