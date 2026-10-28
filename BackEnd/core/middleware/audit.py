from django.conf import settings


class AuditMiddleware:
    """Adds the API CORS contract; sensitive operations can be audited later."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            from django.http import HttpResponse
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        response["Access-Control-Allow-Origin"] = settings.FRONTEND_ORIGIN
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
        return response