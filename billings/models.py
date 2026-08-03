from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=80, blank=True, default="")
    price = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "products_product"

    def __str__(self):
        return self.name


class Stock(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stocks_stock"

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

    class Meta:
        db_table = "stocks_stockentry"

    def __str__(self):
        return f"{self.product.name} - {self.entry_type} - {self.quantity}"


# ==========================
# FINAL PAID BILL
# ==========================

class Bill(models.Model):
    bill_no = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=100, default="Walk-in Customer")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill #{self.bill_no}"


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="bill_items")
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"


# ==========================
# HOLD BILL
# ==========================

class HoldBill(models.Model):
    hold_number = models.CharField(max_length=20, unique=True)
    customer_name = models.CharField(max_length=100, default="Walk-in Customer")
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.hold_number


class HoldBillItem(models.Model):
    hold_bill = models.ForeignKey(HoldBill, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"


class DailyReport(models.Model):
    date = models.DateField(unique=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_items_sold = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reports_dailyreport"


class DailyProductReport(models.Model):
    date = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_sold = models.IntegerField(default=0)
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = "reports_dailyproductreport"


class DailyStockReport(models.Model):
    date = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    opening_stock = models.IntegerField(default=0)
    sold_quantity = models.IntegerField(default=0)
    closing_stock = models.IntegerField(default=0)

    class Meta:
        db_table = "reports_dailystockreport"
    