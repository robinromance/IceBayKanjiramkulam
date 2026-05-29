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

    # GRAND TOTAL OF ALL BILLS
    grand_total = bills.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    context = {

        "today": today,

        "bills": bills,

        "grand_total": grand_total

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

    bill = get_object_or_404(
        Bill,
        id=bill_id
    )
    print(bill)
    items = BillItem.objects.filter(
        bill=bill
    )

    context = {

        "bill": bill,

        "items": items

    }
    print(items)
    return render(
        request,
        "reports/bill_details.html",
        context
    )