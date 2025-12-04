from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("financials/", views.financials_view, name="financials"),
    path("api/cart/add/", views.cart_add, name="cart_add"),
    path("api/cart/update/", views.cart_update, name="cart_update"),
    path("api/cart/clear/", views.cart_clear, name="cart_clear"),
    path("api/cart/checkout/", views.cart_checkout, name="cart_checkout"),
]
