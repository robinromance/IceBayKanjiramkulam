from django.urls import path
from . import views

urlpatterns = [
    path('remaining/', views.remaining_stock, name='remaining_stock'),
    path('finished/', views.finished_stocks, name='finished_stocks'),
    path("add-stock/", views.add_stock_page, name="add_stock_page"),
]