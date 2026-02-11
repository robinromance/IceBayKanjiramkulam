from django.utils import timezone
from django.db.models import Sum

from stocks.models import Stock, StockEntry
from reports.models import DailyStockReport


def generate_daily_stock_report():
    today = timezone.now().date()

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

        # Prevent duplicate daily reports
        report, created = DailyStockReport.objects.update_or_create(
            date=today,
            product=stock.product,
            defaults={
                "opening_stock": opening,
                "sold_quantity": sold,
                "closing_stock": stock.quantity
            }
        )
