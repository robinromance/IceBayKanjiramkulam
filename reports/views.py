from django.utils import timezone
from django.shortcuts import render, redirect
from .utils import generate_daily_stock_report
from django.utils import timezone
from django.db.models import Sum
from billings.models import BillItem
from django.utils import timezone
from django.db.models import Sum, F

def generate_today_report(request):
    generate_daily_stock_report()
    return redirect("daily_reports")

def daily_reports(request):
    today = timezone.now().date()
    
    # Get items sold today, grouped by product name
    product_sales = BillItem.objects.filter(bill__created_at__date=today).values(
        'product__name'
    ).annotate(
        total_qty=Sum('quantity'),
        # Changed 'price_at_billing' to 'price'
        total_price=Sum(F('quantity') * F('price')) 
    ).order_by('-total_qty')

    # Calculate Grand Total
    grand_total = product_sales.aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    return render(request, 'reports/daily_reports.html', {
        'product_sales': product_sales,
        'grand_total': grand_total,
        'today': today
    })