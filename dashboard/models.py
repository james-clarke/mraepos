from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# Create your models here.
class SessionType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class ProductCategory(models.TextChoices):
    ADMISSION = "ADMISSION", "Admission"
    HIRE = "HIRE", "Hire"
    ADDON = "ADDON", "Add-on"
    MERCH = "MERCH", "Merchandise"


class Product(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=50, blank=True)
    category = models.CharField(
        max_length=20,
        choices=ProductCategory.choices,
        default=ProductCategory.ADMISSION,
    )
    is_active = models.BooleanField(default=True)

    # If False, the product will not be shown on the POS dashboard
    show_on_dashboard = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("name", "sku")]

    def __str__(self) -> str:
        return self.name


class SessionProduct(models.Model):
    session_type = models.ForeignKey(
        SessionType,
        on_delete=models.CASCADE,
        related_name="session_products",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="session_products",
    )
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("session_type", "product")]
        ordering = ["session_type__sort_order", "product__name"]

    def __str__(self) -> str:
        return f"{self.session_type} – {self.product} @ {self.price}"


class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    session_type = models.ForeignKey(
        SessionType,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} – {self.created_at:%Y-%m-%d %H:%M}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    product_name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product_name} x {self.quantity}"