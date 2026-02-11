from django.urls import path
from . import views

urlpatterns = [
    path('', views.billing_page, name="billing_page"),
    path("create-bill-api/", views.create_bill_api, name="create_bill_api"),
]