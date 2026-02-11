from django.shortcuts import render
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from products.models import Product
from stocks.models import Stock, StockEntry
from billings.models import Bill, BillItem
from reports.models import DailyReport, DailyProductReport
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from products.models import Product
from stocks.models import Stock

def remaining_stock(request):
    # Show products with stock > 0
    products_in_stock = Product.objects.filter(stock__quantity__gt=0)
    return render(request, "billings/remaining_stock.html", {"products": products_in_stock})

def finished_stocks(request):
    # Show products with stock = 0
    finished_products = Product.objects.filter(stock__quantity=0)
    return render(request, "billings/finished_stocks.html", {"products": finished_products})

def billing_page(request):
    """
    Display all products for billing page.
    - Annotates each product with current stock quantity.
    - Calculates total sold quantity from BillItem.
    - Orders products by most-selling first.
    """
    products = Product.objects.annotate(
        stock_quantity=F("stock__quantity"),
        total_sold=Coalesce(Sum("billitem__quantity"), 0)  # 0 if no sales yet
    ).order_by("-total_sold", "name")  # most-selling first, then alphabetically

    context = {
        "products": products
    }

    return render(request, "billings/billing_page.html", context)


def reduce_stock(product, qty, bill):
    stock = Stock.objects.get(product=product)

    if stock.quantity < qty:
        raise Exception(f"Not enough stock for {product.name}")

    stock.quantity -= qty
    stock.save()

    StockEntry.objects.create(
        product=product,
        entry_type="SALE",
        quantity=qty,
        note=f"Bill No: {bill.bill_no}"
    )

@transaction.atomic
def create_bill(cart_data):

    bill = Bill.objects.create(
        bill_no=f"BILL-{Bill.objects.count() + 1}",
        total_amount=0
    )

    total_amount = Decimal("0.00")
    today = timezone.now().date()

    daily_report, _ = DailyReport.objects.get_or_create(date=today)

    for item in cart_data:
        product = Product.objects.get(id=item["product_id"])
        qty = int(item["qty"])

        # ✅ CREATE BILL ITEM
        BillItem.objects.create(
            bill=bill,
            product=product,
            quantity=qty,
            price=product.price
        )

        # ✅ REDUCE STOCK
        reduce_stock(product, qty, bill)

        # ✅ DAILY PRODUCT REPORT
        daily_product, _ = DailyProductReport.objects.get_or_create(
            date=today,
            product=product
        )

        daily_product.quantity_sold += qty
        daily_product.total_sales += product.price * qty
        daily_product.save()

        # ✅ DAILY TOTAL REPORT
        daily_report.total_items_sold += qty
        daily_report.total_sales += product.price * qty

        total_amount += product.price * qty

    daily_report.save()

    bill.total_amount = total_amount
    bill.save()

    return bill

@csrf_exempt
def create_bill_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            cart_data = data.get("cart", [])
            if not cart_data:
                return JsonResponse({"success": False, "error": "Cart is empty"})

            bill = create_bill(cart_data)
            return JsonResponse({
                "success": True,
                "bill_no": bill.bill_no,
                "total_amount": str(bill.total_amount)
            })
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request method"})