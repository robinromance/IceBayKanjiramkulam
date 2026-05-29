from django.db import models
from products.models import Product

# Create your models here.

class DailyReport(models.Model):
    date = models.DateField(unique=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_items_sold = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

class DailyProductReport(models.Model):
    date = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    quantity_sold = models.IntegerField(default=0)
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    

class DailyStockReport(models.Model):
    date = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    opening_stock = models.IntegerField(default=0)
    sold_quantity = models.IntegerField(default=0)
    closing_stock = models.IntegerField(default=0)
