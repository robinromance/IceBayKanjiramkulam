from django.contrib import admin
from .models import DailyReport, DailyProductReport, DailyStockReport

admin.site.register(DailyReport)
admin.site.register(DailyProductReport)
admin.site.register(DailyStockReport)

