from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class HomeHero(models.Model):
    title = models.CharField(max_length=120, default="Homepage Hero")
    video = models.FileField(upload_to="hero_videos/")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Home Hero Video"
        verbose_name_plural = "Home Hero Videos"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Watch(models.Model):
    MODEL_CHOICES = [
        ("classic", "Classic"),
        ("sport", "Sport"),
        ("luxury", "Luxury"),
        ("dress", "Dress"),
        ("diver", "Diver"),
        ("chronograph", "Chronograph"),
        ("vandross", "Vandross"),
    ]

    GENDER_CHOICES = [
        ("men", "Men"),
        ("women", "Women"),
        ("unisex", "Unisex"),
    ]

    MOVEMENT_CHOICES = [
        ("automatic", "Automatic"),
        ("quartz", "Quartz"),
        ("mechanical", "Mechanical"),
        ("solar", "Solar"),
        ("smart", "Smart"),
    ]

    STRAP_CHOICES = [
        ("leather", "Leather"),
        ("metal", "Metal"),
        ("rubber", "Rubber"),
        ("fabric", "Fabric"),
        ("ceramic", "Ceramic"),
    ]

    STRAP_COLOR_CHOICES = [
        ("silver", "Silver"),
        ("gold", "Gold"),
        ("rose_gold", "Rose Gold"),
        ("black", "Black"),
        ("brown", "Brown"),
        ("blue", "Blue"),
        ("white", "White"),
    ]

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="watches")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="watches",
    )
    model = models.CharField(max_length=30, choices=MODEL_CHOICES, default="classic")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="unisex")
    movement = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    strap_material = models.CharField(max_length=20, choices=STRAP_CHOICES)
    strap_color = models.CharField(
        max_length=20,
        choices=STRAP_COLOR_CHOICES,
        default="silver",
    )
    case_size_mm = models.PositiveSmallIntegerField()
    water_resistance_m = models.PositiveSmallIntegerField(default=0)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
    )
    stock = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=60, unique=True)
    featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.brand} {self.name}"

    @property
    def current_price(self):
        if self.discount_price is not None:
            return self.discount_price
        return self.price

    @property
    def in_stock(self):
        return self.stock > 0


class WatchImage(models.Model):
    watch = models.ForeignKey(Watch, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="watches/")
    alt_text = models.CharField(max_length=160, blank=True)
    is_main = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-is_main", "created_at"]

    def __str__(self):
        return f"Image for {self.watch}"


class AnalyticsEvent(models.Model):
    EVENT_CHOICES = [
        ("page_view", "Page View"),
        ("product_view", "Product View"),
        ("cart_add", "Cart Add"),
        ("checkout_start", "Checkout Start"),
        ("order_placed", "Order Placed"),
    ]

    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES, db_index=True)
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="analytics_events",
        blank=True,
        null=True,
    )
    watch = models.ForeignKey(
        Watch,
        on_delete=models.SET_NULL,
        related_name="analytics_events",
        blank=True,
        null=True,
    )
    path = models.CharField(max_length=255, blank=True)
    referrer = models.CharField(max_length=512, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["watch", "-created_at"]),
            models.Index(fields=["session_key", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.created_at:%Y-%m-%d %H:%M}"


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        blank=True,
        null=True,
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart #{self.pk}"

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    watch = models.ForeignKey(Watch, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "watch"], name="unique_cart_watch")
        ]

    def __str__(self):
        return f"{self.quantity} x {self.watch}"

    @property
    def subtotal(self):
        return self.watch.current_price * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="orders",
        blank=True,
        null=True,
    )
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} - {self.full_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    watch = models.ForeignKey(Watch, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    def __str__(self):
        return f"{self.quantity} x {self.watch}"

    @property
    def subtotal(self):
        return self.price * self.quantity
