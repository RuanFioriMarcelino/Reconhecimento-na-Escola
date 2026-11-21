import uuid


def _extract_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45]


class AuditMiddleware:
    """Enriquece requisições com rastreabilidade (Request ID, IP) e cabeçalhos de segurança."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex[:16]
        request.request_id = request_id
        request.client_ip = _extract_client_ip(request)

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        response["Permissions-Policy"] = "camera=(self)"
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
        return response
