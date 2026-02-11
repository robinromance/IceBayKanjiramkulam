from django.urls import path
from . import views

urlpatterns = [
    path('remaining/', views.remaining_stock, name='remaining_stock'),
    path('finished/', views.finished_stocks, name='finished_stocks'),
]