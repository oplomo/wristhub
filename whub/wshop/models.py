from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


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
    video = models.FileField(upload_to="hero_videos/", blank=True)
    image = models.ImageField(upload_to="hero_images/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Home Hero"
        verbose_name_plural = "Home Heroes"
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


class WatchImage(models.Model):
    watch = models.ForeignKey(Watch, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="watches/")
    color = models.CharField(max_length=50, blank=True, default="", help_text="Colour or finish shown in this image, e.g. Black or Rose Gold.")
    alt_text = models.CharField(max_length=160, blank=True)
    is_main = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-is_main", "created_at"]

    def __str__(self):
        return f"Image for {self.watch}"


class GalleryCategory(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Gallery Categories"

    def __str__(self):
        return self.name


class GalleryItem(models.Model):
    MEDIA_TYPE_CHOICES = [
        ("image", "Image"),
        ("video", "Video"),
    ]

    title = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True, blank=True, default="")
    category = models.ForeignKey(GalleryCategory, on_delete=models.CASCADE, related_name="items")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default="image")
    image = models.ImageField(upload_to="gallery/images/", blank=True, null=True)
    video_file = models.FileField(upload_to="gallery/videos/", blank=True, null=True)
    video_url = models.URLField(blank=True, help_text="YouTube/Vimeo/MP4 link")
    caption = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-created_at"]

    def __str__(self):
        return self.title or "Untitled Gallery Item"

    def save(self, *args, **kwargs):
        if not self.slug:
            import uuid
            from django.utils.text import slugify
            base_slug = slugify(self.title) if self.title else f"gallery-{uuid.uuid4().hex[:8]}"
            slug = base_slug
            counter = 1
            qs = GalleryItem.objects.all()
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


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
    county = models.CharField(max_length=100, blank=True)
    sub_county = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=100, blank=True)
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


class Journal(models.Model):
    CATEGORY_CHOICES = [
        ("watch-guides", "Watch Guides"),
        ("style", "Style & Trends"),
        ("history", "Watch History"),
        ("reviews", "Reviews"),
        ("industry", "Industry News"),
        ("lifestyle", "Lifestyle"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    excerpt = models.TextField(max_length=300, help_text="Short summary for cards and SEO.")
    content = models.TextField(help_text="Full article body (HTML supported).")
    image = models.ImageField(upload_to="journals/", blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="style")
    author = models.CharField(max_length=100, default="Wrist Hub Editorial")
    published_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "Journal Article"
        verbose_name_plural = "Journal Articles"

    def __str__(self):
        return self.title

    @property
    def images_all(self):
        imgs = list(self.images.all())
        if not imgs and self.image:
            imgs = [self.image]
        return imgs

    @property
    def has_gallery(self):
        return self.images.exists() or bool(self.image)


class JournalImage(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="journals/", blank=True)
    caption = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"Image for {self.journal.title}"


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


class ProductReview(models.Model):
    watch = models.ForeignKey(Watch, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    content = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["watch", "user"]

    def __str__(self):
        return f"Review by {self.user} on {self.watch}"


class ReviewReply(models.Model):
    review = models.ForeignKey(
        ProductReview, on_delete=models.CASCADE, related_name="replies"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_replies",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply by {self.user} on review #{self.review.pk}"


class ReviewLike(models.Model):
    review = models.ForeignKey(
        ProductReview, on_delete=models.CASCADE, related_name="likes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["review", "user"]

    def __str__(self):
        return f"Like by {self.user} on review #{self.review.pk}"
