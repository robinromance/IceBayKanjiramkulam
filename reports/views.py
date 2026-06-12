from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Sum

from .utils import generate_daily_stock_report
from billings.models import Bill, BillItem


# =====================================================
# GENERATE STOCK REPORT
# =====================================================

def generate_today_report(request):
    generate_daily_stock_report()
    return redirect("daily_reports")


# =====================================================
# DAILY BILL REPORTS
# =====================================================

def daily_reports(request):

    today = timezone.now().date()

    # FETCH TODAY'S BILLS
    bills = Bill.objects.filter(
        created_at__date=today
    ).order_by("-created_at")

    # PRODUCT-WISE SALES SUMMARY  ← this was missing
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

    # GRAND TOTAL OF ALL BILLS
    grand_total = bills.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    context = {
        "today": today,
        "bills": bills,
        "product_sales": product_sales,  # ← was missing from context
        "grand_total": grand_total,
    }

    return render(
        request,
        "reports/daily_reports.html",
        context
    )


# =====================================================
# BILL DETAIL PAGE
# =====================================================

def bill_detail(request, bill_id):

    bill = get_object_or_404(Bill, id=bill_id)

    items = BillItem.objects.filter(bill=bill)

    context = {
        "bill": bill,
        "items": items,
    }

    return render(
        request,
        "reports/bill_details.html",
        context
    )