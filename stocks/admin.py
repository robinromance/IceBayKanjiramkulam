from django.contrib import admin
from .models import Stock, StockEntry

admin.site.register(Stock)
admin.site.register(StockEntry)

