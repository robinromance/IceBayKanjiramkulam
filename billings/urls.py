from django.urls import path
from . import views

app_name = 'billings'

urlpatterns = [
    path("", views.billing_page, name="billing_page"),
    path("products/", views.product_list, name="product_list"),
    path("stock/", views.stock_list, name="stock_list"),
    path("stock/remaining/", views.remaining_stock, name="remaining_stock"),
    path("stock/finished/", views.finished_stocks, name="finished_stocks"),
    path("add-stock/", views.add_stock_page, name="add_stock_page"),
    path("daily-reports/", views.daily_reports, name="daily_reports"),
    path("generate-report/", views.generate_today_report, name="generate_today_report"),
    path("bill/<int:bill_id>/", views.bill_detail, name="bill_detail"),
    path("api/create-bill/", views.create_bill_api, name="create_bill_api"),
    path("api/hold-bill/", views.hold_bill_api, name="hold_bill_api"),
    path("api/held-bills/", views.held_bills_api, name="held_bills_api"),
    path("api/hold-details/<int:hold_id>/", views.hold_bill_details, name="hold_bill_details"),
    path("api/recall-bill/<int:hold_id>/", views.recall_bill_api, name="recall_bill_api"),
    path("api/update-hold-bill/<int:hold_id>/", views.update_hold_bill, name="update_hold_bill"),
    path("api/delete-hold-bill/<int:hold_id>/", views.delete_hold_bill_api, name="delete_hold_bill_api"),
    path("api/products/", views.products_api, name="products_api"),
    path("api/remaining-stock/", views.remaining_stock_api, name="remaining_stock_api"),
    path("api/finished-stock/", views.finished_stock_api, name="finished_stock_api"),
    path("api/daily-report/", views.daily_report_api, name="daily_report_api"),
    path("api/search-hold-bill/", views.search_hold_bill_api, name="search_hold_bill_api"),
    path("daily-reports/day/<slug:report_date>/", views.daily_report_day, name="daily_report_day"),
    path("monthly-reports/<int:year>/<int:month>/", views.monthly_report, name="monthly_report"),
]
