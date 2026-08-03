from django.contrib import admin
from .models import (
    Product,
    Stock,
    StockEntry,
    Bill,
    BillItem,
    HoldBill,
    HoldBillItem,
    DailyReport,
    DailyProductReport,
    DailyStockReport,
)

admin.site.register(Product)
admin.site.register(Stock)
admin.site.register(StockEntry)
admin.site.register(Bill)
admin.site.register(BillItem)
admin.site.register(HoldBill)
admin.site.register(HoldBillItem)
admin.site.register(DailyReport)
admin.site.register(DailyProductReport)
admin.site.register(DailyStockReport)
