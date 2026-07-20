import logging
import urllib.parse

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def _build_absolute_url(path):
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    if not site_url:
        return path
    return f"{site_url}{path}"


def send_order_notification_email(order):
    items = list(order.items.select_related("watch__brand", "watch__category").all())
    if not items:
        return False

    watch_urls = []
    for item in items:
        watch = item.watch
        path = reverse("product-detail", kwargs={"slug": watch.slug})
        absolute_url = _build_absolute_url(path)
        qr_api_url = "https://api.qrserver.com/v1/create-qr-code/?size=96x96&data=" + urllib.parse.quote(absolute_url, safe="")
        watch_urls.append(
            {
                "watch": watch,
                "quantity": item.quantity,
                "price": item.price,
                "url": absolute_url,
                "qr_url": qr_api_url,
            }
        )

    context = {
        "order": order,
        "items": watch_urls,
        "customer_name": order.full_name,
    }

    try:
        html_body = render_to_string("emails/order_notification.html", context)
    except Exception as exc:
        logger.exception("Failed to render order notification email template: %s", exc)
        return False

    subject = f"New Order #{order.pk} — Wrist Hub"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = settings.ORDER_NOTIFICATION_EMAIL

    lines = [
        f"New Order #{order.pk} — Wrist Hub",
        "",
        f"Customer: {order.full_name}",
        f"Email: {order.email}",
        f"Phone: {order.phone}",
        f"Location: {order.county}, {order.sub_county or ''} {order.ward or ''}".strip(", "),
        f"Total: Ksh {order.total}",
        "",
        "Items:",
    ]
    for item in watch_urls:
        lines.append(
            f"- {item['watch'].brand.name} {item['watch'].name} x{item['quantity']} — Ksh {item['price']} — {item['url']}"
        )
    plain_body = "\n".join(lines)

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=from_email,
        to=[to_email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send(fail_silently=False)
        logger.info("Order notification email sent for order %s to %s", order.pk, to_email)
        return True
    except Exception as exc:
        logger.exception("Failed to send order notification email for order %s to %s: %s", order.pk, to_email, exc)
        return False


def send_review_notification_email(review):
    subject = f"New Product Review — {review.watch.brand.name} {review.watch.name}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = settings.ORDER_NOTIFICATION_EMAIL

    watch_url = _build_absolute_url(
        reverse("product-detail", kwargs={"slug": review.watch.slug})
    )

    plain_body = (
        f"New product review submitted.\n\n"
        f"Product: {review.watch.brand.name} {review.watch.name}\n"
        f"Rating: {review.rating}/5\n"
        f"Customer: {review.user.get_full_name() or review.user.username}\n"
        f"Review:\n{review.content}\n\n"
        f"View product: {watch_url}\n"
        f"Admin panel: {_build_absolute_url('/panel/')}"
    )

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #111;">
        <h2>New Product Review</h2>
        <p><strong>Product:</strong> {review.watch.brand.name} {review.watch.name}</p>
        <p><strong>Rating:</strong> {'★' * review.rating}{'☆' * (5 - review.rating)}</p>
        <p><strong>Customer:</strong> {review.user.get_full_name() or review.user.username}</p>
        <p><strong>Review:</strong></p>
        <p style="background:#f5f5f5;padding:14px;border-radius:8px;">{review.content}</p>
        <p><a href="{watch_url}">View Product</a> &nbsp;|&nbsp; <a href="{_build_absolute_url('/panel/')}">Admin Panel</a></p>
    </body>
    </html>
    """

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=from_email,
        to=[to_email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send(fail_silently=False)
        logger.info("Review notification email sent for review %s to %s", review.pk, to_email)
        return True
    except Exception as exc:
        logger.exception("Failed to send review notification email for review %s to %s: %s", review.pk, to_email, exc)
        return False


    watch_urls = []
    for item in items:
        watch = item.watch
        path = reverse("product-detail", kwargs={"slug": watch.slug})
        absolute_url = _build_absolute_url(path)
        qr_api_url = "https://api.qrserver.com/v1/create-qr-code/?size=96x96&data=" + urllib.parse.quote(absolute_url, safe="")
        watch_urls.append(
            {
                "watch": watch,
                "quantity": item.quantity,
                "price": item.price,
                "url": absolute_url,
                "qr_url": qr_api_url,
            }
        )

    context = {
        "order": order,
        "items": watch_urls,
        "customer_name": order.full_name,
    }

    try:
        html_body = render_to_string("emails/order_notification.html", context)
    except Exception as exc:
        logger.exception("Failed to render order notification email template: %s", exc)
        return False

    subject = f"New Order #{order.pk} — Wrist Hub"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = settings.ORDER_NOTIFICATION_EMAIL

    lines = [
        f"New Order #{order.pk} — Wrist Hub",
        "",
        f"Customer: {order.full_name}",
        f"Email: {order.email}",
        f"Phone: {order.phone}",
        f"Location: {order.county}, {order.sub_county or ''} {order.ward or ''}".strip(", "),
        f"Total: Ksh {order.total}",
        "",
        "Items:",
    ]
    for item in watch_urls:
        lines.append(
            f"- {item['watch'].brand.name} {item['watch'].name} x{item['quantity']} — Ksh {item['price']} — {item['url']}"
        )
    plain_body = "\n".join(lines)

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=from_email,
        to=[to_email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send(fail_silently=False)
        logger.info("Order notification email sent for order %s to %s", order.pk, to_email)
        return True
    except Exception as exc:
        logger.exception("Failed to send order notification email for order %s: %s", order.pk, exc)
        return False
