from django.db import models
from django.shortcuts import render
from products.models import Product

class Stock(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"

class StockEntry(models.Model):

    ENTRY_TYPE = (
        ("OPENING", "Opening Stock"),
        ("PURCHASE", "Purchase"),
        ("ADJUSTMENT", "Adjustment"),
        ("SALE", "Sale"),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE)

    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.product.name} - {self.entry_type} - {self.quantity}"

