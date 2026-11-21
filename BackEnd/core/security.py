import functools
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

from .models import AuthToken, DispositivoPortaria, LogAuditoria, PerfilUsuario

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 300


def hash_secret(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def generate_secret(prefix: str = "tok") -> tuple[str, str, str]:
    """Gera segredo criptográfico aleatório: (raw_secret, prefixo_visivel, sha256_hex)."""
    raw = f"{prefix}_{secrets.token_urlsafe(32)}"
    return raw, raw[:12], hash_secret(raw)


def issue_auth_token(user, ip_address: str | None = None) -> tuple[str, AuthToken]:
    raw, prefix, digest = generate_secret("rne")
    ttl_hours = getattr(settings, "AUTH_TOKEN_TTL_HOURS", 12)
    token_obj = AuthToken.objects.create(
        user=user,
        token_hash=digest,
        prefixo=prefix,
        expira_em=timezone.now() + timedelta(hours=ttl_hours),
        ip_origem=ip_address or None,
    )
    return raw, token_obj


def get_user_perfil(user) -> dict:
    try:
        perfil = user.perfil
        return {"nome": perfil.nome_exibicao, "papel": perfil.papel}
    except PerfilUsuario.DoesNotExist:
        papel = "admin" if user.is_superuser else "coordenacao"
        nome = user.get_full_name() or user.first_name or user.username
        return {"nome": nome, "papel": papel}


def _rate_limit_key(ip: str, email: str) -> str:
    digest = hashlib.sha256(f"{ip}:{(email or '').strip().lower()}".encode("utf-8")).hexdigest()[:32]
    return f"login_fail:{digest}"


def check_login_rate_limit(ip: str, email: str) -> bool:
    """Retorna True se o login estiver permitido, False se bloqueado por excesso de falhas."""
    attempts = cache.get(_rate_limit_key(ip, email), 0)
    return attempts < LOGIN_MAX_FAILURES


def record_login_failure(ip: str, email: str) -> int:
    key = _rate_limit_key(ip, email)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, timeout=LOGIN_WINDOW_SECONDS)
    return attempts


def clear_login_failures(ip: str, email: str) -> None:
    cache.delete(_rate_limit_key(ip, email))


def registrar_auditoria(
    tabela: str,
    operacao: str,
    chave: str = "",
    usuario: str = "",
    ip: str | None = None,
    detalhes: dict | None = None,
    sensivel: bool = False,
) -> None:
    try:
        LogAuditoria.objects.create(
            tabela=tabela,
            operacao=operacao,
            chave=str(chave)[:100],
            usuario=str(usuario)[:150],
            ip_origem=ip or None,
            detalhes=detalhes or {},
            sensivel=sensivel,
        )
    except Exception:
        # Auditoria nunca deve quebrar rollback transacional ou resposta principal caso ocorra falha pontual
        pass


def require_auth(roles_or_func=None):
    """Decorator de autenticação por Bearer Token (AuthToken) ou sessão Django + RBAC."""
    roles = None if callable(roles_or_func) else set(roles_or_func or [])

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            user = None
            token_obj = None

            if auth_header.startswith("Bearer "):
                raw_token = auth_header[7:].strip()
                if raw_token:
                    digest = hash_secret(raw_token)
                    token_obj = (
                        AuthToken.objects.select_related("user")
                        .filter(token_hash=digest, revogado=False, expira_em__gt=timezone.now())
                        .first()
                    )
                    if token_obj and token_obj.user.is_active:
                        user = token_obj.user
                        token_obj.ultimo_uso_em = timezone.now()
                        token_obj.save(update_fields=["ultimo_uso_em"])

            if user is None and getattr(request, "user", None) is not None and request.user.is_authenticated:
                if request.user.is_active:
                    user = request.user

            if user is None:
                return JsonResponse({"detail": "Autenticação necessária. Faça login novamente."}, status=401)

            perfil = get_user_perfil(user)
            if roles and perfil["papel"] not in roles:
                return JsonResponse({"detail": "Sem permissão para executar esta operação."}, status=403)

            request.auth_user = user
            request.auth_token = token_obj
            request.auth_perfil = perfil
            return view_func(request, *args, **kwargs)

        return wrapper

    if callable(roles_or_func):
        return decorator(roles_or_func)
    return decorator


def require_device_auth(view_func):
    """Decorator exclusivo para terminais de portaria autenticados via X-Portaria-Key."""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        raw_key = (request.META.get("HTTP_X_PORTARIA_KEY") or "").strip()
        if not raw_key:
            return JsonResponse({"detail": "Cabeçalho X-Portaria-Key obrigatório."}, status=401)

        dispositivo = DispositivoPortaria.objects.filter(api_key_hash=hash_secret(raw_key), ativo=True).first()
        if dispositivo is None:
            return JsonResponse({"detail": "Chave de dispositivo inválida ou dispositivo desativado."}, status=401)

        ip = getattr(request, "client_ip", None) or request.META.get("REMOTE_ADDR")
        if ip and dispositivo.ip_ultimo_acesso != ip:
            dispositivo.ip_ultimo_acesso = ip
            dispositivo.save(update_fields=["ip_ultimo_acesso"])

        request.dispositivo = dispositivo
        return view_func(request, *args, **kwargs)

    return wrapper
