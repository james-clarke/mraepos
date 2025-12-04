from django.contrib import admin

admin.site.site_header = "MRA POS Administration & Customization"
admin.site.site_title = "MRA POS Admin"
admin.site.index_title = "Skate Hut Overview"

# Register your models here.
from .models import (
    SessionType,
    Product,
    SessionProduct,
    Order,
    OrderItem,
)

@admin.register(SessionType)
class SessionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "category",
        "is_active",
        "show_on_dashboard",
    )
    list_filter = ("category", "is_active", "show_on_dashboard")
    search_fields = ("name", "sku")


@admin.register(SessionProduct)
class SessionProductAdmin(admin.ModelAdmin):
    list_display = ("session_type", "product", "price", "is_active")
    list_filter = ("session_type", "product__category", "is_active")
    search_fields = ("product__name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product",
        "product_name",
        "unit_price",
        "quantity",
        "line_total",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "session_type", "user", "total")
    list_filter = ("session_type", "user", "created_at")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    readonly_fields = ("created_at",)