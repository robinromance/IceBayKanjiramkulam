from django.urls import path
from . import views

urlpatterns = [
    path('daily/', views.daily_reports, name="daily_reports"),
    path('generate/', views.generate_today_report, name="generate_today_report"),
]
