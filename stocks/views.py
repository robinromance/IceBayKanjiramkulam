from django.shortcuts import render, redirect
from .models import Stock, StockEntry
from products.models import Product
from django.db.models import Sum

def stock_list(request):
    stocks = Stock.objects.select_related("product").all()

    return render(request, "stocks/stock_list.html", {
        "stocks": stocks
    })

from django.db.models import F

def remaining_stock(request):
    stocks = (
        Stock.objects
        .select_related("product")
        .filter(quantity__gt=0)
        .order_by('-quantity')   # DESCENDING ✔
    )

    return render(request, "stocks/stock_list.html", {
        "stocks": stocks,
        "page_title": "Remaining Stock"
    })


# View for items that are OUT of stock
def finished_stocks(request):
    stocks = (
        Stock.objects
        .select_related("product")
        .filter(quantity__lte=0)
        .order_by('product__name')
    )

    return render(request, "stocks/stock_list.html", {
        "stocks": stocks,
        "page_title": "Finished Stock"
    })


def add_stock(request):
    if request.method == "POST":
        product_id = request.POST.get("product")
        quantity = int(request.POST.get("quantity"))
        entry_type = request.POST.get("entry_type")

        product = Product.objects.get(id=product_id)

        stock, created = Stock.objects.get_or_create(product=product)
        stock.quantity += quantity
        stock.save()

        StockEntry.objects.create(
            product=product,
            entry_type=entry_type,
            quantity=quantity,
            note="Manual stock entry"
        )

        return redirect("stock_list")

    products = Product.objects.all()
    return render(request, "stocks/add_stock.html", {
        "products": products
    })

def add_opening_stock(product, qty):

    stock, _ = Stock.objects.get_or_create(product=product)
    stock.quantity += qty
    stock.save()

    StockEntry.objects.create(
        product=product,
        entry_type="OPENING",
        quantity=qty,
        note="Morning opening stock"
    )

def add_purchase_stock(product, qty, supplier_name=""):

    stock = Stock.objects.get(product=product)
    stock.quantity += qty
    stock.save()

    StockEntry.objects.create(
        product=product,
        entry_type="PURCHASE",
        quantity=qty,
        note=f"Supplier: {supplier_name}"
    )

