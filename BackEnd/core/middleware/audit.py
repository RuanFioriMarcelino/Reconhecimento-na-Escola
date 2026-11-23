import logging
import uuid

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _extract_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45]


class AuditMiddleware:
    """Enriquece requisições com rastreabilidade (Request ID, IP), segurança e resposta JSON em erros de API."""

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

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/"):
            return None
        request_id = getattr(request, "request_id", uuid.uuid4().hex[:16])
        logger.exception("Erro interno não tratado na API [request_id=%s path=%s]", request_id, request.path)
        payload = {
            "detail": "Erro interno no servidor. Tente novamente em instantes.",
            "requestId": request_id,
        }
        if settings.DEBUG:
            payload["debug"] = f"{type(exception).__name__}: {exception}"
        resp = JsonResponse(payload, status=500)
        resp["X-Request-ID"] = request_id
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp
