from django.urls import resolve
from django.utils import timezone

from .models import AnalyticsEvent, Watch


def get_visitor_key(request):
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    return f"session:{request.session.session_key or ''}"


def record_analytics_event(request, event_type, watch=None, path=None):
    if not request.session.session_key:
        request.session.create()

    resolved = None
    try:
        resolved = resolve(request.path)
    except Exception:
        resolved = None

    if watch is None and resolved and resolved.view_name == "product-detail":
        slug = resolved.kwargs.get("slug")
        if slug:
            watch = Watch.objects.filter(slug=slug, is_active=True).first()

    AnalyticsEvent.objects.create(
        event_type=event_type,
        session_key=request.session.session_key or "",
        user=request.user if request.user.is_authenticated else None,
        watch=watch,
        path=path or request.path,
        referrer=request.META.get("HTTP_REFERER", "")[:512],
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        ip_address=request.META.get("REMOTE_ADDR"),
    )


def should_track_request(request):
    if request.path.startswith(("/admin/", "/panel/", "/static/", "/media/")):
        return False
    if request.path in {"/cart/count/"}:
        return False
    if request.method not in {"GET", "POST"}:
        return False
    return True
