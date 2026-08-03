from decimal import Decimal
import json
from django.db import transaction
from datetime import datetime
from django.db.models import F, Sum, Count, Value, DecimalField
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

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


# ═══════════════════════════════════════════════════════════
# BILLING PAGE (Main Dashboard)
# ═══════════════════════════════════════════════════════════

def billing_page(request):
    """Display main billing/POS dashboard with product list"""
    
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

def product_list(request):
    products = Product.objects.filter(is_active=True)
    query = request.GET.get("q", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    category = request.GET.get("category", "all")
    sort = request.GET.get("sort", "name")

    if query:
        products = products.filter(name__icontains=query)

    if category == "other":
        products = products.filter(category__exact="")
    elif category != "all":
        products = products.filter(category__iexact=category)

    if min_price.isdigit():
        products = products.filter(price__gte=int(min_price))

    if max_price.isdigit():
        products = products.filter(price__lte=int(max_price))

    if sort == "price_desc":
        products = products.order_by("-price")
    elif sort == "price_asc":
        products = products.order_by("price")
    else:
        products = products.order_by("name")

    categories = Product.objects.filter(is_active=True).values_list("category", flat=True).distinct()
    category_options = [cat for cat in categories if cat]

    return render(request, "products/product_list.html", {
        "products": products,
        "search_query": query,
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort,
        "category": category,
        "category_options": category_options,
    })


def build_stock_context(stocks, page_title):
    total_quantity = stocks.aggregate(total=Coalesce(Sum("quantity"), 0))["total"] or 0
    total_stock_value = stocks.aggregate(
        value=Coalesce(Sum(F("quantity") * F("product__price")), 0)
    )["value"] or 0
    low_stock_count = stocks.filter(quantity__gt=5, quantity__lte=10).count()
    critical_stock_count = stocks.filter(quantity__lte=5).count()

    return {
        "stocks": stocks,
        "page_title": page_title,
        "total_quantity": total_quantity,
        "total_stock_value": total_stock_value,
        "low_stock_count": low_stock_count,
        "critical_stock_count": critical_stock_count,
    }


def stock_list(request):
    stocks = Stock.objects.select_related("product").all()
    return render(
        request,
        "stocks/stock_list.html",
        build_stock_context(stocks, "Stock Report"),
    )


def remaining_stock(request):
    stocks = (
        Stock.objects
        .select_related("product")
        .filter(quantity__gt=0)
        .order_by("-quantity")
    )

    return render(
        request,
        "stocks/stock_list.html",
        build_stock_context(stocks, "Remaining Stock"),
    )


def finished_stocks(request):
    stocks = (
        Stock.objects
        .select_related("product")
        .filter(quantity__lte=0)
        .order_by("product__name")
    )

    return render(
        request,
        "stocks/stock_list.html",
        build_stock_context(stocks, "Finished Stock"),
    )


def add_stock_page(request):
    if request.method == "POST":
        product_id = request.POST.get("product")
        quantity = int(request.POST.get("quantity"))
        entry_type = request.POST.get("entry_type")
        note = request.POST.get("note")

        product = Product.objects.get(id=product_id)
        stock, _ = Stock.objects.get_or_create(product=product)
        stock.quantity += quantity
        stock.save()

        StockEntry.objects.create(
            product=product,
            entry_type=entry_type,
            quantity=quantity,
            note=note,
        )

        return redirect("add_stock_page")

    products = Product.objects.all().order_by("name")
    return render(request, "stocks/add_stock.html", {
        "products": products,
    })

# ═══════════════════════════════════════════════════════════
# REDUCE STOCK (Helper Function)
# ═══════════════════════════════════════════════════════════

def reduce_stock(product, qty, bill):
    """
    Reduce product stock after sale and create stock entry.
    
    Args:
        product: Product instance
        qty: Quantity to reduce
        bill: Bill instance (for reference)
    
    Raises:
        Exception: If quantity invalid or insufficient stock
    """
    
    stock = Stock.objects.get(product=product)
    qty = int(qty)

    if qty <= 0:
        raise Exception("Invalid quantity")

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


# ═══════════════════════════════════════════════════════════
# CREATE BILL (Helper Function)
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def create_bill(cart_data, customer_name="Walk-in Customer", hold_id=None):
    """
    Create a final bill from cart data.
    
    Args:
        cart_data: List of dicts [{product_id, qty}, ...]
        customer_name: Customer name (default: Walk-in Customer)
        hold_id: If recalling from held bill (optional)
    
    Returns:
        Bill instance
    """
    
    bill = Bill.objects.create(
        bill_no=f"BILL-{Bill.objects.count() + 1:04d}",
        customer_name=customer_name,
        total_amount=0,
        grand_total=0
    )

    grand_total = Decimal("0.00")
    today = timezone.localdate()

    # Get or create daily report for today
    daily_report, _ = DailyReport.objects.get_or_create(date=today)

    # ─────────────────────────────────────
    # PROCESS EACH CART ITEM
    # ─────────────────────────────────────
    
    for item in cart_data:
        product = Product.objects.get(id=item["product_id"])
        qty = int(item["qty"])
        line_total = product.price * qty

        # Create Bill Item
        BillItem.objects.create(
            bill=bill,
            product=product,
            quantity=qty,
            price=product.price,
            total=line_total
        )

        # Reduce Stock
        reduce_stock(product, qty, bill)

        # Update Daily Product Report
        daily_product, _ = DailyProductReport.objects.get_or_create(
            date=today,
            product=product
        )
        daily_product.quantity_sold += qty
        daily_product.total_sales += line_total
        daily_product.save()

        # Update Daily Report Totals
        daily_report.total_items_sold += qty
        daily_report.total_sales += line_total

        grand_total += line_total

    # Save daily report
    daily_report.save()

    # Update bill totals
    bill.total_amount = grand_total
    bill.grand_total = grand_total
    bill.save()

    # Delete Hold Bill after successful payment
    if hold_id:
        try:
            HoldBill.objects.get(id=hold_id).delete()
        except HoldBill.DoesNotExist:
            pass

    return bill


# ═══════════════════════════════════════════════════════════
# CREATE BILL API
# ═══════════════════════════════════════════════════════════

@csrf_exempt
def create_bill_api(request):
    """
    API endpoint to create a final bill.
    
    POST JSON:
    {
        "customer_name": "John Doe",
        "cart": [
            {"product_id": 1, "qty": 2},
            {"product_id": 2, "qty": 1}
        ],
        "hold_id": null  // Optional: if recalling from held bill
    }
    """
    
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Invalid request method"
        })

    try:
        data = json.loads(request.body)
        cart_data = data.get("cart", [])
        customer_name = data.get("customer_name", "Walk-in Customer")
        hold_id = data.get("hold_id")

        if not cart_data:
            return JsonResponse({
                "success": False,
                "error": "Cart is empty"
            })

        bill = create_bill(cart_data, customer_name, hold_id)

        return JsonResponse({
            "success": True,
            "bill_id": bill.id,
            "bill_no": bill.bill_no,
            "customer_name": bill.customer_name,
            "total_amount": str(bill.total_amount)
        })

    except Product.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Product not found"
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })


# ═══════════════════════════════════════════════════════════
# GENERATE HOLD NUMBER (Helper Function)
# ═══════════════════════════════════════════════════════════

def generate_hold_number():
    """Generate next hold bill number (HB0001, HB0002, etc.)"""
    
    last = HoldBill.objects.order_by("-id").first()

    if not last:
        return "HB0001"

    number = int(last.hold_number.replace("HB", ""))
    return f"HB{number + 1:04d}"


# ═══════════════════════════════════════════════════════════
# HOLD BILL API
# ═══════════════════════════════════════════════════════════

@csrf_exempt
def hold_bill_api(request):
    """
    API endpoint to hold a bill for later.
    
    POST JSON:
    {
        "customer_name": "John Doe",
        "cart": {
            "1": 2,
            "2": 1
        }
    }
    """
    
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Invalid request method"
        })

    try:
        data = json.loads(request.body)
        customer_name = data.get("customer_name", "Walk-in Customer")
        cart = data.get("cart", {})

        if not cart:
            return JsonResponse({
                "success": False,
                "error": "Cart is empty"
            })

        # Create Hold Bill
        hold = HoldBill.objects.create(
            hold_number=generate_hold_number(),
            customer_name=customer_name,
            grand_total=Decimal("0.00")
        )

        total = Decimal("0.00")

        # ─────────────────────────────────────
        # PROCESS CART ITEMS (Object Format)
        # {product_id: qty, ...}
        # ─────────────────────────────────────
        
        for product_id, qty in cart.items():
            product = Product.objects.get(id=product_id)
            qty = int(qty)
            line_total = product.price * qty

            HoldBillItem.objects.create(
                hold_bill=hold,
                product=product,
                quantity=qty,
                price=product.price,
                total=line_total
            )

            total += line_total

        hold.grand_total = total
        hold.save()

        return JsonResponse({
            "success": True,
            "hold_id": hold.id,
            "hold_number": hold.hold_number
        })

    except Product.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Product not found"
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })


# ═══════════════════════════════════════════════════════════
# LIST HELD BILLS
# ═══════════════════════════════════════════════════════════

def held_bills_api(request):
    """
    Get list of all held bills.
    
    GET /held-bills/
    """
    
    data = []
    bills = HoldBill.objects.order_by("-created_at")

    for bill in bills:
        data.append({
            "id": bill.id,
            "hold_number": bill.hold_number,
            "customer_name": bill.customer_name,
            "grand_total": float(bill.grand_total),
            "items": bill.items.count(),
            "date": bill.created_at.strftime("%d-%m-%Y %I:%M %p")
        })

    return JsonResponse({
        "success": True,
        "bills": data
    })


# ═══════════════════════════════════════════════════════════
# RECALL HOLD BILL
# ═══════════════════════════════════════════════════════════

def recall_bill_api(request, hold_id):
    """
    Recall a held bill to cart.
    
    GET /recall-bill/<hold_id>/
    """
    
    try:
        hold = HoldBill.objects.get(id=hold_id)
    except HoldBill.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Hold Bill not found"
        })

    cart = []

    for item in hold.items.all():
        cart.append({
            "product_id": item.product.id,
            "name": item.product.name,
            "qty": item.quantity,
            "price": float(item.price)
        })

    return JsonResponse({
        "success": True,
        "customer_name": hold.customer_name,
        "hold_number": hold.hold_number,
        "cart": cart
    })


# ═══════════════════════════════════════════════════════════
# DELETE HOLD BILL
# ═══════════════════════════════════════════════════════════

@csrf_exempt
def delete_hold_bill_api(request, hold_id):
    """
    Delete a held bill.
    
    POST /delete-hold-bill/<hold_id>/
    """
    
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Invalid request method"
        })

    try:
        hold = HoldBill.objects.get(id=hold_id)
        hold.delete()

        return JsonResponse({
            "success": True
        })

    except HoldBill.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Hold Bill not found"
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })


def products_api(request):
    """Return active product list with stock quantity."""
    products = Product.objects.filter(is_active=True).select_related('stock')
    data = []

    for product in products:
        stock_quantity = 0
        if hasattr(product, 'stock') and product.stock is not None:
            stock_quantity = product.stock.quantity

        data.append({
            'id': product.id,
            'name': product.name,
            'category': product.category,
            'price': float(product.price),
            'stock_quantity': stock_quantity,
        })

    return JsonResponse({
        'success': True,
        'products': data,
    })


def remaining_stock_api(request):
    """Return active products with remaining stock."""
    products = Product.objects.filter(is_active=True, stock__quantity__gt=0).select_related('stock')
    data = []

    for product in products:
        data.append({
            'id': product.id,
            'name': product.name,
            'category': product.category,
            'price': float(product.price),
            'stock_quantity': product.stock.quantity,
        })

    return JsonResponse({
        'success': True,
        'products': data,
    })


def finished_stock_api(request):
    """Return active products with zero or negative stock."""
    products = Product.objects.filter(is_active=True, stock__quantity__lte=0).select_related('stock')
    data = []

    for product in products:
        data.append({
            'id': product.id,
            'name': product.name,
            'category': product.category,
            'price': float(product.price),
            'stock_quantity': product.stock.quantity,
        })

    return JsonResponse({
        'success': True,
        'products': data,
    })


def daily_report_api(request):
    """Return daily sales summary with product breakdown."""
    summaries = []

    for report in DailyReport.objects.order_by('-date'):
        items = []
        for item in DailyProductReport.objects.filter(date=report.date).select_related('product'):
            items.append({
                'product_id': item.product.id,
                'name': item.product.name,
                'quantity_sold': item.quantity_sold,
                'total_sales': float(item.total_sales),
            })

        summaries.append({
            'date': report.date.isoformat(),
            'total_sales': float(report.total_sales),
            'total_items_sold': report.total_items_sold,
            'products': items,
        })

    return JsonResponse({
        'success': True,
        'reports': summaries,
    })


# ═══════════════════════════════════════════════════════════
# SEARCH HOLD BILL
# ═══════════════════════════════════════════════════

def search_hold_bill_api(request):
    """
    Search held bills by customer name.
    
    GET /search-hold-bill/?q=john
    """
    
    keyword = request.GET.get("q", "").strip()

    bills = HoldBill.objects.filter(
        customer_name__icontains=keyword
    ).order_by("-created_at")

    result = []

    for bill in bills:
        result.append({
            "id": bill.id,
            "hold_number": bill.hold_number,
            "customer_name": bill.customer_name,
            "grand_total": float(bill.grand_total),
            "items": bill.items.count(),
            "date": bill.created_at.strftime("%d-%m-%Y %I:%M %p")
        })

    return JsonResponse({
        "success": True,
        "bills": result
    })


# ═══════════════════════════════════════════════════════════
# HOLD BILL DETAILS (Optional - for viewing details)
# ═══════════════════════════════════════════════════════════

def hold_bill_details(request, hold_id):
    """
    Get detailed information of a held bill.
    
    GET /hold-details/<hold_id>/
    """
    
    try:
        hold = HoldBill.objects.get(id=hold_id)
    except HoldBill.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Hold Bill not found"
        })

    items = []

    for item in hold.items.select_related("product"):
        items.append({
            "product_id": item.product.id,
            "product_name": item.product.name,
            "price": float(item.price),
            "qty": item.quantity,
            "total": float(item.total)
        })

    return JsonResponse({
        "success": True,
        "hold_id": hold.id,
        "hold_number": hold.hold_number,
        "customer_name": hold.customer_name,
        "grand_total": float(hold.grand_total),
        "items": items
    })


# ═══════════════════════════════════════════════════════════
# UPDATE HOLD BILL (Optional - for editing held bills)
# ═══════════════════════════════════════════════════════════

@csrf_exempt
def update_hold_bill(request, hold_id):
    """
    Update a held bill's customer name and items.
    
    POST /update-hold-bill/<hold_id>/
    
    JSON:
    {
        "customer_name": "Jane Doe",
        "cart": [
            {"product_id": 1, "qty": 3}
        ]
    }
    """
    
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Invalid request method"
        })

    try:
        hold = HoldBill.objects.get(id=hold_id)
    except HoldBill.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Hold Bill not found"
        })

    try:
        data = json.loads(request.body)
        customer_name = data.get("customer_name", "Walk-in Customer")
        cart = data.get("cart", [])

        hold.customer_name = customer_name

        # Delete old items
        hold.items.all().delete()

        grand_total = Decimal("0.00")

        # Add new items
        for item in cart:
            product = Product.objects.get(id=item["product_id"])
            qty = int(item["qty"])
            total = product.price * qty

            HoldBillItem.objects.create(
                hold_bill=hold,
                product=product,
                quantity=qty,
                price=product.price,
                total=total
            )

            grand_total += total

        hold.grand_total = grand_total
        hold.save()

        return JsonResponse({
            "success": True,
            "message": "Hold Bill updated successfully"
        })

    except Product.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Product not found"
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })


# ═══════════════════════════════════════════════════════════════════
# GENERATE STOCK REPORT
# ═══════════════════════════════════════════════════════════════════


def generate_daily_stock_report():
    today = timezone.localdate()

    for stock in Stock.objects.all():
        opening = StockEntry.objects.filter(
            product=stock.product,
            entry_type="OPENING",
            created_at__date=today
        ).aggregate(total=Sum("quantity"))["total"] or 0

        sold = StockEntry.objects.filter(
            product=stock.product,
            entry_type="SALE",
            created_at__date=today
        ).aggregate(total=Sum("quantity"))["total"] or 0

        DailyStockReport.objects.update_or_create(
            date=today,
            product=stock.product,
            defaults={
                "opening_stock": opening,
                "sold_quantity": sold,
                "closing_stock": stock.quantity,
            }
        )


def generate_today_report(request):
    generate_daily_stock_report()
    return redirect("billings:daily_reports")


def daily_reports(request):
    today = timezone.localdate()

    bills = Bill.objects.filter(
        created_at__date=today
    ).order_by("-created_at")

    product_sales = (
        BillItem.objects
        .filter(bill__created_at__date=today)
        .values("product__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_price=Sum("total")
        )
        .order_by("product__name")
    )

    grand_total = bills.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    # Day-by-day for last 30 days
    from datetime import timedelta
    start_date = today - timedelta(days=29)
    day_qs = (
        Bill.objects
        .filter(created_at__date__gte=start_date)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total_amount=Coalesce(Sum('total_amount'), Value(0), output_field=DecimalField()), bill_count=Count('id'))
        .order_by('-day')
    )

    day_by_day = [
        {
            'date': d['day'],
            'total': d['total_amount'],
            'bills': d['bill_count']
        }
        for d in day_qs
    ]

    # Monthly aggregates for last 12 months
    month_qs = (
        Bill.objects
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total_amount=Coalesce(Sum('total_amount'), Value(0), output_field=DecimalField()), bill_count=Count('id'))
        .order_by('-month')[:12]
    )

    monthly = [
        {
            'month': m['month'],
            'total': m['total_amount'],
            'bills': m['bill_count']
        }
        for m in month_qs
    ]

    return render(request, "reports/daily_reports.html", {
        "today": today,
        "bills": bills,
        "product_sales": product_sales,
        "grand_total": grand_total,
        "day_by_day": day_by_day,
        "monthly": monthly,
    })


def daily_report_day(request, report_date):
    try:
        selected_date = datetime.strptime(report_date, "%Y-%m-%d").date()
    except ValueError:
        return redirect("billings:daily_reports")

    bills = Bill.objects.filter(
        created_at__date=selected_date
    ).order_by("-created_at")

    product_sales = (
        BillItem.objects
        .filter(bill__created_at__date=selected_date)
        .values("product__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_price=Sum("total")
        )
        .order_by("product__name")
    )

    grand_total = bills.aggregate(
        total=Coalesce(Sum("total_amount"), Value(0), output_field=DecimalField())
    )["total"] or 0

    return render(request, "reports/report_detail.html", {
        "title": selected_date.strftime("Daily Report — %d %b %Y"),
        "subtitle": selected_date.strftime("Detailed sales for %d %b %Y"),
        "bills": bills,
        "product_sales": product_sales,
        "grand_total": grand_total,
        "back_url": "billings:daily_reports",
        "back_text": "Back to Daily Reports",
    })


def monthly_report(request, year, month):
    try:
        selected_date = datetime(year, month, 1).date()
    except ValueError:
        return redirect("billings:daily_reports")

    bills = Bill.objects.filter(
        created_at__year=year,
        created_at__month=month
    ).order_by("-created_at")

    product_sales = (
        BillItem.objects
        .filter(bill__created_at__year=year, bill__created_at__month=month)
        .values("product__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_price=Sum("total")
        )
        .order_by("product__name")
    )

    grand_total = bills.aggregate(
        total=Coalesce(Sum("total_amount"), Value(0), output_field=DecimalField())
    )["total"] or 0

    return render(request, "reports/report_detail.html", {
        "title": selected_date.strftime("Monthly Report — %B %Y"),
        "subtitle": selected_date.strftime("Detailed sales for %B %Y"),
        "bills": bills,
        "product_sales": product_sales,
        "grand_total": grand_total,
        "back_url": "billings:daily_reports",
        "back_text": "Back to Daily Reports",
    })


def bill_detail(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    items = BillItem.objects.filter(bill=bill)

    return render(request, "reports/bill_details.html", {
        "bill": bill,
        "items": items,
    })
