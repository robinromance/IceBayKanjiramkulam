from django.urls import path
from . import views

urlpatterns = [
    path('daily-reports/', views.daily_reports, name='daily_reports'),
    path('generate-report/', views.generate_today_report, name='generate_today_report'),
    path('bill/<int:bill_id>/', views.bill_detail, name='bill_detail'),
]