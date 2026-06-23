from django.urls import resolve

from wshop.analytics import record_analytics_event, should_track_request


class AnalyticsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if should_track_request(request) and request.method == "GET" and response.status_code < 400:
            try:
                record_analytics_event(request, "page_view")
                resolved = resolve(request.path)
                if resolved.view_name == "product-detail":
                    record_analytics_event(request, "product_view")
            except Exception:
                pass
        return response
