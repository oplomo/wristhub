from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.forms import CharField, EmailField, Form
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .analytics import record_analytics_event
from .forms import LoginForm, RegisterForm
from .models import Brand, Category, HomeHero, Order, OrderItem, Watch, Cart, CartItem


PERSONALITIES = [
    {
        "slug": "executive",
        "title": "The Executive",
        "eyebrow": "Sharp and refined",
        "text": "Polished watches for meetings, milestones, and confident first impressions.",
        "category_slug": "dress",
    },
    {
        "slug": "adventurer",
        "title": "The Adventurer",
        "eyebrow": "Ready for anywhere",
        "text": "Durable pieces built for movement, weather, travel, and discovery.",
        "category_slug": "diver",
    },
    {
        "slug": "minimalist",
        "title": "The Minimalist",
        "eyebrow": "Quiet precision",
        "text": "Clean dials, slim cases, and timeless details without the noise.",
        "category_slug": "classic",
    },
    {
        "slug": "collector",
        "title": "The Collector",
        "eyebrow": "Curated taste",
        "text": "Distinctive watches for people who notice the craft behind every detail.",
        "category_slug": "luxury",
    },
    {
        "slug": "athlete",
        "title": "The Athlete",
        "eyebrow": "Performance minded",
        "text": "Sport-ready watches with practical features and everyday strength.",
        "category_slug": "sport",
    },
    {
        "slug": "trendsetter",
        "title": "The Trendsetter",
        "eyebrow": "Style forward",
        "text": "Bold watches made to stand out and finish the whole look.",
        "category_slug": "luxury",
    },
]


class CheckoutForm(Form):
    full_name = CharField(max_length=120)
    email = EmailField()
    phone = CharField(max_length=30)
    address = CharField(max_length=255)
    city = CharField(max_length=100)
    postal_code = CharField(max_length=20)
    country = CharField(max_length=100)


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
        if session_item.watch.stock <= 0:
            session_item.delete()
            continue
        user_item, created = CartItem.objects.get_or_create(cart=user_cart, watch=session_item.watch)
        if created:
            user_item.quantity = min(session_item.quantity, session_item.watch.stock or session_item.quantity)
        else:
            user_item.quantity = min(user_item.quantity + session_item.quantity, session_item.watch.stock or user_item.quantity + session_item.quantity)
        user_item.save()
        session_item.delete()


def get_cart_items(cart):
    items = list(
        cart.items.select_related("watch", "watch__brand", "watch__category")
        .prefetch_related("watch__images")
        .order_by("added_at")
    )
    for item in items:
        if item.watch.stock <= 0:
            item.delete()
        elif item.quantity > item.watch.stock:
            item.quantity = item.watch.stock
            item.save(update_fields=["quantity"])
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
    personalities = []

    for personality in PERSONALITIES:
        personalities.append({
            **personality,
            "category": categories.get(personality["category_slug"]),
        })

    featured_watches = (
        Watch.objects.filter(is_active=True, featured=True)
        .select_related("brand", "category")
        .prefetch_related("images")
        .order_by("-price")[:3]
    )

    return render(
        request,
        "home.html",
        {
            "hero": hero,
            "personalities": personalities,
            "recent_watches": recent_watches,
            "featured_watches": featured_watches,
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
        },
    )


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
            "eyebrow": "Orders",
            "title": "Order history",
            "body": "Your recent orders will appear here once account authentication is enabled.",
        },
    }
    page_data = pages.get(slug)
    if not page_data:
        raise Http404

    orders = []
    if slug == "orders" and request.user.is_authenticated:
        orders = Order.objects.filter(user=request.user).prefetch_related("items__watch").order_by("-created_at")[:10]
        page_data = {
            **page_data,
            "body": "Here are your most recent Wrist Hub orders.",
        }

    return render(
        request,
        "page.html",
        {
            "page": page_data,
            "orders": orders,
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

    return render(request, "auth/login.html", {"form": form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Your account has been created.")
        return redirect("home")

    return render(request, "auth/register.html", {"form": form})


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
    related_watches = (
        Watch.objects.filter(is_active=True, category=watch.category)
        .exclude(pk=watch.pk)
        .select_related("brand", "category")
        .prefetch_related("images")
        .order_by("-created_at")[:4]
    )
    return render(
        request,
        "product_detail.html",
        {
            "watch": watch,
            "related_watches": related_watches,
        },
    )


def cart_add(request, watch_id):
    if request.method != "POST":
        return redirect("cart")

    watch = get_object_or_404(Watch, id=watch_id, is_active=True)
    if not watch.in_stock:
        messages.error(request, f"{watch.name} is currently out of stock.")
        return redirect("cart")

    cart = get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, watch=watch)
    if created:
        item.quantity = 1
    else:
        item.quantity = min(item.quantity + 1, watch.stock)
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
        if item.watch.stock <= 0:
            messages.error(request, f"{item.watch.name} is currently out of stock.")
        elif item.quantity < item.watch.stock:
            item.quantity += 1
            item.save(update_fields=["quantity"])
        else:
            messages.warning(request, f"Only {item.watch.stock} available for {item.watch.name}.")
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
        elif quantity > item.watch.stock:
            messages.warning(request, f"Only {item.watch.stock} available for {item.watch.name}.")
            item.quantity = item.watch.stock
            item.save(update_fields=["quantity"])
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
        },
    )


def cart_count(request):
    cart = get_or_create_cart(request)
    return JsonResponse({"count": get_cart_count(cart)})


def cart_checkout(request):
    cart = get_or_create_cart(request)
    items = get_cart_items(cart)
    initial = {}

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

        for item in items:
            if item.quantity > item.watch.stock or item.watch.stock <= 0:
                messages.error(request, f"{item.watch.name} is no longer available in the requested quantity.")
                return redirect("cart")

        total = sum(item.subtotal for item in items)

        try:
            with transaction.atomic():
                for item in items:
                    updated = Watch.objects.filter(pk=item.watch_id, stock__gte=item.quantity).update(
                        stock=F("stock") - item.quantity
                    )
                    if not updated:
                        raise ValidationError("Stock changed during checkout.")

                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    full_name=form.cleaned_data["full_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    address=form.cleaned_data["address"],
                    city=form.cleaned_data["city"],
                    postal_code=form.cleaned_data["postal_code"],
                    country=form.cleaned_data["country"],
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
        except ValidationError:
            messages.error(request, "Stock changed during checkout. Please review your cart.")
            return redirect("cart")

        record_analytics_event(request, "order_placed")
        request.session["last_order_id"] = order.pk
        messages.success(request, "Order placed successfully.")
        return redirect("order-confirmation", order_id=order.pk)

    return render(
        request,
        "checkout.html",
        {
            "cart": cart,
            "items": items,
            "form": form,
            "cart_count": get_cart_count(cart),
        },
    )


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
        {"order": order},
    )
