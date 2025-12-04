from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from django.db.models import Sum, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import (
    SessionType,
    SessionProduct,
    Product,
    Order,
    OrderItem,
    ProductCategory,
)

CART_SESSION_KEY = "pos_cart"


# Create your views here.
def _get_cart(request):
    cart = request.session.get(CART_SESSION_KEY)
    if not cart:
        cart = {"session_type_id": None, "items": {}}
        request.session[CART_SESSION_KEY] = cart
    return cart


def _save_cart(request, cart):
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def _cart_summary(cart):
    total = Decimal("0")
    item_count = 0

    for item in cart["items"].values():
        price = Decimal(item["price"])
        qty = int(item["quantity"])
        total += price * qty
        item_count += qty

    return {
        "total": f"{total:.2f}",
        "item_count": item_count,
    }


@login_required
def dashboard_view(request):
    cart = _get_cart(request)

    session_types = (
        SessionType.objects.filter(is_active=True)
        .order_by("sort_order", "name")
    )

    # Determine current session type
    session_type_id_param = request.GET.get("session_type")
    if session_type_id_param:
        try:
            session_type_id = int(session_type_id_param)
        except ValueError:
            session_type_id = None
    else:
        # default to first active session type if None
        session_type_id = cart.get("session_type_id") or (
            session_types.first().id if session_types else None
        )

    current_session_type = None
    if session_type_id:
        current_session_type = SessionType.objects.filter(
            id=session_type_id,
            is_active=True,
        ).first()

    # Clear cart on session change
    if current_session_type:
        if cart.get("session_type_id") != current_session_type.id:
            cart = {
                "session_type_id": current_session_type.id,
                "items": {},
            }
            _save_cart(request, cart)
        elif cart.get("session_type_id") is None:
            cart["session_type_id"] = current_session_type.id
            _save_cart(request, cart)

    event_products = []
    addon_products = []
    merch_products = []

    if current_session_type:
        session_products_qs = (
            SessionProduct.objects
            .select_related("product")
            .filter(
                session_type=current_session_type,
                is_active=True,
                product__is_active=True,
                product__show_on_dashboard=True,
            )
            .order_by("product__category", "product__name")
        )

        for sp in session_products_qs:
            category = sp.product.category
            if category in (ProductCategory.ADMISSION, ProductCategory.HIRE):
                event_products.append(sp)
            elif category == ProductCategory.ADDON:
                addon_products.append(sp)
            elif category == ProductCategory.MERCH:
                merch_products.append(sp)

    summary = _cart_summary(cart)

    context = {
        "session_types": session_types,
        "current_session_type": current_session_type,
        "event_products": event_products,
        "addon_products": addon_products,
        "merch_products": merch_products,
        "cart": cart,
        "cart_summary": summary,
    }

    return render(request, "dashboard/dashboard.html", context)


@require_POST
@login_required
def cart_add(request):
    cart = _get_cart(request)
    session_type_id = cart.get("session_type_id")

    if not session_type_id:
        return HttpResponseBadRequest("No session type selected")

    product_id = request.POST.get("product_id")
    if not product_id:
        return HttpResponseBadRequest("Missing product_id")

    try:
        qty = int(request.POST.get("quantity", 1))
    except ValueError:
        return HttpResponseBadRequest("Invalid quantity")

    if qty <= 0:
        qty = 1

    session_type = get_object_or_404(
        SessionType,
        id=session_type_id,
        is_active=True,
    )

    session_product = get_object_or_404(
        SessionProduct.objects.select_related("product"),
        session_type=session_type,
        product_id=product_id,
        is_active=True,
        product__is_active=True,
        product__show_on_dashboard=True,
    )
    product = session_product.product

    key = str(product.id)
    item = cart["items"].get(key)
    if item:
        item["quantity"] += qty
    else:
        cart["items"][key] = {
            "product_id": product.id,
            "name": product.name,
            "price": str(session_product.price),
            "quantity": qty,
        }

    _save_cart(request, cart)
    summary = _cart_summary(cart)
    return JsonResponse({"cart": cart, "summary": summary})


@require_POST
@login_required
def cart_update(request):
    cart = _get_cart(request)

    product_id = request.POST.get("product_id")
    if not product_id:
        return HttpResponseBadRequest("Missing product_id")

    key = str(product_id)
    if key not in cart["items"]:
        return HttpResponseBadRequest("Product not in cart")

    try:
        qty = int(request.POST.get("quantity", 1))
    except ValueError:
        return HttpResponseBadRequest("Invalid quantity")

    if qty <= 0:
        del cart["items"][key]
    else:
        cart["items"][key]["quantity"] = qty

    _save_cart(request, cart)
    summary = _cart_summary(cart)
    return JsonResponse({"cart": cart, "summary": summary})


@require_POST
@login_required
def cart_clear(request):
    cart = _get_cart(request)
    cart["items"] = {}
    _save_cart(request, cart)

    summary = _cart_summary(cart)
    return JsonResponse({"cart": cart, "summary": summary})


@require_POST
@login_required
def cart_checkout(request):
    cart = _get_cart(request)
    session_type_id = cart.get("session_type_id")

    if not session_type_id:
        return HttpResponseBadRequest("No session type selected")
    if not cart["items"]:
        return HttpResponseBadRequest("Cart is empty")

    session_type = get_object_or_404(
        SessionType,
        id=session_type_id,
        is_active=True,
    )

    with transaction.atomic():
        total = Decimal("0")
        order = Order.objects.create(
            session_type=session_type,
            user=request.user,
            total=Decimal("0"),  # temporary
        )

        for item in cart["items"].values():
            price = Decimal(item["price"])
            qty = int(item["quantity"])
            line_total = price * qty
            total += line_total

            product = get_object_or_404(Product, id=item["product_id"])

            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=item["name"],
                unit_price=price,
                quantity=qty,
                line_total=line_total,
            )

        order.total = total
        order.save(update_fields=["total"])

    # Clear cart
    cart["items"] = {}
    _save_cart(request, cart)
    summary = _cart_summary(cart)

    return JsonResponse(
        {
            "order_id": order.id,
            "summary": summary,
        }
    )


@login_required
def financials_view(request):
    # date filter
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    orders = Order.objects.all()

    if start_date_str:
        try:
            start_date = timezone.datetime.fromisoformat(start_date_str).date()
            orders = orders.filter(created_at__date__gte=start_date)
        except ValueError:
            start_date = None
    else:
        start_date = None

    if end_date_str:
        try:
            end_date = timezone.datetime.fromisoformat(end_date_str).date()
            orders = orders.filter(created_at__date__lte=end_date)
        except ValueError:
            end_date = None
    else:
        end_date = None

    # totals
    overall = orders.aggregate(total_revenue=Sum("total"))
    overall_total = overall["total_revenue"] or 0

    # Revenue per day
    revenue_by_day = (
        orders.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total"))
        .order_by("day")
    )

    # Revenue per session type
    revenue_by_session_type = (
        orders.values("session_type__id", "session_type__name")
        .annotate(total=Sum("total"))
        .order_by("session_type__name")
    )

    # Revenue per product category (via OrderItem)
    items = OrderItem.objects.filter(order__in=orders)
    revenue_by_category = (
        items.values("product__category")
        .annotate(total=Sum("line_total"))
        .order_by("product__category")
    )

    context = {
        "overall_total": overall_total,
        "revenue_by_day": revenue_by_day,
        "revenue_by_session_type": revenue_by_session_type,
        "revenue_by_category": revenue_by_category,
        "start_date": start_date_str or "",
        "end_date": end_date_str or "",
    }
    return render(request, "dashboard/financials.html", context)
