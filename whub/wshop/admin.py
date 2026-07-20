from django.contrib import admin

from .models import (
    AnalyticsEvent,
    Brand,
    Cart,
    CartItem,
    Category,
    GalleryCategory,
    GalleryItem,
    HomeHero,
    Journal,
    Order,
    OrderItem,
    Watch,
    WatchImage,
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(HomeHero)
class HomeHeroAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    list_editable = ("is_active",)
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "is_featured", "is_published", "published_at")
    list_filter = ("category", "is_published", "is_featured", "published_at")
    search_fields = ("title", "author", "excerpt")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_published", "is_featured")
    readonly_fields = ("published_at", "updated_at")
    fieldsets = (
        ("Content", {"fields": ("title", "slug", "excerpt", "content", "image")}),
        ("Details", {"fields": ("category", "author", "is_published", "is_featured")}),
        ("Dates", {"fields": ("published_at", "updated_at")}),
    )


class WatchImageInline(admin.TabularInline):
    model = WatchImage
    extra = 1
    fields = ("image", "alt_text", "is_main")


@admin.register(Watch)
class WatchAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "model",
        "movement",
        "strap_color",
        "current_price",
        "featured",
        "is_active",
    )
    list_filter = (
        "brand",
        "category",
        "model",
        "gender",
        "movement",
        "strap_material",
        "strap_color",
        "featured",
        "is_active",
    )
    list_editable = ("featured", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "brand__name", "sku")
    readonly_fields = ("created_at", "updated_at")
    inlines = [WatchImageInline]
    fieldsets = (
        (
            "Product",
            {
                "fields": (
                    "name",
                    "slug",
                    "sku",
                    "brand",
                    "category",
                    "model",
                    "gender",
                    "featured",
                    "is_active",
                )
            },
        ),
        (
            "Watch Details",
            {
                "fields": (
                    "movement",
                    "strap_material",
                    "strap_color",
                    "case_size_mm",
                    "water_resistance_m",
                )
            },
        ),
        ("Pricing", {"fields": ("price", "discount_price")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(GalleryCategory)
class GalleryCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(GalleryItem)
class GalleryItemAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "media_type", "is_featured", "is_published", "created_at")
    list_filter = ("category", "media_type", "is_published", "is_featured", "created_at")
    search_fields = ("title", "caption")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_published", "is_featured")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Content", {"fields": ("title", "slug", "caption")}),
        ("Category", {"fields": ("category",)}),
        ("Media", {"fields": ("media_type", "image", "video_file", "video_url")}),
        ("Settings", {"fields": ("is_published", "is_featured")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(WatchImage)
class WatchImageAdmin(admin.ModelAdmin):
    list_display = ("watch", "is_main", "created_at")
    list_filter = ("is_main", "created_at")
    search_fields = ("watch__name", "watch__brand__name", "alt_text")


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "watch", "user", "session_key", "path", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("watch__name", "watch__brand__name", "path", "session_key", "user__username")
    readonly_fields = ("created_at",)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("subtotal",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "total", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "session_key")
    readonly_fields = ("total", "created_at", "updated_at")
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("subtotal",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "email", "status", "total", "created_at")
    list_filter = ("status", "created_at", "updated_at")
    list_editable = ("status",)
    search_fields = ("full_name", "email", "phone", "city", "postal_code")
    readonly_fields = ("created_at", "updated_at")
    inlines = [OrderItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "watch", "quantity", "subtotal", "added_at")
    search_fields = ("watch__name", "watch__brand__name")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "watch", "quantity", "price", "subtotal")
    search_fields = ("order__full_name", "watch__name", "watch__brand__name")
