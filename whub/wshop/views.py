import json
import os

from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.db.models import Q, Sum
from django.forms import CharField, ChoiceField, EmailField, Form, Select
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .analytics import record_analytics_event
from .forms import LoginForm, RegisterForm
from .models import Brand, Category, GalleryCategory, GalleryItem, HomeHero, Journal, Order, OrderItem, Watch, Cart, CartItem, ProductReview, ReviewReply, ReviewLike
from .email import send_order_notification_email


def get_location_data():
    path = os.path.join(os.path.dirname(__file__), "counties_data", "db.json")
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    data = {}
    for row in raw:
        county = (row.get("County_name") or "").strip()
        sub = (row.get("Constituency_name") or "").strip()
        wards = row.get("Ward") or []
        if not county or not sub:
            continue
        data.setdefault(county, {})
        data[county].setdefault(sub, [])
        for ward in wards:
            if ward and ward not in data[county][sub]:
                data[county][sub].append(ward)
    return data


PERSONALITIES = [
    {
        "slug": "sport",
        "title": "Sport",
        "eyebrow": "Built for movement",
        "text": "Sport watches built to keep pace with training, travel, and the everyday grind - durable, legible, and ready when you are.",
        "category_slug": "sport",
    },
    {
        "slug": "executive",
        "title": "Executive",
        "eyebrow": "Made for the office",
        "text": "Refined dress watches that bring a polished finish to the workday and every important occasion.",
        "category_slug": "dress",
    },
    {
        "slug": "luxury",
        "title": "Luxury",
        "eyebrow": "Made to stand apart",
        "text": "Luxury timepieces for the moments that matter - distinctive pieces with lasting presence.",
        "category_slug": "luxury",
    },
]


class CheckoutForm(Form):
    full_name = CharField(max_length=120)
    email = EmailField()
    phone = CharField(max_length=30)
    county = ChoiceField(required=True, widget=Select(attrs={"class": "form-input"}))
    sub_county = ChoiceField(required=True, widget=Select(attrs={"class": "form-input"}))
    ward = ChoiceField(required=False, widget=Select(attrs={"class": "form-input"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        locations = get_location_data()
        counties = sorted(locations.keys())
        self.fields["county"].choices = [("", "Select county")] + [(c, c) for c in counties]

        selected_county = self.data.get("county") or self.initial.get("county") or ""
        subs = sorted(locations.get(selected_county, {}).keys())
        self.fields["sub_county"].choices = [("", "Select sub-county")] + [(s, s) for s in subs]

        selected_sub = self.data.get("sub_county") or self.initial.get("sub_county") or ""
        wards = locations.get(selected_county, {}).get(selected_sub, [])
        self.fields["ward"].choices = [("", "Select ward (optional)")] + [(w, w) for w in wards]


def get_session_key(request):
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    return session_key


def get_or_create_cart(request):
    session_key = get_session_key(request)

    if request.user.is_authenticated:
        user_cart = Cart.objects.filter(user=request.user).first()
        session_cart = Cart.objects.filter(session_key=session_key).first()

        if not user_cart and session_cart:
            session_cart.user = request.user
            session_cart.save(update_fields=["user"])
            return session_cart

        if user_cart and session_cart and user_cart.pk != session_cart.pk:
            merge_session_cart_into_user_cart(user_cart, session_cart)

        if user_cart:
            return user_cart

    cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart


def merge_session_cart_into_user_cart(user_cart, session_cart):
    session_items = list(session_cart.items.select_related("watch"))
    for session_item in session_items:
        user_item, created = CartItem.objects.get_or_create(cart=user_cart, watch=session_item.watch)
        if created:
            user_item.quantity = session_item.quantity
        else:
            user_item.quantity = user_item.quantity + session_item.quantity
        user_item.save()
        session_item.delete()


def get_cart_items(cart):
    items = list(
        cart.items.select_related("watch", "watch__brand", "watch__category")
        .prefetch_related("watch__images")
        .order_by("added_at")
    )
    return items


def get_cart_count(cart):
    return cart.items.aggregate(total=Sum("quantity"))["total"] or 0


def home(request):
    hero = HomeHero.objects.filter(is_active=True).first()
    recent_watches = (
        Watch.objects.filter(is_active=True)
        .select_related("brand", "category")
        .prefetch_related("images")
        .order_by("-created_at")[:5]
    )
    categories = {
        category.slug: category
        for category in Category.objects.filter(is_active=True)
    }

    random_watch_image = {}
    for personality in PERSONALITIES:
        slug = personality["category_slug"]
        if slug in random_watch_image:
            continue
        watch = (
            Watch.objects.filter(is_active=True, category__slug=slug)
            .prefetch_related("images")
            .order_by("?")
            .first()
        )
        image = watch.images.first() if watch else None
        random_watch_image[slug] = image.image.url if image else None

    personalities = []

    for personality in PERSONALITIES:
        personalities.append({
            **personality,
            "category": categories.get(personality["category_slug"]),
            "image": random_watch_image.get(personality["category_slug"]),
        })

    featured_watches = (
        Watch.objects.filter(is_active=True, featured=True)
        .select_related("brand", "category")
        .prefetch_related("images")
        .order_by("-price")[:3]
    )
    home_journal = (
        Journal.objects.filter(is_published=True)
        .order_by("-is_featured", "-published_at")
        .first()
    )

    return render(
        request,
        "home.html",
        {
            "hero": hero,
            "personalities": personalities,
            "recent_watches": recent_watches,
            "featured_watches": featured_watches,
            "home_journal": home_journal,
            "theme": "unisex",
        },
    )


def shop(request, **filters):
    params = request.GET.copy()
    for key, value in filters.items():
        if value and not params.get(key):
            params[key] = value

    watches = (
        Watch.objects.filter(is_active=True)
        .select_related("brand", "category")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    query = params.get("q", "").strip()
    brand_filter = params.get("brand", "").strip()
    category_filter = params.get("category", "").strip()
    movement_filter = params.get("movement", "").strip()
    model_filter = params.get("model", "").strip()
    gender_filter = params.get("gender", "").strip()
    strap_material_filter = params.get("strap_material", "").strip()
    price_filter = params.get("price", "").strip()

    if query:
        watches = watches.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(category__name__icontains=query)
        )
    if brand_filter:
        watches = watches.filter(brand__name__iexact=brand_filter)
    if category_filter:
        watches = watches.filter(category__name__iexact=category_filter)
    if movement_filter:
        watches = watches.filter(movement=movement_filter)
    if model_filter:
        watches = watches.filter(model=model_filter)
    if gender_filter:
        watches = watches.filter(gender=gender_filter)
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

    brands = Brand.objects.all().order_by("name")
    categories = Category.objects.filter(is_active=True).order_by("name")

    gender = gender_filter or filters.get("gender")
    theme = gender if gender in ("men", "women") else "unisex"

    return render(
        request,
        "shop.html",
        {
            "watches": watches,
            "brands": brands,
            "categories": categories,
            "active_filters": {
                "q": query,
                "brand": brand_filter,
                "category": category_filter,
                "movement": movement_filter,
                "model": model_filter,
                "gender": gender_filter,
                "strap_material": strap_material_filter,
                "price": price_filter,
            },
            "theme": theme,
        },
    )


STATUS_FLOW = ["pending", "paid", "processing", "shipped", "delivered"]

STATUS_BADGE = {
    "pending": "badge-default",
    "paid": "badge-info",
    "processing": "badge-warning",
    "shipped": "badge-info",
    "delivered": "badge-success",
    "cancelled": "badge-danger",
}


def _enrich_order(order):
    if order.status in STATUS_FLOW:
        order.tracker_step = STATUS_FLOW.index(order.status)
    elif order.status == "cancelled":
        order.tracker_step = -1
    else:
        order.tracker_step = 0
    order.is_current = order.status not in ("delivered", "cancelled")
    order.status_badge = STATUS_BADGE.get(order.status, "badge-default")
    order.item_count = sum(item.quantity for item in order.items.all())


def about(request):
    return render(request, "about.html", {"theme": "unisex"})


def faq(request):
    faqs = [
        {
            "q": "Do your watches fade or lose colour over time?",
            "a": "Not with proper care. We use high-grade stainless steel, mineral crystal glass, and quality plating on all our timepieces. To keep your watch looking its best, avoid prolonged exposure to harsh chemicals, perfumes, and extreme direct sunlight. Wipe it with a soft cloth after wear — especially in humid conditions — and it will retain its colour and shine for years.",
        },
        {
            "q": "How long does delivery take?",
            "a": "Delivery within Nairobi takes 1–2 business days. For destinations outside Nairobi (upcountry), delivery takes 2–5 business days depending on your location. We partner with reliable courier services to ensure your order arrives safely and on time. You will receive a tracking link once your order ships.",
        },
        {
            "q": "Can I pay on delivery (cash on delivery)?",
            "a": "Yes. We offer cash on delivery (M-Pesa or cash accepted) for all orders within Kenya. Simply select 'Cash on Delivery' at checkout, and pay when your watch arrives. For orders above Ksh 10,000, we may request a small deposit to confirm serious intent.",
        },
        {
            "q": "Can I exchange my watch if it does not fit or I do not like it?",
            "a": "Absolutely. We offer a 7-day exchange policy. If your watch does not meet your expectations — whether it is the size, style, or feel — you can exchange it for another timepiece of equal or lesser value. The watch must be unworn, in its original packaging, and returned within 7 days of delivery. Contact our support team to start the process.",
        },
        {
            "q": "Are your watches authentic or original?",
            "a": "We do not sell counterfeits. Every watch we list is a premium-quality piece sourced from verified distributors and trusted manufacturers. Our team inspects each unit before dispatch to ensure it meets our quality standards. We stand behind every watch we sell.",
        },
        {
            "q": "Do you offer warranty?",
            "a": "Yes. Every watch comes with a minimum 3-month warranty covering manufacturing defects such as movement failure, loose hands, or faulty crown operation. The warranty does not cover damage from water ingress (on non-diver watches), accidental drops, or normal strap wear. Extend your warranty to 12 months by registering your purchase on our site.",
        },
        {
            "q": "What if my watch stops working or gets damaged?",
            "a": "If your watch develops a fault within the warranty period, reach out to us and we will assess, repair, or replace it at no cost. Outside warranty, we offer affordable repair services — from battery replacement to strap adjustments and movement servicing. Just send us a message and we will guide you through the process.",
        },
        {
            "q": "Can I adjust the strap before delivery?",
            "a": "Yes. If you need your bracelet or strap sized before we ship, let us know your wrist measurement in centimetres during checkout, and we will adjust it for free. Most metal bracelets can be sized down to fit wrist circumferences between 15 cm and 20 cm.",
        },
        {
            "q": "Do you ship outside Kenya?",
            "a": "Currently we ship within Kenya only. International shipping is in our roadmap and will be announced soon. If you are based outside Kenya and are interested in a specific watch, reach out to us and we may be able to arrange a special delivery.",
        },
        {
            "q": "How do I clean and maintain my watch?",
            "a": "For metal bracelets and cases: use a soft toothbrush with mild soapy water, rinse gently, and dry with a lint-free cloth. For leather straps: wipe with a slightly damp cloth and let them air dry naturally — never soak leather. Avoid using alcohol-based cleaners. For water-resistant watches, rinse with fresh water after swimming in salt water or chlorine.",
        },
    ]
    return render(request, "faq.html", {"faqs": faqs, "theme": "unisex"})


def page(request, slug):
    pages = {
        "about": {
            "eyebrow": "About Wrist Hub",
            "title": "Curated timepieces for confident style.",
            "body": "Wrist Hub brings together classic, sport, luxury, and everyday watches selected for craftsmanship, comfort, and lasting design.",
        },
        "contact": {
            "eyebrow": "Contact Us",
            "title": "Need help choosing a watch?",
            "body": "Reach out to our team for sizing guidance, gift recommendations, order updates, or help finding the right timepiece.",
        },
        "login": {
            "eyebrow": "Account",
            "title": "Sign in to continue.",
            "body": "Account sign-in is ready to connect when authentication is enabled. You can still browse, add items to cart, and checkout as a guest.",
        },
        "register": {
            "eyebrow": "Account",
            "title": "Create your Wrist Hub account.",
            "body": "Registration will let returning customers track orders and save checkout details. Guest checkout is available now.",
        },
        "profile": {
            "eyebrow": "Profile",
            "title": "Your profile",
            "body": "Profile details will appear here once account authentication is enabled.",
        },
        "orders": {
            "eyebrow": "Your Orders",
            "title": "Track and review your watches.",
            "body": "Sign in to see your order history and follow the status of orders in progress.",
        },
    }
    page_data = pages.get(slug)
    if not page_data:
        raise Http404

    orders = []
    if slug == "orders":
        if request.user.is_authenticated:
            orders = list(
                Order.objects.filter(user=request.user)
                .prefetch_related("items__watch__brand", "items__watch__images")
                .order_by("-created_at")
            )
            for order in orders:
                _enrich_order(order)
            page_data = {
                **page_data,
                "body": "Track your current order and review everything you have bought from Wrist Hub.",
            }
        else:
            page_data = {
                **page_data,
                "body": "Sign in to see your order history and follow the status of orders in progress.",
            }

    return render(
        request,
        "page.html",
        {
            "page": page_data,
            "orders": orders,
            "theme": "unisex",
        },
    )


def journals_list(request):
    category_filter = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()

    journals = (
        Journal.objects.filter(is_published=True)
        .order_by("-published_at")
    )

    if category_filter:
        journals = journals.filter(category=category_filter)

    if query:
        journals = journals.filter(
            Q(title__icontains=query)
            | Q(excerpt__icontains=query)
            | Q(content__icontains=query)
            | Q(author__icontains=query)
        )

    featured_journals = journals.filter(is_featured=True)[:1]
    recent_journals = journals[:12]
    categories_list = [
        {"key": key, "label": label} for key, label in Journal.CATEGORY_CHOICES
    ]
    return render(
        request,
        "journals.html",
        {
            "featured_journals": featured_journals,
            "recent_journals": recent_journals,
            "categories": categories_list,
            "total_journals": journals.count(),
            "query": query,
            "category_filter": category_filter,
            "theme": "unisex",
        },
    )


def journal_detail(request, slug):
    journal = get_object_or_404(Journal, slug=slug, is_published=True)
    related_journals = (
        Journal.objects.filter(is_published=True, category=journal.category)
        .exclude(pk=journal.pk)
        .order_by("-published_at")[:3]
    )
    return render(
        request,
        "journal_detail.html",
        {
            "journal": journal,
            "related_journals": related_journals,
            "theme": "unisex",
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.cleaned_data["user"])
        messages.success(request, "Welcome back.")
        return redirect(request.GET.get("next") or "home")

    return render(request, "auth/login.html", {"form": form, "theme": "unisex"})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Your account has been created.")
        return redirect("home")
    return render(request, "auth/register.html", {"form": form, "theme": "unisex"})


def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect("home")
    return redirect("home")


def product_detail(request, slug):
    watch = get_object_or_404(
        Watch.objects.select_related("brand", "category")
        .prefetch_related("images"),
        slug=slug,
        is_active=True,
    )
    color_options = []
    seen_colors = set()
    for image in watch.images.all():
        color = (image.color or "").strip()
        color_key = color.casefold()
        if color and color_key not in seen_colors:
            seen_colors.add(color_key)
            color_options.append({"name": color, "key": color_key})

    related_watches = (
        Watch.objects.filter(is_active=True, category=watch.category)
        .exclude(pk=watch.pk)
        .select_related("brand", "category")
        .prefetch_related("images")
        .order_by("-created_at")[:4]
    )

    reviews = (
        ProductReview.objects.filter(watch=watch, is_approved=True)
        .select_related("user")
        .prefetch_related("replies__user", "likes")
        .order_by("-created_at")
    )

    user_review = None
    user_likes = set()
    has_purchased = False
    if request.user.is_authenticated:
        user_review = ProductReview.objects.filter(
            watch=watch, user=request.user
        ).first()
        user_likes = set(
            ReviewLike.objects.filter(
                review__in=reviews, user=request.user
            ).values_list("review_id", flat=True)
        )
        has_purchased = OrderItem.objects.filter(
            order__user=request.user,
            watch=watch,
            order__status__in=["delivered", "shipped", "processing", "paid"],
        ).exists()

    return render(
        request,
        "product_detail.html",
        {
            "watch": watch,
            "color_options": color_options,
            "related_watches": related_watches,
            "reviews": reviews,
            "user_review": user_review,
            "user_likes": user_likes,
            "has_purchased": has_purchased,
            "theme": watch.gender if watch.gender in ("men", "women") else "unisex",
        },
    )


def add_review(request, slug):
    watch = get_object_or_404(Watch, slug=slug, is_active=True)

    if request.method != "POST":
        return redirect("product-detail", slug=watch.slug)

    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to leave a review.")
        return redirect("login")

    has_purchased = OrderItem.objects.filter(
        order__user=request.user,
        watch=watch,
        order__status__in=["delivered", "shipped", "processing", "paid"],
    ).exists()

    if not has_purchased:
        messages.error(request, "You can only review watches you have purchased.")
        return redirect("product-detail", slug=watch.slug)

    rating = request.POST.get("rating", "").strip()
    content = request.POST.get("content", "").strip()

    if not rating or not content:
        messages.error(request, "Please provide both a rating and a review.")
        return redirect("product-detail", slug=watch.slug)

    try:
        rating_val = int(rating)
        if rating_val < 1 or rating_val > 5:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "Rating must be between 1 and 5.")
        return redirect("product-detail", slug=watch.slug)

    review, created = ProductReview.objects.get_or_create(
        watch=watch,
        user=request.user,
        defaults={"rating": rating_val, "content": content},
    )

    if not created:
        review.rating = rating_val
        review.content = content
        review.save(update_fields=["rating", "content", "updated_at"])

    try:
        from .email import send_review_notification_email
        send_review_notification_email(review)
    except Exception:
        pass

    messages.success(request, "Thank you! Your review has been submitted.")
    return redirect("product-detail", slug=watch.slug)


def add_reply(request, review_id):
    review = get_object_or_404(ProductReview, pk=review_id, is_approved=True)

    if request.method != "POST":
        return redirect("product-detail", slug=review.watch.slug)

    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to reply.")
        return redirect("login")

    has_purchased = OrderItem.objects.filter(
        order__user=request.user,
        watch=review.watch,
        order__status__in=["delivered", "shipped", "processing", "paid"],
    ).exists()

    if not has_purchased:
        messages.error(request, "You can only reply to reviews for watches you have purchased.")
        return redirect("product-detail", slug=review.watch.slug)

    content = request.POST.get("content", "").strip()
    if not content:
        messages.error(request, "Reply cannot be empty.")
        return redirect("product-detail", slug=review.watch.slug)

    ReviewReply.objects.create(
        review=review,
        user=request.user,
        content=content,
    )

    messages.success(request, "Your reply has been posted.")
    return redirect("product-detail", slug=review.watch.slug)


def like_review(request, review_id):
    review = get_object_or_404(ProductReview, pk=review_id, is_approved=True)

    if request.method != "POST":
        return redirect("product-detail", slug=review.watch.slug)

    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to like reviews.")
        return redirect("login")

    like, created = ReviewLike.objects.get_or_create(review=review, user=request.user)
    if not created:
        like.delete()
        messages.success(request, "Like removed.")
    else:
        messages.success(request, "Review liked!")

    return redirect("product-detail", slug=review.watch.slug)


def cart_add(request, watch_id):
    if request.method != "POST":
        return redirect("cart")

    watch = get_object_or_404(Watch, id=watch_id, is_active=True)
    cart = get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, watch=watch)
    if created:
        item.quantity = 1
    else:
        item.quantity = item.quantity + 1
    item.save()
    record_analytics_event(request, "cart_add", watch=watch)
    messages.success(request, f"Added {watch.name} to cart.")
    return redirect("cart")


def cart_update(request, item_id):
    if request.method != "POST":
        return redirect("cart")

    cart = get_or_create_cart(request)
    item = get_object_or_404(
        CartItem.objects.select_related("cart", "watch"),
        id=item_id,
        cart=cart,
    )
    action = request.POST.get("action")

    if action == "increase":
        item.quantity += 1
        item.save(update_fields=["quantity"])
    elif action == "decrease":
        if item.quantity > 1:
            item.quantity -= 1
            item.save(update_fields=["quantity"])
        else:
            item.delete()
            messages.success(request, "Item removed from cart.")
    elif action == "set":
        try:
            quantity = int(request.POST.get("quantity", "1"))
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid quantity.")
            return redirect("cart")

        if quantity <= 0:
            item.delete()
            messages.success(request, "Item removed from cart.")
        else:
            item.quantity = quantity
            item.save(update_fields=["quantity"])
    else:
        messages.error(request, "Invalid cart action.")

    return redirect("cart")


def cart_remove(request, item_id):
    if request.method != "POST":
        return redirect("cart")

    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect("cart")


def cart_clear(request):
    if request.method != "POST":
        return redirect("cart")

    cart = get_or_create_cart(request)
    cart.items.all().delete()
    messages.success(request, "Cart cleared.")
    return redirect("cart")


def cart_view(request):
    cart = get_or_create_cart(request)
    items = get_cart_items(cart)
    return render(
        request,
        "cart.html",
        {
            "cart": cart,
            "items": items,
            "cart_count": get_cart_count(cart),
            "theme": "unisex",
        },
    )


def cart_count(request):
    cart = get_or_create_cart(request)
    return JsonResponse({"count": get_cart_count(cart)})


def cart_checkout(request):
    cart = get_or_create_cart(request)
    items = get_cart_items(cart)
    initial = {}

    theme = "women"

    if request.user.is_authenticated:
        full_name = request.user.get_full_name()
        if full_name:
            initial["full_name"] = full_name
        if request.user.email:
            initial["email"] = request.user.email

    form = CheckoutForm(request.POST or None, initial=initial)

    if request.method == "POST":
        record_analytics_event(request, "checkout_start")

    if request.method == "POST" and form.is_valid():
        if not items:
            messages.error(request, "Your cart is empty.")
            return redirect("cart")

        total = sum(item.subtotal for item in items)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"],
                phone=form.cleaned_data["phone"],
                county=form.cleaned_data["county"],
                sub_county=form.cleaned_data["sub_county"],
                ward=form.cleaned_data.get("ward", ""),
                total=total,
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    watch=item.watch,
                    quantity=item.quantity,
                    price=item.watch.current_price,
                )
            cart.items.all().delete()

        record_analytics_event(request, "order_placed")
        request.session["last_order_id"] = order.pk

        try:
            email_sent = send_order_notification_email(order)
            if not email_sent:
                messages.warning(request, "Order placed, but the notification email could not be sent.")
            else:
                messages.success(request, "Order placed successfully. Confirmation email sent.")
        except Exception:
            logger = __import__("logging").getLogger(__name__)
            logger.exception("Order notification email failed for order %s", order.pk)
            messages.warning(request, "Order placed, but the notification email failed to send.")
        return redirect("order-confirmation", order_id=order.pk)

    return render(
        request,
        "checkout.html",
        {
            "cart": cart,
            "items": items,
            "form": form,
            "cart_count": get_cart_count(cart),
            "theme": theme,
        },
    )


def checkout_locations(request):
    return JsonResponse(get_location_data())


def order_confirmation(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__watch"),
        id=order_id,
    )
    last_order_id = request.session.get("last_order_id")

    if request.user.is_authenticated:
        if order.user_id != request.user.pk:
            raise Http404
    elif str(last_order_id) != str(order.pk):
        raise Http404

    return render(
        request,
        "order_confirmation.html",
        {
            "order": order,
            "theme": "unisex",
        },
    )


def gallery(request, category_slug=None):
    categories = GalleryCategory.objects.filter(is_active=True).order_by("name")
    selected_category = None
    if category_slug:
        selected_category = get_object_or_404(GalleryCategory, slug=category_slug, is_active=True)

    items = GalleryItem.objects.filter(is_published=True).select_related("category").order_by("-is_featured", "-created_at")
    if selected_category:
        items = items.filter(category=selected_category)

    return render(
        request,
        "gallery.html",
        {
            "categories": categories,
            "selected_category": selected_category,
            "items": items,
            "theme": "unisex",
        },
    )


def gallery_item(request, slug):
    item = get_object_or_404(GalleryItem, slug=slug, is_published=True)
    related_items = (
        GalleryItem.objects.filter(is_published=True, category=item.category)
        .exclude(pk=item.pk)
        .order_by("-created_at")[:6]
    )
    return render(
        request,
        "gallery_item.html",
        {
            "item": item,
            "related_items": related_items,
            "theme": "unisex",
        },
    )
