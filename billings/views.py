from decimal import Decimal
import json

from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from products.models import Product
from stocks.models import Stock, StockEntry
from billings.models import Bill, BillItem
from reports.models import DailyReport, DailyProductReport


# =====================================================
# BILLING PAGE
# =====================================================

def billing_page(request):

    products = Product.objects.annotate(
        stock_quantity=F("stock__quantity"),
        total_sold=Coalesce(Sum("bill_items__quantity"), 0)
    ).order_by("-total_sold", "name")

    return render(
        request,
        "billings/billing_page.html",
        {
            "products": products
        }
    )


# =====================================================
# REMAINING STOCK PAGE
# =====================================================

def remaining_stock(request):

    products = Product.objects.filter(
        stock__quantity__gt=0
    )

    return render(
        request,
        "billings/remaining_stock.html",
        {
            "products": products
        }
    )


# =====================================================
# FINISHED STOCK PAGE
# =====================================================

def finished_stocks(request):

    products = Product.objects.filter(
        stock__quantity=0
    )

    return render(
        request,
        "billings/finished_stocks.html",
        {
            "products": products
        }
    )


# =====================================================
# REDUCE STOCK
# =====================================================

def reduce_stock(product, qty, bill):

    stock = Stock.objects.get(product=product)

    qty = int(qty)

    if qty <= 0:

        raise Exception(
            "Invalid quantity"
        )

    if stock.quantity < qty:

        raise Exception(
            f"Only {stock.quantity} stock left for {product.name}"
        )

    stock.quantity -= qty

    stock.save()

    StockEntry.objects.create(

        product=product,

        entry_type="SALE",

        quantity=qty,

        note=f"Bill No: {bill.bill_no}"

    )

# =====================================================
# CREATE BILL
# =====================================================

@transaction.atomic
def create_bill(cart_data):

    # CREATE MAIN BILL
    bill = Bill.objects.create(
        bill_no=f"BILL-{Bill.objects.count() + 1}",
        total_amount=0
    )

    grand_total = Decimal("0.00")

    today = timezone.now().date()

    # DAILY REPORT
    daily_report, _ = DailyReport.objects.get_or_create(
        date=today
    )

    # ============================================
    # LOOP THROUGH CART ITEMS
    # ============================================

    for item in cart_data:

        product = Product.objects.get(
            id=item["product_id"]
        )

        qty = int(item["qty"])

        line_total = product.price * qty

        # =====================================
        # CREATE BILL ITEM
        # =====================================

        BillItem.objects.create(
            bill=bill,
            product=product,
            quantity=qty,
            price=product.price,
            total=line_total
        )

        # =====================================
        # REDUCE STOCK
        # =====================================

        reduce_stock(product, qty, bill)

        # =====================================
        # DAILY PRODUCT REPORT
        # =====================================

        daily_product, _ = DailyProductReport.objects.get_or_create(
            date=today,
            product=product
        )

        daily_product.quantity_sold += qty
        daily_product.total_sales += line_total
        daily_product.save()

        # =====================================
        # DAILY TOTAL REPORT
        # =====================================

        daily_report.total_items_sold += qty
        daily_report.total_sales += line_total

        grand_total += line_total

    # SAVE DAILY REPORT
    daily_report.save()

    # UPDATE BILL TOTAL
    bill.total_amount = grand_total
    bill.save()

    return bill


# =====================================================
# CREATE BILL API
# =====================================================

@csrf_exempt
def create_bill_api(request):

    if request.method != "POST":

        return JsonResponse({
            "success": False,
            "error": "Invalid request method"
        })

    try:

        data = json.loads(request.body)

        cart_data = data.get("cart", [])

        if not cart_data:

            return JsonResponse({
                "success": False,
                "error": "Cart is empty"
            })

        bill = create_bill(cart_data)

        return JsonResponse({

            "success": True,

            "bill_id": bill.id,

            "bill_no": bill.bill_no,

            "total_amount": str(
                bill.total_amount
            )

        })

    except Exception as e:

        return JsonResponse({
            "success": False,
            "error": str(e)
        })