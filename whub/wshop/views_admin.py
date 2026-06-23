from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.html import escape
from django.utils.text import slugify

from .models import Watch, Order, OrderItem, Cart, Brand, Category, HomeHero, WatchImage, AnalyticsEvent

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


def get_analytics_range(request):
    try:
        days = int(request.GET.get("days", "30"))
    except (TypeError, ValueError):
        days = 30
    if days not in {7, 14, 30, 90, 180, 365}:
        days = 30
    end = timezone.now().date()
    start = end - timedelta(days=days - 1)
    return start, end, days


def money(value):
    value = value or Decimal("0")
    return f"${value:,.2f}"


def number(value):
    value = value or 0
    return f"{int(value):,}"


def visitor_key(event):
    if event.user_id:
        return f"user:{event.user_id}"
    return f"session:{event.session_key}"


def device_from_user_agent(user_agent):
    ua = (user_agent or "").lower()
    if any(token in ua for token in ("mobile", "android", "iphone", "ipad")):
        return "Mobile"
    if any(token in ua for token in ("edg", "chrome", "firefox", "safari", "opera")):
        return "Desktop"
    return "Other"


def build_line_chart(series, color="#2563eb", height=230):
    values = [float(point["value"]) for point in series]
    max_value = max(values) if values else 1
    max_value = max_value or 1
    width = 760
    pad = 34
    chart_height = height
    points = []
    if len(series) == 1:
        points = [(pad, chart_height - pad)]
    else:
        step = (width - pad * 2) / max(len(series) - 1, 1)
        for index, point in enumerate(series):
            x = pad + index * step
            y = chart_height - pad - (float(point["value"]) / max_value) * (chart_height - pad * 2)
            points.append((x, y))

    line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area_points = f"{pad},{chart_height - pad} {line_points} {width - pad},{chart_height - pad}"
    label_points = []
    if series:
        sample_count = min(len(series), 6)
        if sample_count == len(series):
            indexes = range(len(series))
        else:
            indexes = [round(index * (len(series) - 1) / (sample_count - 1)) for index in range(sample_count)]
        label_points = [series[index]["label"] for index in indexes]

    grid_lines = []
    for index in range(5):
        y = pad + index * ((chart_height - pad * 2) / 4)
        grid_lines.append(f'<line x1="{pad}" y1="{y:.1f}" x2="{width - pad}" y2="{y:.1f}" stroke="rgba(100,116,139,0.16)" stroke-width="1"/>')

    return (
        f'<svg class="chart-svg" viewBox="0 0 {width} {chart_height}" role="img" aria-label="Analytics trend chart">'
        + "".join(grid_lines)
        + f'<polygon points="{area_points}" fill="{color}" opacity="0.12"/>'
        + f'<polyline points="{line_points}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        + ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>' for x, y in points)
        + f'<text x="{pad}" y="{chart_height - 8}" fill="#64748b" font-size="12">{escape(label_points[0]) if label_points else ""}</text>'
        + f'<text x="{width - pad}" y="{chart_height - 8}" fill="#64748b" font-size="12" text-anchor="end">{escape(label_points[-1]) if label_points else ""}</text>'
        + '</svg>'
    )


def build_bar_chart(series, color="#16a34a", height=230):
    width = 760
    pad = 34
    max_value = max([float(point["value"]) for point in series] or [1]) or 1
    bar_width = max(8, (width - pad * 2) / max(len(series), 1) * 0.62)
    gap = (width - pad * 2) / max(len(series), 1)
    bars = []
    labels = []
    for index, point in enumerate(series):
        x = pad + index * gap + (gap - bar_width) / 2
        bar_height = (float(point["value"]) / max_value) * (height - pad * 2)
        y = height - pad - bar_height
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" rx="6" fill="{color}" opacity="0.88"/>')
        if index % max(1, len(series) // 6) == 0 or index == len(series) - 1:
            labels.append(f'<text x="{x + bar_width / 2:.1f}" y="{height - 8}" fill="#64748b" font-size="12" text-anchor="middle">{escape(point["label"][:10])}</text>')
    grid_lines = []
    for index in range(5):
        y = pad + index * ((height - pad * 2) / 4)
        grid_lines.append(f'<line x1="{pad}" y1="{y:.1f}" x2="{width - pad}" y2="{y:.1f}" stroke="rgba(100,116,139,0.16)" stroke-width="1"/>')
    return (
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Analytics bar chart">'
        + "".join(grid_lines)
        + "".join(bars)
        + "".join(labels)
        + '</svg>'
    )


def daily_series(start, end, queryset, date_field, value_field=None):
    if value_field:
        rows = queryset.annotate(day=TruncDate(date_field)).values("day").annotate(value=Sum(value_field)).order_by("day")
    else:
        rows = queryset.annotate(day=TruncDate(date_field)).values("day").annotate(value=Count("id")).order_by("day")
    mapped = {row["day"]: row["value"] or 0 for row in rows}
    return [
        {"label": day.strftime("%b %d"), "value": mapped.get(day, 0)}
        for day in daterange(start, end)
    ]


def daterange(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def summarize_orders(orders):
    revenue = orders.aggregate(total=Sum("total"))["total"] or Decimal("0")
    units = OrderItem.objects.filter(order__in=orders).aggregate(total=Sum("quantity"))["total"] or 0
    average_order = orders.aggregate(avg=Avg("total"))["avg"] or Decimal("0")
    return revenue, units, average_order


def get_product_rows(watches, start, end):
    rows = []
    for watch in watches:
        views = AnalyticsEvent.objects.filter(
            event_type="product_view",
            watch=watch,
            created_at__date__gte=start,
            created_at__date__lte=end,
        ).count()
        sold = OrderItem.objects.filter(
            watch=watch,
            order__created_at__date__gte=start,
            order__created_at__date__lte=end,
        ).aggregate(total=Sum("quantity"))["total"] or 0
        revenue = OrderItem.objects.filter(
            watch=watch,
            order__created_at__date__gte=start,
            order__created_at__date__lte=end,
        ).aggregate(total=Sum(F("price") * F("quantity")))["total"] or Decimal("0")
        conversion = (sold / views * 100) if views else 0
        sell_through = (sold / (sold + watch.stock) * 100) if (sold + watch.stock) else 0
        rows.append({
            "watch": watch,
            "views": views,
            "sold": sold,
            "revenue": revenue,
            "conversion": conversion,
            "sell_through": sell_through,
            "stock": watch.stock,
        })
    return sorted(rows, key=lambda row: row["views"] + row["sold"] * 3 + float(row["revenue"]) / 100, reverse=True)


def get_analytics_base_context(request):
    start, end, days = get_analytics_range(request)
    orders = Order.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    events = AnalyticsEvent.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    product_events = events.filter(event_type="product_view")
    revenue, units_sold, average_order = summarize_orders(orders)
    visitors = len({visitor_key(event) for event in events if visitor_key(event) != "session:"})
    conversion_rate = (orders.count() / visitors * 100) if visitors else 0
    top_viewed = (
        product_events.exclude(watch__isnull=True)
        .values("watch_id", "watch__name", "watch__slug", "watch__brand__name")
        .annotate(views=Count("id"))
        .order_by("-views")[:8]
    )
    top_sold = (
        OrderItem.objects.filter(order__in=orders)
        .values("watch_id", "watch__name", "watch__slug", "watch__brand__name")
        .annotate(units=Sum("quantity"), revenue=Sum(F("price") * F("quantity")))
        .order_by("-units")[:8]
    )

    return {
        "start": start,
        "end": end,
        "days": days,
        "orders": orders,
        "events": events,
        "product_events": product_events,
        "revenue": revenue,
        "units_sold": units_sold,
        "average_order": average_order,
        "visitors": visitors,
        "conversion_rate": conversion_rate,
        "top_viewed": top_viewed,
        "top_sold": top_sold,
        "range_options": [7, 14, 30, 90, 180, 365],
    }


def admin_dashboard(request):
    total_products = Watch.objects.filter(is_active=True).count()
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    total_revenue = Order.objects.aggregate(Sum("total"))["total__sum"] or 0
    low_stock = Watch.objects.filter(stock__lt=5, is_active=True).count()
    recent_orders = Order.objects.select_related("user").order_by("-created_at")[:8]
    top_products = (
        OrderItem.objects.values("watch__name", "watch__brand__name", "watch__slug")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:6]
    )
    recent_watches = Watch.objects.filter(is_active=True).select_related("brand").order_by("-created_at")[:8]

    context = {
        "total_products": total_products,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "total_revenue": total_revenue,
        "low_stock": low_stock,
        "recent_orders": recent_orders,
        "top_products": top_products,
        "recent_watches": recent_watches,
        "dashboard_title": "Dashboard",
        "dashboard_active": True,
    }
    return render(request, "panel/dashboard.html", context)


def admin_analytics(request):
    base = get_analytics_base_context(request)
    orders = base["orders"]
    events = base["events"]
    product_events = base["product_events"]
    watches = Watch.objects.select_related("brand", "category").all()
    product_rows = get_product_rows(watches, base["start"], base["end"])

    revenue_series = daily_series(base["start"], base["end"], orders, "created_at", "total")
    view_series = daily_series(base["start"], base["end"], product_events, "created_at")
    visitor_series = []
    visitors_by_day = defaultdict(set)
    for event in events:
        visitors_by_day[event.created_at.date()].add(visitor_key(event))
    for day in daterange(base["start"], base["end"]):
        visitor_series.append({"label": day.strftime("%b %d"), "value": len(visitors_by_day.get(day, set()))})

    category_rows = []
    for category in Category.objects.all():
        category_watches = list(watches.filter(category=category))
        if not category_watches:
            continue
        category_ids = [watch.pk for watch in category_watches]
        views = product_events.filter(watch_id__in=category_ids).count()
        sold = OrderItem.objects.filter(watch_id__in=category_ids, order__in=orders).aggregate(total=Sum("quantity"))["total"] or 0
        revenue = OrderItem.objects.filter(watch_id__in=category_ids, order__in=orders).aggregate(total=Sum(F("price") * F("quantity")))["total"] or Decimal("0")
        category_rows.append({"category": category, "views": views, "sold": sold, "revenue": revenue})
    category_rows = sorted(category_rows, key=lambda row: row["revenue"], reverse=True)[:6]

    brand_rows = []
    for brand in Brand.objects.all():
        brand_watches = list(watches.filter(brand=brand))
        if not brand_watches:
            continue
        brand_ids = [watch.pk for watch in brand_watches]
        views = product_events.filter(watch_id__in=brand_ids).count()
        sold = OrderItem.objects.filter(watch_id__in=brand_ids, order__in=orders).aggregate(total=Sum("quantity"))["total"] or 0
        revenue = OrderItem.objects.filter(watch_id__in=brand_ids, order__in=orders).aggregate(total=Sum(F("price") * F("quantity")))["total"] or Decimal("0")
        brand_rows.append({"brand": brand, "views": views, "sold": sold, "revenue": revenue})
    brand_rows = sorted(brand_rows, key=lambda row: row["revenue"], reverse=True)[:6]

    top_paths = (
        events.exclude(path="")
        .values("path")
        .annotate(visits=Count("id"))
        .order_by("-visits")[:8]
    )
    device_counts = defaultdict(int)
    for event in events:
        device_counts[device_from_user_agent(event.user_agent)] += 1
    device_rows = sorted(
        [{"device": device, "visits": visits} for device, visits in device_counts.items()],
        key=lambda row: row["visits"],
        reverse=True,
    )

    context = {
        **base,
        "dashboard_title": "Analytics",
        "analytics_active": True,
        "revenue_chart": build_line_chart(revenue_series, "#2563eb"),
        "view_chart": build_line_chart(view_series, "#16a34a"),
        "visitor_chart": build_line_chart(visitor_series, "#d97706"),
        "product_rows": product_rows[:10],
        "category_rows": category_rows,
        "brand_rows": brand_rows,
        "top_paths": top_paths,
        "device_rows": device_rows,
        "out_of_stock": Watch.objects.filter(stock=0, is_active=True).count(),
        "low_stock": Watch.objects.filter(stock__lt=5, stock__gt=0, is_active=True).count(),
    }
    return render(request, "panel/analytics.html", context)


def admin_analytics_products(request):
    base = get_analytics_base_context(request)
    watches = Watch.objects.select_related("brand", "category").prefetch_related("images").all()
    rows = get_product_rows(watches, base["start"], base["end"])
    context = {
        **base,
        "dashboard_title": "Product Analytics",
        "analytics_active": True,
        "products_active": True,
        "rows": rows,
        "product_chart": build_bar_chart([
            {"label": row["watch"].name[:18], "value": row["views"] + row["sold"] * 2}
            for row in rows[:12]
        ], "#2563eb"),
    }
    return render(request, "panel/analytics_products.html", context)


def admin_analytics_sales(request):
    base = get_analytics_base_context(request)
    orders = base["orders"]
    revenue_series = daily_series(base["start"], base["end"], orders, "created_at", "total")
    order_series = daily_series(base["start"], base["end"], orders, "created_at")
    status_rows = []
    for status, label in Order.STATUS_CHOICES:
        count = orders.filter(status=status).count()
        revenue = orders.filter(status=status).aggregate(total=Sum("total"))["total"] or Decimal("0")
        status_rows.append({"status": status, "label": label, "count": count, "revenue": revenue})
    status_rows = sorted(status_rows, key=lambda row: row["count"], reverse=True)

    top_customers = (
        orders.values("full_name", "email", "city")
        .annotate(orders_count=Count("id"), revenue=Sum("total"))
        .order_by("-revenue")[:8]
    )
    context = {
        **base,
        "dashboard_title": "Sales Analytics",
        "analytics_active": True,
        "orders_active": True,
        "revenue_chart": build_line_chart(revenue_series, "#2563eb"),
        "order_chart": build_line_chart(order_series, "#16a34a"),
        "pending_orders": orders.filter(status="pending").count(),
        "status_rows": status_rows,
        "top_customers": top_customers,
    }
    return render(request, "panel/analytics_sales.html", context)


def admin_analytics_visitors(request):
    base = get_analytics_base_context(request)
    events = base["events"]
    visitor_series = []
    visitors_by_day = defaultdict(set)
    for event in events:
        visitors_by_day[event.created_at.date()].add(visitor_key(event))
    for day in daterange(base["start"], base["end"]):
        visitor_series.append({"label": day.strftime("%b %d"), "value": len(visitors_by_day.get(day, set()))})

    top_paths = (
        events.exclude(path="")
        .values("path")
        .annotate(visits=Count("id"))
        .order_by("-visits")[:10]
    )
    referrers = (
        events.exclude(referrer="")
        .values("referrer")
        .annotate(visits=Count("id"))
        .order_by("-visits")[:10]
    )
    device_counts = defaultdict(int)
    for event in events:
        device_counts[device_from_user_agent(event.user_agent)] += 1
    device_rows = sorted(
        [{"device": device, "visits": visits} for device, visits in device_counts.items()],
        key=lambda row: row["visits"],
        reverse=True,
    )
    recent_events = events.select_related("watch", "user").order_by("-created_at")[:20]
    context = {
        **base,
        "dashboard_title": "Visitor Analytics",
        "analytics_active": True,
        "visitor_chart": build_line_chart(visitor_series, "#d97706"),
        "top_paths": top_paths,
        "referrers": referrers,
        "device_rows": device_rows,
        "recent_events": recent_events,
    }
    return render(request, "panel/analytics_visitors.html", context)


def admin_products(request):
    query = request.GET.get("q", "")
    brand_filter = request.GET.get("brand", "")
    category_filter = request.GET.get("category", "")
    model_filter = request.GET.get("model", "")
    gender_filter = request.GET.get("gender", "")
    movement_filter = request.GET.get("movement", "")
    strap_filter = request.GET.get("strap", "")
    stock_filter = request.GET.get("stock", "")
    active_filter = request.GET.get("active", "")
    watches = Watch.objects.select_related("brand", "category").prefetch_related("images").order_by("-created_at")
    if query:
        watches = watches.filter(Q(name__icontains=query) | Q(sku__icontains=query) | Q(brand__name__icontains=query))
    if brand_filter:
        watches = watches.filter(brand__name=brand_filter)
    if category_filter:
        watches = watches.filter(category__name=category_filter)
    if model_filter:
        watches = watches.filter(model=model_filter)
    if gender_filter:
        watches = watches.filter(gender=gender_filter)
    if movement_filter:
        watches = watches.filter(movement=movement_filter)
    if strap_filter:
        watches = watches.filter(strap_material=strap_filter)
    if stock_filter == "in_stock":
        watches = watches.filter(stock__gt=0)
    elif stock_filter == "low_stock":
        watches = watches.filter(stock__gt=0, stock__lt=5)
    elif stock_filter == "out_of_stock":
        watches = watches.filter(stock=0)
    if active_filter == "active":
        watches = watches.filter(is_active=True)
    elif active_filter == "inactive":
        watches = watches.filter(is_active=False)
    watches = watches[:50]
    total_products = Watch.objects.filter(is_active=True).count()
    out_of_stock = Watch.objects.filter(stock=0, is_active=True).count()
    featured_count = Watch.objects.filter(featured=True, is_active=True).count()
    all_brands = Brand.objects.all().order_by("name")
    all_categories = Category.objects.all().order_by("name")

    context = {
        "watches": watches,
        "total_products": total_products,
        "out_of_stock": out_of_stock,
        "featured_count": featured_count,
        "all_brands": all_brands,
        "all_categories": all_categories,
        "dashboard_title": "Products",
        "products_active": True,
    }
    return render(request, "panel/products.html", context)


def admin_product_search(request):
    query = request.GET.get("q", "")
    brand_filter = request.GET.get("brand", "")
    category_filter = request.GET.get("category", "")
    model_filter = request.GET.get("model", "")
    gender_filter = request.GET.get("gender", "")
    movement_filter = request.GET.get("movement", "")
    strap_filter = request.GET.get("strap", "")
    strap_material_filter = request.GET.get("strap_material", "")
    price_filter = request.GET.get("price", "")
    stock_filter = request.GET.get("stock", "")
    active_filter = request.GET.get("active", "")
    watches = Watch.objects.select_related("brand", "category").prefetch_related("images").order_by("-created_at")
    if query:
        watches = watches.filter(Q(name__icontains=query) | Q(sku__icontains=query) | Q(brand__name__icontains=query))
    if brand_filter:
        watches = watches.filter(brand__name=brand_filter)
    if category_filter:
        watches = watches.filter(category__name=category_filter)
    if model_filter:
        watches = watches.filter(model=model_filter)
    if gender_filter:
        watches = watches.filter(gender=gender_filter)
    if movement_filter:
        watches = watches.filter(movement=movement_filter)
    if strap_filter:
        watches = watches.filter(strap_material=strap_filter)
    if strap_material_filter:
        watches = watches.filter(strap_material=strap_material_filter)
    if price_filter == "0-500":
        watches = watches.filter(price__lt=500)
    elif price_filter == "500-2000":
        watches = watches.filter(price__gte=500, price__lt=2000)
    elif price_filter == "2000-5000":
        watches = watches.filter(price__gte=2000, price__lt=5000)
    elif price_filter == "5000":
        watches = watches.filter(price__gte=5000)
    if stock_filter == "in_stock":
        watches = watches.filter(stock__gt=0)
    elif stock_filter == "low_stock":
        watches = watches.filter(stock__gt=0, stock__lt=5)
    elif stock_filter == "out_of_stock":
        watches = watches.filter(stock=0)
    if active_filter == "active":
        watches = watches.filter(is_active=True)
    elif active_filter == "inactive":
        watches = watches.filter(is_active=False)
    watches = watches[:20]

    rows = []
    for w in watches:
        images = w.images.all()
        rows.append({
            "id": w.id,
            "name": w.name,
            "slug": w.slug,
            "brand": w.brand.name,
            "category": w.category.name,
            "model": w.model,
            "price": str(w.current_price),
            "old_price": str(w.price) if w.discount_price else "",
            "stock": w.stock,
            "is_active": w.is_active,
            "images": [
                {"url": image.image.url, "alt": image.alt_text or w.name}
                for image in images
            ],
        })

    from django.http import JsonResponse
    return JsonResponse({"results": rows})


def admin_product_detail(request, slug):
    watch = get_object_or_404(Watch.objects.select_related("brand", "category").prefetch_related("images"), slug=slug)
    context = {
        "watch": watch,
        "dashboard_title": watch.name,
        "products_active": True,
    }
    return render(request, "panel/product_detail.html", context)


def admin_product_toggle_featured(request, slug):
    watch = get_object_or_404(Watch, slug=slug)
    watch.featured = not watch.featured
    watch.save()
    messages.success(request, f"Featured status updated for {watch.name}.")
    return redirect("panel-products")


def admin_product_toggle_active(request, slug):
    watch = get_object_or_404(Watch, slug=slug)
    watch.is_active = not watch.is_active
    watch.save()
    messages.success(request, f"Active status updated for {watch.name}.")
    return redirect("panel-products")


def admin_product_delete(request, slug):
    watch = get_object_or_404(Watch, slug=slug)
    name = watch.name
    watch.delete()
    messages.success(request, f"{name} has been deleted.")
    return redirect("panel-products")


def admin_product_add(request):
    brands = Brand.objects.all().order_by("name")
    categories = Category.objects.all().order_by("name")
    if request.method == "POST":
        from django import forms

        class WatchForm(forms.ModelForm):
            class Meta:
                model = Watch
                fields = [
                    "name", "brand", "category", "model", "gender",
                    "movement", "strap_material", "strap_color", "case_size_mm",
                    "water_resistance_m", "price", "discount_price", "stock",
                    "featured", "is_active",
                ]

        form = WatchForm(request.POST)
        if form.is_valid():
            watch = form.save(commit=False)
            watch.slug = slugify(watch.name)
            watch.sku = f"{watch.brand.name[:3].upper()}-{watch.name[:3].upper()}-{uuid.uuid4().hex[:8].upper()}"
            watch.save()
            uploaded_files = request.FILES.getlist("new_images")
            primary_index = request.POST.get("primary_image_id", "0")
            try:
                primary_index = int(primary_index)
            except (ValueError, TypeError):
                primary_index = 0
            for idx, uploaded_file in enumerate(uploaded_files):
                WatchImage.objects.create(
                    watch=watch,
                    image=uploaded_file,
                    alt_text=watch.name,
                    is_primary=(idx == primary_index),
                )
            if not watch.images.filter(is_primary=True).exists() and watch.images.exists():
                first = watch.images.first()
                first.is_primary = True
                first.save()
            messages.success(request, f"Created {watch.name}.")
            return redirect("panel-product-edit", slug=watch.slug)
    else:
        from django import forms

        class WatchForm(forms.ModelForm):
            class Meta:
                model = Watch
                fields = [
                    "name", "brand", "category", "model", "gender",
                    "movement", "strap_material", "strap_color", "case_size_mm",
                    "water_resistance_m", "price", "discount_price", "stock",
                    "featured", "is_active",
                ]

        form = WatchForm()

    return render(request, "panel/product_add.html", {
        "form": form,
        "brands": brands,
        "categories": categories,
        "dashboard_title": "Add Product",
        "products_active": True,
    })


def admin_add_brand(request):
    if request.method == "POST":
        from django.http import JsonResponse
        import json
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        brand, created = Brand.objects.get_or_create(
            name__iexact=name,
            defaults={"name": name, "slug": slugify(name), "is_active": True},
        )
        return JsonResponse({"id": brand.id, "name": brand.name, "created": created})
    return JsonResponse({"error": "Invalid request"}, status=400)


def admin_add_category(request):
    if request.method == "POST":
        from django.http import JsonResponse
        import json
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        category, created = Category.objects.get_or_create(
            name__iexact=name,
            defaults={"name": name, "slug": slugify(name), "is_active": True},
        )
        return JsonResponse({"id": category.id, "name": category.name, "created": created})
    return JsonResponse({"error": "Invalid request"}, status=400)


def admin_add_model(request):
    if request.method == "POST":
        from django.http import JsonResponse
        import json
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        return JsonResponse({"id": name, "name": name, "created": True})
    return JsonResponse({"error": "Invalid request"}, status=400)


def admin_add_movement(request):
    if request.method == "POST":
        from django.http import JsonResponse
        import json
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        return JsonResponse({"id": name, "name": name, "created": True})
    return JsonResponse({"error": "Invalid request"}, status=400)


def admin_add_strap_material(request):
    if request.method == "POST":
        from django.http import JsonResponse
        import json
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        return JsonResponse({"id": name, "name": name, "created": True})
    return JsonResponse({"error": "Invalid request"}, status=400)


def admin_add_strap_color(request):
    if request.method == "POST":
        from django.http import JsonResponse
        import json
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        return JsonResponse({"id": name, "name": name, "created": True})
    return JsonResponse({"error": "Invalid request"}, status=400)


def admin_product_edit(request, slug):
    watch = get_object_or_404(Watch, slug=slug)
    images = watch.images.all()
    if request.method == "POST":
        from django import forms

        class WatchForm(forms.ModelForm):
            class Meta:
                model = Watch
                fields = [
                    "name", "slug", "sku", "brand", "category", "model", "gender",
                    "movement", "strap_material", "strap_color", "case_size_mm",
                    "water_resistance_m", "price", "discount_price", "stock",
                    "featured", "is_active",
                ]
                widgets = {"slug": forms.TextInput(attrs={"readonly": "readonly"})}

        form = WatchForm(request.POST, instance=watch)
        if form.is_valid():
            form.save()
            uploaded_files = request.FILES.getlist("new_images")
            for idx, uploaded_file in enumerate(uploaded_files):
                WatchImage.objects.create(
                    watch=watch,
                    image=uploaded_file,
                    alt_text=watch.name,
                    is_primary=(idx == 0 and not watch.images.filter(is_primary=True).exists()),
                )
            if not watch.images.filter(is_primary=True).exists() and watch.images.exists():
                first = watch.images.first()
                first.is_primary = True
                first.save()
            primary_id = request.POST.get("primary_image_id")
            if primary_id:
                watch.images.exclude(id=primary_id).update(is_primary=False)
                watch.images.filter(id=primary_id).update(is_primary=True)
            delete_ids = request.POST.getlist("delete_image_ids")
            if delete_ids:
                watch.images.filter(id__in=delete_ids).delete()
                if not watch.images.filter(is_primary=True).exists() and watch.images.exists():
                    first = watch.images.first()
                    first.is_primary = True
                    first.save()
            messages.success(request, f"Updated {watch.name}.")
            return redirect("panel-product-edit", slug=watch.slug)
    else:
        from django import forms

        class WatchForm(forms.ModelForm):
            class Meta:
                model = Watch
                fields = [
                    "name", "slug", "sku", "brand", "category", "model", "gender",
                    "movement", "strap_material", "strap_color", "case_size_mm",
                    "water_resistance_m", "price", "discount_price", "stock",
                    "featured", "is_active",
                ]
                widgets = {"slug": forms.TextInput(attrs={"readonly": "readonly"})}

        form = WatchForm(instance=watch)

    return render(request, "panel/product_edit.html", {
        "watch": watch,
        "form": form,
        "images": images,
        "dashboard_title": f"Edit {watch.name}",
        "products_active": True,
    })


def admin_image_set_primary(request, slug, image_id):
    watch = get_object_or_404(Watch, slug=slug)
    watch.images.exclude(id=image_id).update(is_primary=False)
    watch.images.filter(id=image_id).update(is_primary=True)
    messages.success(request, "Primary image updated.")
    return redirect("panel-product-edit", slug=watch.slug)


def admin_image_delete(request, slug, image_id):
    watch = get_object_or_404(Watch, slug=slug)
    image = get_object_or_404(WatchImage, id=image_id, watch=watch)
    was_primary = image.is_primary
    image.delete()
    if was_primary and watch.images.exists():
        first = watch.images.first()
        first.is_primary = True
        first.save()
    messages.success(request, "Image deleted.")
    return redirect("panel-product-edit", slug=watch.slug)


def admin_orders(request):
    orders = Order.objects.select_related("user").prefetch_related("items__watch").order_by("-created_at")[:50]
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    processing_orders = Order.objects.filter(status="processing").count()
    delivered_orders = Order.objects.filter(status="delivered").count()

    context = {
        "orders": orders,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "processing_orders": processing_orders,
        "delivered_orders": delivered_orders,
        "dashboard_title": "Orders",
        "orders_active": True,
    }
    return render(request, "panel/orders.html", context)


def admin_cart(request):
    carts = Cart.objects.select_related("user").prefetch_related("items__watch").order_by("-updated_at")[:50]
    total_carts = Cart.objects.count()
    active_carts = Cart.objects.filter(items__isnull=False).distinct().count()

    context = {
        "carts": carts,
        "total_carts": total_carts,
        "active_carts": active_carts,
        "dashboard_title": "Carts",
        "cart_active": True,
    }
    return render(request, "panel/cart.html", context)


def admin_media(request):
    heroes = HomeHero.objects.all().order_by("-created_at")[:20]
    images = WatchImage.objects.select_related("watch").order_by("-created_at")[:50]
    total_heroes = HomeHero.objects.count()
    total_images = WatchImage.objects.count()

    context = {
        "heroes": heroes,
        "images": images,
        "total_heroes": total_heroes,
        "total_images": total_images,
        "dashboard_title": "Media",
        "media_active": True,
    }
    return render(request, "panel/media.html", context)


def admin_settings(request):
    brands = Brand.objects.all().order_by("name")
    categories = Category.objects.all().order_by("name")
    total_brands = Brand.objects.count()
    total_categories = Category.objects.count()

    context = {
        "brands": brands,
        "categories": categories,
        "total_brands": total_brands,
        "total_categories": total_categories,
        "dashboard_title": "Settings",
        "settings_active": True,
    }
    return render(request, "panel/settings.html", context)
