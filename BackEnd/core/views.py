import csv
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Exists, Max, OuterRef, Q, Subquery
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .crypto.cipher import blind_index, encrypt_text
from .crypto.fields import clean_str, normalize_digits
from .models import (
    Alerta,
    Aluno,
    ConfiguracaoEscola,
    DadoBiometrico,
    DispositivoPortaria,
    Funcionario,
    LogAuditoria,
    RegistroAcesso,
    RelAlunoResponsavel,
    Responsavel,
    Turma,
    Turno,
)
from .security import (
    check_login_rate_limit,
    clear_login_failures,
    generate_secret,
    issue_auth_token,
    record_login_failure,
    registrar_auditoria,
    require_auth,
    require_device_auth,
)
from .services.access_service import get_school_config, processar_passagem
from .services.biometrics import BiometricValidationError, enroll_person_biometrics, get_active_gallery

WEEKDAY_NAMES = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _json_body(request) -> dict:
    if not request.body:
        return {}
    max_json = getattr(settings, "JSON_BODY_MAX_BYTES", 256 * 1024)
    if len(request.body) > max_json:
        raise ValueError("Corpo da requisição JSON excede o limite permitido.")
    body = json.loads(request.body)
    if not isinstance(body, dict):
        raise ValueError("O corpo deve ser um objeto JSON.")
    return body


def _parse_pagination(request, default_size: int = 24, max_size: int = 100) -> tuple[int, int, int]:
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size", default_size))
    except (TypeError, ValueError):
        page_size = default_size
    page_size = max(1, min(max_size, page_size))
    return page, page_size, (page - 1) * page_size


def _pagination_meta(page: int, page_size: int, total: int) -> dict:
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
    return {
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "hasNext": page < total_pages,
        "hasPrev": page > 1,
    }


def _start_of_local_today() -> datetime:
    local_today = timezone.localdate()
    return timezone.make_aware(datetime.combine(local_today, time.min), timezone.get_current_timezone())


def _find_person(person_ref):
    raw = str(person_ref).strip()
    if raw.startswith("aluno-"):
        pk = int(raw.split("-", 1)[1])
        return Aluno.objects.select_related("turma_ref", "turno_ref").get(pk=pk), "aluno"
    if raw.startswith("funcionario-"):
        pk = int(raw.split("-", 1)[1])
        return Funcionario.objects.select_related("turno_ref").get(pk=pk), "funcionario"
    num = int(raw)
    if num >= 10000:
        return Funcionario.objects.select_related("turno_ref").get(pk=num - 10000), "funcionario"
    return Aluno.objects.select_related("turma_ref", "turno_ref").get(pk=num), "aluno"


def _bio_map() -> dict[tuple[str, int], float]:
    result = {}
    for row in DadoBiometrico.objects.filter(ativo=True).values("aluno_id", "funcionario_id", "qualidade"):
        if row["aluno_id"]:
            result[("aluno", row["aluno_id"])] = float(row["qualidade"])
        elif row["funcionario_id"]:
            result[("funcionario", row["funcionario_id"])] = float(row["qualidade"])
    return result


def _present_today_set() -> set[tuple[str, int]]:
    """Usa PostgreSQL DISTINCT ON para obter em O(1) por pessoa quem está dentro da escola agora."""
    start_of_day = _start_of_local_today()
    present: set[tuple[str, int]] = set()

    for aluno_id, tipo in (
        RegistroAcesso.objects.filter(data_hora__gte=start_of_day, aluno__isnull=False)
        .order_by("aluno_id", "-data_hora", "-id")
        .distinct("aluno_id")
        .values_list("aluno_id", "tipo")
    ):
        if tipo == RegistroAcesso.Tipo.ENTRADA:
            present.add(("aluno", aluno_id))

    for func_id, tipo in (
        RegistroAcesso.objects.filter(data_hora__gte=start_of_day, funcionario__isnull=False)
        .order_by("funcionario_id", "-data_hora", "-id")
        .distinct("funcionario_id")
        .values_list("funcionario_id", "tipo")
    ):
        if tipo == RegistroAcesso.Tipo.ENTRADA:
            present.add(("funcionario", func_id))

    return present


def _person(
    person,
    tipo: str,
    bio_map: dict | None = None,
    present_set: set | None = None,
    has_bio_override: bool | None = None,
    bio_qualidade_override: float | None = None,
) -> dict:
    funcionario = tipo == "funcionario"
    key = (tipo, person.pk)

    if has_bio_override is not None:
        bio_ok = bool(has_bio_override)
        bio_qual = float(bio_qualidade_override) if bio_qualidade_override is not None else None
    else:
        bio_map = bio_map if bio_map is not None else _bio_map()
        bio_ok = key in bio_map
        bio_qual = bio_map.get(key)

    if present_set is None:
        present_set = _present_today_set()

    date_val = person.data_admissao if funcionario else person.data_nascimento

    return {
        "id": f"{tipo}-{person.pk}",
        "realId": person.pk,
        "tipo": tipo,
        "nome": person.nome,
        "documento": person.documento,
        "grupo": person.cargo if funcionario else person.turma,
        "turmaId": None if funcionario else person.turma_ref_id,
        "turno": person.turno,
        "status": person.status,
        "contatoNome": person.contato_nome,
        "contatoTelefone": person.contato_telefone,
        "dataCadastro": timezone.localtime(person.criado_em).strftime("%d/%m/%Y"),
        "dataRef": date_val.strftime("%d/%m/%Y") if date_val else "—",
        "consentimentoBiometrico": bool(person.consentimento_biometrico),
        "consentimentoEm": person.consentimento_em.isoformat() if person.consentimento_em else None,
        "biometriaCadastrada": bio_ok,
        "biometriaQualidade": bio_qual,
        "presenteAgora": key in present_set,
    }


def _serialize_log(item: RegistroAcesso) -> dict:
    person = item.funcionario or item.aluno
    tipo = "funcionario" if item.funcionario_id else ("aluno" if item.aluno_id else None)
    uid = f"{tipo}-{person.pk}" if person and tipo else None
    grupo = person.cargo if item.funcionario_id and person else (person.turma if item.aluno_id and person else None)
    local_time = timezone.localtime(item.data_hora)
    return {
        "id": item.pk,
        "personId": uid,
        "tipo": item.tipo,
        "horaMin": local_time.hour * 60 + local_time.minute,
        "status": item.status,
        "local": item.portal,
        "confianca": float(item.confianca) if item.confianca is not None else None,
        "incidente": item.incidente,
        "dataHora": item.data_hora.isoformat(),
        "dataDia": local_time.strftime("%d/%m/%Y"),
        "personType": tipo,
        "personName": person.nome if person else None,
        "personGrupo": grupo,
    }


def _enrich_alerts(alert_items: list[Alerta]) -> list[dict]:
    """Resolve nomes e grupos dos titulares de alertas em apenas 2 queries batch (in_bulk)."""
    aluno_ids = [a.pessoa_id for a in alert_items if a.pessoa_tipo == "aluno" and a.pessoa_id]
    func_ids = [a.pessoa_id for a in alert_items if a.pessoa_tipo == "funcionario" and a.pessoa_id]

    alunos_map = Aluno.objects.in_bulk(aluno_ids) if aluno_ids else {}
    funcs_map = Funcionario.objects.in_bulk(func_ids) if func_ids else {}

    serialized = []
    for item in alert_items:
        p_name = None
        p_grupo = None
        if item.pessoa_tipo == "aluno" and item.pessoa_id in alunos_map:
            obj = alunos_map[item.pessoa_id]
            p_name = obj.nome
            p_grupo = obj.turma
        elif item.pessoa_tipo == "funcionario" and item.pessoa_id in funcs_map:
            obj = funcs_map[item.pessoa_id]
            p_name = obj.nome
            p_grupo = obj.cargo

        serialized.append({
            "id": item.pk,
            "personId": f"{item.pessoa_tipo}-{item.pessoa_id}" if item.pessoa_tipo and item.pessoa_id else None,
            "personType": item.pessoa_tipo or None,
            "personName": p_name,
            "personGrupo": p_grupo,
            "tipo": item.tipo,
            "descricao": item.descricao,
            "severidade": item.severidade,
            "status": item.status,
            "observacao": item.observacao,
            "criadoEm": item.criado_em.isoformat(),
            "resolvidoEm": item.resolvido_em.isoformat() if item.resolvido_em else None,
            "resolvidoPor": item.resolvido_por.first_name or item.resolvido_por.username if item.resolvido_por else None,
        })
    return serialized


def _settings_dict(cfg: ConfiguracaoEscola) -> dict:
    return {
        "nomeEscola": cfg.nome_escola,
        "notifAtraso": cfg.notif_atraso,
        "notifAusencia": cfg.notif_ausencia,
        "notifNaoReconhecido": cfg.notif_nao_reconhecido,
        "notifSaidaAntecipada": cfg.notif_saida_antecipada,
        "limiteManha": cfg.limite_manha,
        "limiteTarde": cfg.limite_tarde,
        "saidaManha": cfg.saida_manha,
        "saidaTarde": cfg.saida_tarde,
        "cooldownSegundos": cfg.cooldown_segundos,
        "tempoMinimoPermanenciaMin": cfg.tempo_minimo_permanencia_min,
        "limiarConfianca": float(cfg.limiar_confianca),
        "retencaoLogsDias": cfg.retencao_logs_dias,
        "modoPassivo": cfg.modo_passivo,
    }


def _device_dict(dev: DispositivoPortaria) -> dict:
    now = timezone.now()
    online = bool(dev.ativo and dev.ultimo_heartbeat and (now - dev.ultimo_heartbeat).total_seconds() <= 90)
    return {
        "id": dev.pk,
        "nome": dev.nome,
        "portal": dev.portal,
        "sentidoPadrao": dev.sentido_padrao,
        "apiKeyPrefixo": dev.api_key_prefixo,
        "ativo": dev.ativo,
        "online": online,
        "ultimoHeartbeat": dev.ultimo_heartbeat.isoformat() if dev.ultimo_heartbeat else None,
        "ipUltimoAcesso": dev.ip_ultimo_acesso,
        "telemetria": dev.telemetria or {},
    }


def _analytics(alunos_ativos: int) -> dict:
    """Agrega frequência dos últimos 5 dias úteis diretamente no PostgreSQL via TruncDate + COUNT DISTINCT."""
    local_today = timezone.localdate()
    weekdays: list[date] = []
    cursor = local_today
    while len(weekdays) < 5:
        if cursor.weekday() < 5:
            weekdays.append(cursor)
        cursor -= timedelta(days=1)
    weekdays.reverse()

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(weekdays[0], time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(local_today, time.max), tz)

    by_day_rows = (
        RegistroAcesso.objects.filter(
            data_hora__gte=start_dt,
            data_hora__lte=end_dt,
            aluno__isnull=False,
            tipo=RegistroAcesso.Tipo.ENTRADA,
        )
        .annotate(dia=TruncDate("data_hora", tzinfo=tz))
        .values("dia")
        .annotate(presentes=Count("aluno_id", distinct=True))
    )
    by_day = {row["dia"]: row["presentes"] for row in by_day_rows}

    today_start = timezone.make_aware(datetime.combine(local_today, time.min), tz)
    today_agg = RegistroAcesso.objects.filter(data_hora__gte=today_start).aggregate(
        total=Count("id"),
        reconhecidos=Count("id", filter=~Q(status=RegistroAcesso.Status.NAO_RECONHECIDO)),
    )
    today_total = today_agg["total"] or 0
    today_recognized = today_agg["reconhecidos"] or 0

    semana = []
    for d in weekdays:
        presentes = by_day.get(d, 0)
        pct = round((presentes / alunos_ativos) * 100) if alunos_ativos > 0 else 0
        semana.append({
            "dia": f"{WEEKDAY_NAMES[d.weekday()]} {d.strftime('%d/%m')}",
            "curto": WEEKDAY_NAMES[d.weekday()],
            "presentes": presentes,
            "pct": min(100, pct),
        })

    taxa_rec = round((today_recognized / today_total) * 100) if today_total > 0 else 100
    return {
        "semana": semana,
        "taxaReconhecimentoHoje": taxa_rec,
        "eventosHoje": today_total,
    }


def _dashboard_summary() -> dict:
    """Agrega KPIs, estatísticas por turma, últimos eventos e cursores sem carregar tabelas inteiras."""
    start_of_day = _start_of_local_today()
    present_set = _present_today_set()

    alunos_ativos = Aluno.objects.filter(status="ativo").count()
    funcionarios_ativos = Funcionario.objects.filter(status="ativo").count()

    na_escola_alunos = sum(1 for tipo, _ in present_set if tipo == "aluno")
    today_logs_qs = RegistroAcesso.objects.filter(data_hora__gte=start_of_day)

    logs_agg = today_logs_qs.aggregate(
        entraram_alunos=Count("aluno_id", distinct=True, filter=Q(aluno__isnull=False, tipo="entrada", aluno__status="ativo")),
        atrasos_alunos=Count("id", filter=Q(aluno__isnull=False, status="atraso", aluno__status="ativo")),
        presentes_func=Count("funcionario_id", distinct=True, filter=Q(funcionario__isnull=False, tipo="entrada", funcionario__status="ativo")),
        atrasos_func=Count("id", filter=Q(funcionario__isnull=False, status="atraso", funcionario__status="ativo")),
    )
    entraram_alunos = logs_agg["entraram_alunos"] or 0
    alertas_ativos = Alerta.objects.exclude(status=Alerta.Status.RESOLVIDO).count()

    # Estatísticas agregadas por turma
    alunos_por_turma = {
        row["turma"]: row["total"]
        for row in Aluno.objects.filter(status="ativo").values("turma").annotate(total=Count("id"))
    }
    presentes_por_turma = {
        row["aluno__turma"]: row["presentes"]
        for row in today_logs_qs.filter(aluno__isnull=False, aluno__status="ativo", tipo="entrada")
        .values("aluno__turma")
        .annotate(presentes=Count("aluno_id", distinct=True))
    }
    atrasos_por_turma = {
        row["aluno__turma"]: row["atrasos"]
        for row in today_logs_qs.filter(aluno__isnull=False, aluno__status="ativo", status="atraso")
        .values("aluno__turma")
        .annotate(atrasos=Count("aluno_id", distinct=True))
    }

    turmas_db = list(Turma.objects.select_related("turno").filter(ativo=True))
    turma_names = [t.nome for t in turmas_db] or sorted(alunos_por_turma.keys())
    turma_stats = []
    for nome in turma_names:
        total_t = alunos_por_turma.get(nome, 0)
        pres_t = presentes_por_turma.get(nome, 0)
        atr_t = atrasos_por_turma.get(nome, 0)
        pct = round((pres_t / total_t) * 100) if total_t > 0 else 0
        turma_stats.append({
            "turma": nome,
            "alunosAtivos": total_t,
            "presentesHoje": pres_t,
            "ausentesHoje": max(0, total_t - pres_t),
            "atrasosHoje": atr_t,
            "pct": pct,
        })

    recentes = [
        _serialize_log(item)
        for item in RegistroAcesso.objects.select_related("aluno", "funcionario").order_by("-data_hora", "-id")[:8]
    ]
    abertos_qs = list(
        Alerta.objects.select_related("resolvido_por")
        .exclude(status=Alerta.Status.RESOLVIDO)
        .order_by("-criado_em")[:3]
    )
    abertos = _enrich_alerts(abertos_qs)

    last_log_id = RegistroAcesso.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    last_alert_id = Alerta.objects.aggregate(max_id=Max("id"))["max_id"] or 0

    return {
        "summary": {
            "alunosAtivos": alunos_ativos,
            "funcionariosAtivos": funcionarios_ativos,
            "naEscolaAlunos": na_escola_alunos,
            "entraramHojeAlunos": entraram_alunos,
            "ausentesHojeAlunos": max(0, alunos_ativos - entraram_alunos),
            "atrasosHojeAlunos": logs_agg["atrasos_alunos"] or 0,
            "presentesHojeFuncionarios": logs_agg["presentes_func"] or 0,
            "atrasosHojeFuncionarios": logs_agg["atrasos_func"] or 0,
            "alertasAtivos": alertas_ativos,
        },
        "turmaStats": turma_stats,
        "recentes": recentes,
        "abertos": abertos,
        "analytics": _analytics(alunos_ativos),
        "dispositivos": [_device_dict(d) for d in DispositivoPortaria.objects.all()],
        "cursor": {"lastLogId": last_log_id, "lastAlertId": last_alert_id},
    }


def _actor_name(request) -> str:
    user = getattr(request, "auth_user", None)
    return user.username if user else "sistema"


@require_http_methods(["GET"])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "database": "ok", "version": "2.0.0"})
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable", "version": "2.0.0"}, status=503)


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    try:
        body = _json_body(request)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)

    email = clean_str(body.get("email"), 150).lower()
    senha = body.get("senha") or ""
    if not email or not senha:
        return JsonResponse({"detail": "E-mail e senha são obrigatórios."}, status=400)

    ip = getattr(request, "client_ip", "") or request.META.get("REMOTE_ADDR", "")
    if not check_login_rate_limit(ip, email):
        registrar_auditoria("auth_token", "AUTH", chave=email, usuario=email, ip=ip, detalhes={"status": "rate_limited"}, sensivel=True)
        return JsonResponse({"detail": "Muitas tentativas inválidas. Aguarde 5 minutos para tentar novamente."}, status=429)

    user = authenticate(request, username=email, password=senha)
    if user is None or not user.is_active:
        record_login_failure(ip, email)
        registrar_auditoria("auth_token", "AUTH", chave=email, usuario=email, ip=ip, detalhes={"status": "failed"}, sensivel=True)
        return JsonResponse({"detail": "E-mail ou senha inválidos."}, status=401)

    clear_login_failures(ip, email)
    auth_login(request, user)
    raw_token, token_obj = issue_auth_token(user, ip_address=ip)
    from .security import get_user_perfil

    perfil = get_user_perfil(user)
    registrar_auditoria(
        "auth_token",
        "AUTH",
        chave=token_obj.prefixo,
        usuario=user.username,
        ip=ip,
        detalhes={"status": "success", "papel": perfil["papel"]},
        sensivel=False,
    )
    return JsonResponse({
        "token": raw_token,
        "expiresAt": token_obj.expira_em.isoformat(),
        "user": {
            "id": user.pk,
            "email": user.username,
            "nome": perfil["nome"],
            "papel": perfil["papel"],
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
@require_auth
def logout(request):
    token_obj = getattr(request, "auth_token", None)
    if token_obj is not None:
        token_obj.revogado = True
        token_obj.save(update_fields=["revogado"])
    ip = getattr(request, "client_ip", None)
    registrar_auditoria("auth_token", "AUTH", chave="logout", usuario=_actor_name(request), ip=ip, detalhes={"status": "logout"})
    auth_logout(request)
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
@require_auth
def me(request):
    user = request.auth_user
    perfil = request.auth_perfil
    return JsonResponse({
        "user": {
            "id": user.pk,
            "email": user.username,
            "nome": perfil["nome"],
            "papel": perfil["papel"],
        }
    })


@require_http_methods(["GET"])
@require_auth
def bootstrap(request):
    cfg = get_school_config()
    last_log_id = RegistroAcesso.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    last_alert_id = Alerta.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    open_alerts = Alerta.objects.exclude(status=Alerta.Status.RESOLVIDO).count()

    payload = {
        "turmas": [
            {
                "id": turma.id,
                "nome": turma.nome,
                "anoLetivo": turma.ano_letivo,
                "turnoId": turma.turno_id,
                "turno": turma.turno.nome,
            }
            for turma in Turma.objects.select_related("turno").filter(ativo=True)
        ],
        "turnos": [
            {
                "id": turno.id,
                "nome": turno.nome,
                "inicio": turno.inicio.strftime("%H:%M"),
                "limiteEntrada": turno.limite_entrada.strftime("%H:%M"),
                "termino": turno.termino.strftime("%H:%M") if turno.termino else None,
                "limiteSaidaAntecipada": turno.limite_saida_antecipada.strftime("%H:%M")
                if turno.limite_saida_antecipada
                else None,
            }
            for turno in Turno.objects.filter(ativo=True)
        ],
        "dispositivos": [_device_dict(dev) for dev in DispositivoPortaria.objects.all()],
        "settings": _settings_dict(cfg),
        "openAlertsCount": open_alerts,
        "cursor": {"lastLogId": last_log_id, "lastAlertId": last_alert_id},
    }

    if request.GET.get("full") == "1":
        bio_map = _bio_map()
        present_set = _present_today_set()
        alunos = list(Aluno.objects.select_related("turma_ref", "turno_ref").all()[:200])
        funcionarios = list(Funcionario.objects.select_related("turno_ref").all()[:200])
        people_list = [_person(p, "aluno", bio_map, present_set) for p in alunos]
        people_list += [_person(p, "funcionario", bio_map, present_set) for p in funcionarios]
        logs_list = [
            _serialize_log(item)
            for item in reversed(list(RegistroAcesso.objects.select_related("aluno", "funcionario").order_by("-data_hora", "-id")[:200]))
        ]
        alerts_list = _enrich_alerts(list(Alerta.objects.select_related("resolvido_por").all()[:100]))
        payload.update({
            "people": people_list,
            "logs": logs_list,
            "alerts": alerts_list,
            "analytics": _analytics(Aluno.objects.filter(status="ativo").count()),
        })

    return JsonResponse(payload)


@require_http_methods(["GET"])
@require_auth
def dashboard(request):
    return JsonResponse(_dashboard_summary())


@require_http_methods(["GET"])
@require_auth
def live_updates(request):
    """Endpoint incremental leve para tempo real (~250 bytes quando não há eventos novos)."""
    try:
        since_log_id = max(0, int(request.GET.get("since_log_id", 0)))
    except (TypeError, ValueError):
        since_log_id = 0
    try:
        since_alert_id = max(0, int(request.GET.get("since_alert_id", 0)))
    except (TypeError, ValueError):
        since_alert_id = 0

    max_log_id = RegistroAcesso.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    max_alert_id = Alerta.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    open_alerts = Alerta.objects.exclude(status=Alerta.Status.RESOLVIDO).count()
    dispositivos = [_device_dict(d) for d in DispositivoPortaria.objects.all()]

    has_new_logs = max_log_id > since_log_id
    has_new_alerts = max_alert_id > since_alert_id

    if not has_new_logs and not has_new_alerts:
        return JsonResponse({
            "changed": False,
            "lastLogId": max_log_id,
            "lastAlertId": max_alert_id,
            "openAlertsCount": open_alerts,
            "dispositivos": dispositivos,
            "newLogs": [],
            "newAlerts": [],
        })

    new_logs = []
    if has_new_logs:
        new_logs = [
            _serialize_log(item)
            for item in RegistroAcesso.objects.select_related("aluno", "funcionario")
            .filter(id__gt=since_log_id)
            .order_by("id")[:50]
        ]

    new_alerts = []
    if has_new_alerts:
        alert_objs = list(
            Alerta.objects.select_related("resolvido_por")
            .filter(id__gt=since_alert_id)
            .order_by("id")[:30]
        )
        new_alerts = _enrich_alerts(alert_objs)

    return JsonResponse({
        "changed": True,
        "lastLogId": max_log_id,
        "lastAlertId": max_alert_id,
        "openAlertsCount": open_alerts,
        "dispositivos": dispositivos,
        "newLogs": new_logs,
        "newAlerts": new_alerts,
    })


@require_http_methods(["GET"])
@require_auth
def logs_list(request):
    page, page_size, offset = _parse_pagination(request, default_size=25, max_size=100)
    qs = RegistroAcesso.objects.select_related("aluno", "funcionario").order_by("-data_hora", "-id")

    search = clean_str(request.GET.get("search"), 100)
    if search:
        qs = qs.filter(
            Q(aluno__nome__icontains=search)
            | Q(funcionario__nome__icontains=search)
            | Q(portal__icontains=search)
        )

    tipo_pessoa = clean_str(request.GET.get("tipo_pessoa"), 20)
    if tipo_pessoa == "aluno":
        qs = qs.filter(aluno__isnull=False)
    elif tipo_pessoa == "funcionario":
        qs = qs.filter(funcionario__isnull=False)

    tipo_evento = clean_str(request.GET.get("tipo_evento"), 20)
    if tipo_evento in {"entrada", "saida"}:
        qs = qs.filter(tipo=tipo_evento)

    status = clean_str(request.GET.get("status"), 30)
    if status in {"reconhecido", "atraso", "saida-antecipada", "nao-reconhecido"}:
        qs = qs.filter(status=status)

    portal = clean_str(request.GET.get("portal"), 100)
    if portal:
        qs = qs.filter(portal=portal)

    de = clean_str(request.GET.get("de"), 12)
    ate = clean_str(request.GET.get("ate"), 12)
    try:
        if de:
            qs = qs.filter(data_hora__gte=timezone.make_aware(datetime.combine(date.fromisoformat(de), time.min)))
        if ate:
            qs = qs.filter(data_hora__lte=timezone.make_aware(datetime.combine(date.fromisoformat(ate), time.max)))
    except ValueError:
        return JsonResponse({"detail": "Parâmetros 'de' e 'ate' devem usar formato YYYY-MM-DD."}, status=400)

    total = qs.count()
    items = [_serialize_log(item) for item in qs[offset : offset + page_size]]
    last_log_id = RegistroAcesso.objects.aggregate(max_id=Max("id"))["max_id"] or 0

    return JsonResponse({
        "items": items,
        "pagination": _pagination_meta(page, page_size, total),
        "lastLogId": last_log_id,
    })


@require_http_methods(["GET"])
@require_auth
def alerts_list(request):
    page, page_size, offset = _parse_pagination(request, default_size=20, max_size=100)
    qs = Alerta.objects.select_related("resolvido_por").all()

    status = clean_str(request.GET.get("status"), 20)
    if status == "abertos":
        qs = qs.exclude(status=Alerta.Status.RESOLVIDO)
    elif status in {Alerta.Status.NOVO, Alerta.Status.EM_ANALISE, Alerta.Status.RESOLVIDO}:
        qs = qs.filter(status=status)

    severidade = clean_str(request.GET.get("severidade"), 20)
    if severidade in {Alerta.Severidade.ALTA, Alerta.Severidade.MEDIA, Alerta.Severidade.BAIXA}:
        qs = qs.filter(severidade=severidade)

    total = qs.count()
    page_items = list(qs[offset : offset + page_size])
    items = _enrich_alerts(page_items)
    open_count = Alerta.objects.exclude(status=Alerta.Status.RESOLVIDO).count()
    last_alert_id = Alerta.objects.aggregate(max_id=Max("id"))["max_id"] or 0

    return JsonResponse({
        "items": items,
        "pagination": _pagination_meta(page, page_size, total),
        "openCount": open_count,
        "lastAlertId": last_alert_id,
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
@require_auth
def classes(request):
    if request.method == "GET":
        return JsonResponse({
            "turmas": [
                {
                    "id": item.id,
                    "nome": item.nome,
                    "anoLetivo": item.ano_letivo,
                    "turnoId": item.turno_id,
                    "turno": item.turno.nome,
                }
                for item in Turma.objects.select_related("turno").filter(ativo=True)
            ],
            "turnos": [
                {
                    "id": item.id,
                    "nome": item.nome,
                    "inicio": item.inicio.strftime("%H:%M"),
                    "limiteEntrada": item.limite_entrada.strftime("%H:%M"),
                    "termino": item.termino.strftime("%H:%M") if item.termino else None,
                    "limiteSaidaAntecipada": item.limite_saida_antecipada.strftime("%H:%M")
                    if item.limite_saida_antecipada
                    else None,
                }
                for item in Turno.objects.filter(ativo=True)
            ],
        })

    if request.auth_perfil["papel"] not in {"admin", "coordenacao"}:
        return JsonResponse({"detail": "Sem permissão para criar turmas ou turnos."}, status=403)

    try:
        body = _json_body(request)
        if body.get("tipo") == "turno":
            nome = clean_str(body.get("nome"), 20)
            if not nome:
                return JsonResponse({"detail": "Nome do turno é obrigatório."}, status=400)
            turno = Turno(
                nome=nome,
                inicio=body["inicio"],
                limite_entrada=body["limiteEntrada"],
                termino=body.get("termino") or None,
                limite_saida_antecipada=body.get("limiteSaidaAntecipada") or None,
            )
            turno.full_clean(validate_unique=False)
            with transaction.atomic():
                turno.save()
            return JsonResponse({
                "id": turno.id,
                "nome": turno.nome,
                "inicio": turno.inicio.strftime("%H:%M") if hasattr(turno.inicio, "strftime") else str(turno.inicio)[:5],
                "limiteEntrada": turno.limite_entrada.strftime("%H:%M") if hasattr(turno.limite_entrada, "strftime") else str(turno.limite_entrada)[:5],
                "termino": turno.termino.strftime("%H:%M") if turno.termino and hasattr(turno.termino, "strftime") else (str(turno.termino)[:5] if turno.termino else None),
                "limiteSaidaAntecipada": turno.limite_saida_antecipada.strftime("%H:%M")
                if turno.limite_saida_antecipada and hasattr(turno.limite_saida_antecipada, "strftime")
                else (str(turno.limite_saida_antecipada)[:5] if turno.limite_saida_antecipada else None),
            }, status=201)

        nome = clean_str(body.get("nome"), 80)
        if not nome:
            return JsonResponse({"detail": "Nome da turma é obrigatório."}, status=400)
        turno = Turno.objects.get(pk=body["turnoId"], ativo=True)
        turma = Turma(
            nome=nome,
            ano_letivo=int(body["anoLetivo"]),
            turno=turno,
        )
        turma.full_clean(validate_unique=False)
        with transaction.atomic():
            turma.save()
        return JsonResponse({
            "id": turma.id,
            "nome": turma.nome,
            "anoLetivo": turma.ano_letivo,
            "turnoId": turma.turno_id,
            "turno": turno.nome,
        }, status=201)
    except IntegrityError:
        return JsonResponse({"detail": "Turma ou turno com esse nome já existe."}, status=409)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, ValidationError, Turno.DoesNotExist) as error:
        return JsonResponse({"detail": f"Dados inválidos: {error}"}, status=400)


def _annotated_people_queryset(model_cls, tipo: str, request):
    is_aluno = tipo == "aluno"
    bio_filter = {"aluno_id": OuterRef("pk"), "ativo": True} if is_aluno else {"funcionario_id": OuterRef("pk"), "ativo": True}
    bio_qs = DadoBiometrico.objects.filter(**bio_filter)

    qs = model_cls.objects.annotate(
        has_bio=Exists(bio_qs),
        bio_qualidade=Subquery(bio_qs.order_by("-criado_em").values("qualidade")[:1]),
    ).order_by("nome", "id")

    search = clean_str(request.GET.get("search"), 100)
    if search:
        qs = qs.filter(Q(nome__icontains=search) | Q(documento__icontains=search))

    grupo = clean_str(request.GET.get("grupo"), 100)
    if grupo:
        qs = qs.filter(turma=grupo) if is_aluno else qs.filter(cargo=grupo)

    status = clean_str(request.GET.get("status"), 20)
    if status in {"ativo", "inativo"}:
        qs = qs.filter(status=status)

    biometria = clean_str(request.GET.get("biometria"), 10)
    if biometria == "sim":
        qs = qs.filter(has_bio=True)
    elif biometria == "nao":
        qs = qs.filter(has_bio=False)

    return qs


@csrf_exempt
@require_http_methods(["GET", "POST"])
@require_auth
def people(request):
    if request.method == "GET":
        page, page_size, offset = _parse_pagination(request, default_size=24, max_size=100)
        tipo_filter = clean_str(request.GET.get("tipo"), 20)
        present_set = _present_today_set()

        if tipo_filter == "aluno":
            qs = _annotated_people_queryset(Aluno, "aluno", request)
            total = qs.count()
            rows = list(qs[offset : offset + page_size])
            items = [
                _person(p, "aluno", present_set=present_set, has_bio_override=p.has_bio, bio_qualidade_override=p.bio_qualidade)
                for p in rows
            ]
        elif tipo_filter == "funcionario":
            qs = _annotated_people_queryset(Funcionario, "funcionario", request)
            total = qs.count()
            rows = list(qs[offset : offset + page_size])
            items = [
                _person(p, "funcionario", present_set=present_set, has_bio_override=p.has_bio, bio_qualidade_override=p.bio_qualidade)
                for p in rows
            ]
        else:
            qs_al = _annotated_people_queryset(Aluno, "aluno", request)
            qs_fn = _annotated_people_queryset(Funcionario, "funcionario", request)
            total_al = qs_al.count()
            total_fn = qs_fn.count()
            total = total_al + total_fn

            if offset < total_al:
                al_rows = list(qs_al[offset : offset + page_size])
                rem = page_size - len(al_rows)
                fn_rows = list(qs_fn[:rem]) if rem > 0 else []
            else:
                al_rows = []
                fn_offset = offset - total_al
                fn_rows = list(qs_fn[fn_offset : fn_offset + page_size])

            items = [
                _person(p, "aluno", present_set=present_set, has_bio_override=p.has_bio, bio_qualidade_override=p.bio_qualidade)
                for p in al_rows
            ] + [
                _person(p, "funcionario", present_set=present_set, has_bio_override=p.has_bio, bio_qualidade_override=p.bio_qualidade)
                for p in fn_rows
            ]

        return JsonResponse({
            "items": items,
            "people": items,
            "pagination": _pagination_meta(page, page_size, total),
        })

    if request.auth_perfil["papel"] not in {"admin", "coordenacao", "secretaria"}:
        return JsonResponse({"detail": "Sem permissão para cadastrar pessoas."}, status=403)

    try:
        body = _json_body(request)
        required = ["tipo", "nome", "documento", "grupo", "contatoNome", "contatoTelefone"]
        missing = [field for field in required if not clean_str(body.get(field))]
        if missing:
            return JsonResponse({"detail": "Campos obrigatórios ausentes.", "fields": missing}, status=400)

        tipo = body["tipo"]
        if tipo not in {"funcionario", "aluno"}:
            return JsonResponse({"detail": "Tipo de pessoa inválido."}, status=400)

        ref = body.get("dataRef")
        parsed_date = None
        if ref and ref != "—":
            try:
                parsed_date = date.fromisoformat(ref)
            except ValueError:
                try:
                    parsed_date = datetime.strptime(ref, "%d/%m/%Y").date()
                except ValueError as error:
                    raise ValueError("dataRef deve estar no formato YYYY-MM-DD ou DD/MM/YYYY.") from error

        consent = bool(body.get("consentimentoBiometrico", False))
        consent_resp = clean_str(body.get("consentimentoResponsavel") or body.get("contatoNome"), 150)

        common = {
            "nome": clean_str(body["nome"], 150),
            "documento": clean_str(body["documento"], 32),
            "turno": clean_str(body.get("turno") or "Manhã", 20),
            "status": "ativo",
            "contato_nome": clean_str(body["contatoNome"], 150),
            "contato_telefone": clean_str(body["contatoTelefone"], 32),
            "consentimento_biometrico": consent,
            "consentimento_em": timezone.now() if consent else None,
        }

        with transaction.atomic():
            if tipo == "funcionario":
                turno_obj = Turno.objects.filter(nome=common["turno"], ativo=True).first()
                person_obj = Funcionario.objects.create(
                    cargo=clean_str(body["grupo"], 100),
                    turno_ref=turno_obj,
                    data_admissao=parsed_date,
                    **common,
                )
            else:
                turma = None
                if body.get("turmaId"):
                    turma = Turma.objects.filter(pk=body["turmaId"], ativo=True).select_related("turno").first()
                if turma is None:
                    turma = Turma.objects.filter(nome=clean_str(body["grupo"], 80), ativo=True).select_related("turno").first()
                if turma:
                    common["turno"] = turma.turno.nome
                person_obj = Aluno.objects.create(
                    turma=turma.nome if turma else clean_str(body["grupo"], 80),
                    turma_ref=turma,
                    turno_ref=turma.turno if turma else Turno.objects.filter(nome=common["turno"]).first(),
                    data_nascimento=parsed_date,
                    consentimento_responsavel=consent_resp if consent else "",
                    **common,
                )
                resp_cpf = normalize_digits(body.get("responsavelCpf", ""))
                if len(resp_cpf) == 11:
                    cpf_hash = blind_index(resp_cpf, purpose="cpf")
                    resp_obj = Responsavel.objects.filter(cpf_hash=cpf_hash).first()
                    if resp_obj is None:
                        cpf_enc, key_id = encrypt_text(resp_cpf)
                        phone_enc, _ = encrypt_text(common["contato_telefone"])
                        resp_obj = Responsavel.objects.create(
                            nome=common["contato_nome"],
                            cpf_enc=cpf_enc,
                            phone_enc=phone_enc,
                            cpf_hash=cpf_hash,
                            key_id=key_id,
                        )
                    RelAlunoResponsavel.objects.get_or_create(aluno=person_obj, responsavel=resp_obj)

        registrar_auditoria(
            tabela=tipo,
            operacao="INSERT",
            chave=f"{tipo}:{person_obj.pk}",
            usuario=_actor_name(request),
            ip=getattr(request, "client_ip", None),
            detalhes={"documento": person_obj.documento, "consentimento": consent},
            sensivel=consent,
        )
        return JsonResponse(_person(person_obj, tipo, has_bio_override=False, bio_qualidade_override=None, present_set=set()), status=201)
    except IntegrityError:
        return JsonResponse({"detail": "Documento já cadastrado."}, status=409)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@require_auth
def person(request, person_ref):
    try:
        person_obj, tipo = _find_person(person_ref)
    except (Aluno.DoesNotExist, Funcionario.DoesNotExist, ValueError):
        return JsonResponse({"detail": "Pessoa não encontrada."}, status=404)

    if request.method == "GET":
        page, page_size, offset = _parse_pagination(request, default_size=15, max_size=50)
        owner_filter = {"aluno": person_obj} if tipo == "aluno" else {"funcionario": person_obj}
        hist_qs = RegistroAcesso.objects.filter(**owner_filter).order_by("-data_hora", "-id")
        total_hist = hist_qs.count()
        history = [_serialize_log(item) for item in hist_qs[offset : offset + page_size]]

        bio = DadoBiometrico.objects.filter(ativo=True, **owner_filter).order_by("-criado_em").first()
        rel_alerts = list(
            Alerta.objects.select_related("resolvido_por")
            .filter(pessoa_tipo=tipo, pessoa_id=person_obj.pk)
            .order_by("-criado_em")[:20]
        )

        return JsonResponse({
            "person": _person(
                person_obj,
                tipo,
                has_bio_override=(bio is not None),
                bio_qualidade_override=float(bio.qualidade) if bio else None,
            ),
            "history": history,
            "historyPagination": _pagination_meta(page, page_size, total_hist),
            "alerts": _enrich_alerts(rel_alerts),
            "biometria": {
                "cadastrada": bio is not None,
                "algoritmo": bio.algoritmo if bio else None,
                "qualidade": float(bio.qualidade) if bio else None,
                "atualizadaEm": bio.criado_em.isoformat() if bio else None,
            },
        })

    if request.auth_perfil["papel"] not in {"admin", "coordenacao", "secretaria"}:
        return JsonResponse({"detail": "Sem permissão para editar cadastros."}, status=403)

    try:
        body = _json_body(request)
        allowed = {
            "nome": ("nome", 150),
            "documento": ("documento", 32),
            "contatoNome": ("contato_nome", 150),
            "contatoTelefone": ("contato_telefone", 32),
            "turno": ("turno", 20),
        }
        for field, (model_field, max_len) in allowed.items():
            if field in body and clean_str(body[field]):
                setattr(person_obj, model_field, clean_str(body[field], max_len))

        if tipo == "aluno" and body.get("grupo"):
            person_obj.turma = clean_str(body["grupo"], 80)
            turma = None
            if body.get("turmaId"):
                turma = Turma.objects.select_related("turno").get(pk=body["turmaId"])
            else:
                turma = Turma.objects.filter(nome=person_obj.turma).select_related("turno").first()
            if turma:
                person_obj.turma_ref = turma
                person_obj.turno_ref = turma.turno
                person_obj.turno = turma.turno.nome
        elif tipo == "funcionario" and body.get("grupo"):
            person_obj.cargo = clean_str(body["grupo"], 100)

        with transaction.atomic():
            person_obj.save()
        registrar_auditoria(
            tabela=tipo,
            operacao="UPDATE",
            chave=f"{tipo}:{person_obj.pk}",
            usuario=_actor_name(request),
            ip=getattr(request, "client_ip", None),
        )
        return JsonResponse(_person(person_obj, tipo))
    except IntegrityError:
        return JsonResponse({"detail": "Documento já utilizado por outro cadastro."}, status=409)
    except (json.JSONDecodeError, ValueError, KeyError, Turma.DoesNotExist) as error:
        return JsonResponse({"detail": str(error)}, status=400)


@csrf_exempt
@require_http_methods(["PATCH"])
@require_auth(["admin", "coordenacao", "secretaria"])
def person_status(request, person_ref):
    try:
        person_obj, tipo = _find_person(person_ref)
    except (Aluno.DoesNotExist, Funcionario.DoesNotExist, ValueError):
        return JsonResponse({"detail": "Pessoa não encontrada."}, status=404)

    try:
        body = _json_body(request)
        status = body.get("status")
        if status not in {"ativo", "inativo"}:
            return JsonResponse({"detail": "Status deve ser ativo ou inativo."}, status=400)
        person_obj.status = status
        person_obj.save(update_fields=["status"])
        registrar_auditoria(
            tabela=tipo,
            operacao="UPDATE",
            chave=f"{tipo}:{person_obj.pk}",
            usuario=_actor_name(request),
            ip=getattr(request, "client_ip", None),
            detalhes={"status": status},
        )
        return JsonResponse({"id": f"{tipo}-{person_obj.pk}", "status": status})
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"detail": "Dados inválidos."}, status=400)


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
@require_auth(["admin", "coordenacao", "secretaria"])
def person_biometrics(request, person_ref):
    try:
        person_obj, tipo = _find_person(person_ref)
    except (Aluno.DoesNotExist, Funcionario.DoesNotExist, ValueError):
        return JsonResponse({"detail": "Pessoa não encontrada."}, status=404)

    ip = getattr(request, "client_ip", None)
    actor = _actor_name(request)

    if request.method == "DELETE":
        owner_filter = {"aluno": person_obj} if tipo == "aluno" else {"funcionario": person_obj}
        with transaction.atomic():
            deleted, _ = DadoBiometrico.objects.filter(**owner_filter).delete()
            person_obj.consentimento_biometrico = False
            person_obj.consentimento_em = None
            person_obj.save(update_fields=["consentimento_biometrico", "consentimento_em"])
        registrar_auditoria(
            tabela="dados_biometricos",
            operacao="DELETE",
            chave=f"{tipo}:{person_obj.pk}",
            usuario=actor,
            ip=ip,
            detalhes={"registrosRemovidos": deleted},
            sensivel=True,
        )
        return JsonResponse({"ok": True, "removidos": deleted})

    files = request.FILES.getlist("imagens") or ([request.FILES["imagem"]] if "imagem" in request.FILES else [])
    if not files:
        return JsonResponse({"detail": "Envie ao menos 1 imagem facial válida no campo 'imagens' ou 'imagem'."}, status=400)
    if len(files) > 5:
        return JsonResponse({"detail": "Envie no máximo 5 quadros por captura."}, status=400)

    raw_images: list[bytes] = []
    for f in files:
        if not (f.content_type or "").startswith("image/"):
            return JsonResponse({"detail": "Todos os arquivos enviados devem ser imagens."}, status=400)
        if f.size > 5 * 1024 * 1024:
            return JsonResponse({"detail": "Cada imagem deve ter no máximo 5 MB."}, status=400)
        raw_images.append(f.read())

    try:
        bio = enroll_person_biometrics(person_obj, tipo, raw_images, usuario=actor, ip=ip)
    except BiometricValidationError as error:
        return JsonResponse({"detail": str(error)}, status=422)

    return JsonResponse({
        "id": f"{tipo}-{person_obj.pk}",
        "tipo": tipo,
        "biometriaId": bio.pk,
        "algoritmo": bio.algoritmo,
        "dimensao": bio.dimensao,
        "qualidade": float(bio.qualidade),
        "keyId": bio.key_id,
    }, status=201)


@csrf_exempt
@require_http_methods(["PATCH"])
@require_auth(["admin", "coordenacao"])
def update_alert(request, alert_id):
    try:
        alert = Alerta.objects.get(pk=alert_id)
    except Alerta.DoesNotExist:
        return JsonResponse({"detail": "Alerta não encontrado."}, status=404)

    try:
        body = _json_body(request)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)

    novo_status = body.get("status", Alerta.Status.RESOLVIDO)
    if novo_status not in {Alerta.Status.NOVO, Alerta.Status.EM_ANALISE, Alerta.Status.RESOLVIDO}:
        return JsonResponse({"detail": "Status de alerta inválido."}, status=400)

    alert.status = novo_status
    if "observacao" in body:
        alert.observacao = clean_str(body.get("observacao"), 500)
    if novo_status == Alerta.Status.RESOLVIDO:
        alert.resolvido_por = request.auth_user
        alert.resolvido_em = timezone.now()
    alert.save()

    registrar_auditoria(
        tabela="alerta",
        operacao="UPDATE",
        chave=str(alert.pk),
        usuario=_actor_name(request),
        ip=getattr(request, "client_ip", None),
        detalhes={"status": alert.status},
    )
    return JsonResponse({
        "id": alert.id,
        "status": alert.status,
        "observacao": alert.observacao,
        "resolvidoEm": alert.resolvido_em.isoformat() if alert.resolvido_em else None,
        "resolvidoPor": request.auth_user.first_name or request.auth_user.username if alert.resolvido_por else None,
    })


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@require_auth
def school_settings(request):
    cfg = get_school_config()
    if request.method == "GET":
        return JsonResponse({"settings": _settings_dict(cfg)})

    if request.auth_perfil["papel"] not in {"admin", "coordenacao"}:
        return JsonResponse({"detail": "Sem permissão para alterar configurações."}, status=403)

    try:
        body = _json_body(request)
        mapping = {
            "nomeEscola": "nome_escola",
            "notifAtraso": "notif_atraso",
            "notifAusencia": "notif_ausencia",
            "notifNaoReconhecido": "notif_nao_reconhecido",
            "notifSaidaAntecipada": "notif_saida_antecipada",
            "limiteManha": "limite_manha",
            "limiteTarde": "limite_tarde",
            "saidaManha": "saida_manha",
            "saidaTarde": "saida_tarde",
            "cooldownSegundos": "cooldown_segundos",
            "tempoMinimoPermanenciaMin": "tempo_minimo_permanencia_min",
            "limiarConfianca": "limiar_confianca",
            "retencaoLogsDias": "retencao_logs_dias",
            "modoPassivo": "modo_passivo",
        }
        for json_key, field in mapping.items():
            if json_key not in body:
                continue
            val = body[json_key]
            if json_key == "limiarConfianca":
                if val in (None, ""):
                    raise ValueError("Limiar de confiança não pode estar vazio.")
                val = Decimal(str(round(float(val), 3)))
            elif json_key in {"cooldownSegundos", "tempoMinimoPermanenciaMin", "retencaoLogsDias"}:
                if val in (None, ""):
                    raise ValueError(f"Campo {json_key} não pode estar vazio.")
                val = int(val)
            elif json_key == "nomeEscola":
                val = clean_str(val, 150)
                if not val:
                    raise ValueError("Nome da escola não pode estar vazio.")
            elif json_key in {"notifAtraso", "notifAusencia", "notifNaoReconhecido", "notifSaidaAntecipada", "modoPassivo"}:
                val = bool(val)
            setattr(cfg, field, val)
        cfg.full_clean()
        cfg.save()
        registrar_auditoria(
            tabela="configuracao_escola",
            operacao="UPDATE",
            chave=str(cfg.pk),
            usuario=_actor_name(request),
            ip=getattr(request, "client_ip", None),
        )
        return JsonResponse({"settings": _settings_dict(cfg)})
    except (json.JSONDecodeError, ValueError, TypeError, InvalidOperation, ValidationError) as error:
        return JsonResponse({"detail": f"Configuração inválida: {error}"}, status=400)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@require_auth(["admin", "coordenacao"])
def devices(request):
    if request.method == "GET":
        return JsonResponse({"dispositivos": [_device_dict(d) for d in DispositivoPortaria.objects.all()]})

    try:
        body = _json_body(request)
        nome = clean_str(body.get("nome"), 100)
        portal = clean_str(body.get("portal"), 100)
        sentido = body.get("sentidoPadrao", "auto")
        if not nome or not portal:
            return JsonResponse({"detail": "Nome e portal são obrigatórios."}, status=400)
        if sentido not in {"auto", "entrada", "saida"}:
            return JsonResponse({"detail": "sentidoPadrao deve ser auto, entrada ou saida."}, status=400)

        raw_key, prefix, digest = generate_secret("port")
        with transaction.atomic():
            dev = DispositivoPortaria.objects.create(
                nome=nome,
                portal=portal,
                sentido_padrao=sentido,
                api_key_hash=digest,
                api_key_prefixo=prefix,
                ativo=True,
            )
        registrar_auditoria(
            tabela="dispositivo_portaria",
            operacao="INSERT",
            chave=str(dev.pk),
            usuario=_actor_name(request),
            ip=getattr(request, "client_ip", None),
            detalhes={"nome": dev.nome, "portal": dev.portal},
            sensivel=True,
        )
        data = _device_dict(dev)
        data["apiKey"] = raw_key
        return JsonResponse(data, status=201)
    except IntegrityError:
        return JsonResponse({"detail": "Já existe um dispositivo com esse nome."}, status=409)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)


@csrf_exempt
@require_http_methods(["PATCH"])
@require_auth(["admin", "coordenacao"])
def device_detail(request, device_id):
    try:
        dev = DispositivoPortaria.objects.get(pk=device_id)
    except DispositivoPortaria.DoesNotExist:
        return JsonResponse({"detail": "Dispositivo não encontrado."}, status=404)

    try:
        body = _json_body(request)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)

    if "ativo" in body:
        dev.ativo = bool(body["ativo"])
    if "portal" in body and clean_str(body["portal"]):
        dev.portal = clean_str(body["portal"], 100)
    if "sentidoPadrao" in body and body["sentidoPadrao"] in {"auto", "entrada", "saida"}:
        dev.sentido_padrao = body["sentidoPadrao"]

    rotated_key = None
    if body.get("rotacionarChave"):
        rotated_key, prefix, digest = generate_secret("port")
        dev.api_key_hash = digest
        dev.api_key_prefixo = prefix

    dev.save()
    registrar_auditoria(
        tabela="dispositivo_portaria",
        operacao="UPDATE",
        chave=str(dev.pk),
        usuario=_actor_name(request),
        ip=getattr(request, "client_ip", None),
        detalhes={"ativo": dev.ativo, "rotacionouChave": bool(rotated_key)},
        sensivel=bool(rotated_key),
    )
    data = _device_dict(dev)
    if rotated_key:
        data["apiKey"] = rotated_key
    return JsonResponse(data)


@require_http_methods(["GET"])
@require_auth(["admin", "coordenacao"])
def audit_logs(request):
    page, page_size, offset = _parse_pagination(request, default_size=20, max_size=100)
    qs = LogAuditoria.objects.all()

    operacao = clean_str(request.GET.get("operacao"), 16)
    if operacao in {"INSERT", "UPDATE", "DELETE", "SELECT", "AUTH", "SYNC"}:
        qs = qs.filter(operacao=operacao)

    tabela = clean_str(request.GET.get("tabela"), 80)
    if tabela:
        qs = qs.filter(tabela=tabela)

    sensivel = request.GET.get("sensivel")
    if sensivel == "1":
        qs = qs.filter(sensivel=True)
    elif sensivel == "0":
        qs = qs.filter(sensivel=False)

    search = clean_str(request.GET.get("search"), 100)
    if search:
        qs = qs.filter(Q(usuario__icontains=search) | Q(chave__icontains=search))

    total = qs.count()
    items = [
        {
            "id": item.pk,
            "tabela": item.tabela,
            "operacao": item.operacao,
            "chave": item.chave,
            "usuario": item.usuario,
            "ipOrigem": item.ip_origem,
            "detalhes": item.detalhes,
            "sensivel": item.sensivel,
            "ocorridoEm": item.ocorrido_em.isoformat(),
        }
        for item in qs[offset : offset + page_size]
    ]
    return JsonResponse({
        "items": items,
        "logs": items,
        "pagination": _pagination_meta(page, page_size, total),
    })


@require_http_methods(["GET"])
@require_auth
def reports_export(request):
    qs = RegistroAcesso.objects.select_related("aluno", "funcionario").order_by("-data_hora")
    de = request.GET.get("de")
    ate = request.GET.get("ate")
    try:
        if de:
            d_ini = date.fromisoformat(de)
            qs = qs.filter(data_hora__gte=timezone.make_aware(datetime.combine(d_ini, time.min)))
        if ate:
            d_fim = date.fromisoformat(ate)
            qs = qs.filter(data_hora__lte=timezone.make_aware(datetime.combine(d_fim, time.max)))
    except ValueError:
        return JsonResponse({"detail": "Parâmetros 'de' e 'ate' devem usar formato YYYY-MM-DD."}, status=400)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="frequencia-escolar.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["ID", "Data", "Hora", "Pessoa", "Tipo Pessoa", "Turma/Cargo", "Movimento", "Status", "Portal", "Confiança"])

    for row in qs[:5000]:
        local_dt = timezone.localtime(row.data_hora)
        person_obj = row.funcionario or row.aluno
        p_tipo = "Funcionário" if row.funcionario_id else ("Aluno" if row.aluno_id else "Desconhecido")
        grupo = person_obj.cargo if row.funcionario_id else (person_obj.turma if row.aluno_id else "—")
        conf_str = f"{float(row.confianca) * 100:.1f}%" if row.confianca is not None else "—"
        writer.writerow([
            row.pk,
            local_dt.strftime("%d/%m/%Y"),
            local_dt.strftime("%H:%M:%S"),
            person_obj.nome if person_obj else "Rosto não identificado",
            p_tipo,
            grupo,
            row.tipo,
            row.status,
            row.portal,
            conf_str,
        ])

    registrar_auditoria(
        tabela="registro_acesso",
        operacao="SELECT",
        chave="export_csv",
        usuario=_actor_name(request),
        ip=getattr(request, "client_ip", None),
        sensivel=True,
    )
    return response


@csrf_exempt
@require_http_methods(["POST"])
@require_auth(["admin", "coordenacao"])
def access_register(request):
    try:
        body = _json_body(request)
        person_ref = body.get("personId")
        tipo = body.get("tipo", "auto")
        portal = clean_str(body.get("portal") or "Portaria principal", 100)
        status_req = body.get("status")

        person_obj = None
        person_tipo = None
        if person_ref not in (None, ""):
            try:
                person_obj, person_tipo = _find_person(person_ref)
            except (Aluno.DoesNotExist, Funcionario.DoesNotExist, ValueError):
                return JsonResponse({"detail": "Pessoa informada não existe."}, status=404)

        result = processar_passagem(
            person=person_obj,
            person_tipo=person_tipo,
            tipo_solicitado=tipo,
            portal=portal,
            confianca=body.get("confianca"),
            client_event_id=body.get("clientEventId"),
            status_override=status_req,
        )
        return JsonResponse(result, status=200 if result.get("ignored") else 201)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)


# =====================================================================
# ENDPOINTS EXCLUSIVOS DOS TERMINAIS PASSIVOS DE PORTARIA (X-Portaria-Key)
# =====================================================================


@require_http_methods(["GET"])
@require_device_auth
def portaria_config(request):
    cfg = get_school_config()
    dev = request.dispositivo
    sample_people = [
        {"uid": f"aluno-{a.pk}", "nome": a.nome}
        for a in Aluno.objects.filter(status="ativo").order_by("id")[:5]
    ]
    return JsonResponse({
        "dispositivo": _device_dict(dev),
        "settings": _settings_dict(cfg),
        "samplePeople": sample_people,
    })


@require_http_methods(["GET"])
@require_device_auth
def portaria_biometrics(request):
    version, entries = get_active_gallery()
    client_version = request.GET.get("version")
    if client_version and client_version == version:
        return JsonResponse({"version": version, "unchanged": True, "total": len(entries)})
    return JsonResponse({
        "version": version,
        "unchanged": False,
        "total": len(entries),
        "entries": entries,
    })


@csrf_exempt
@require_http_methods(["POST"])
@require_device_auth
def portaria_events(request):
    try:
        body = _json_body(request)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)

    events = body.get("events") if isinstance(body.get("events"), list) else [body]
    if len(events) > 100:
        return JsonResponse({"detail": "Lote máximo de 100 eventos por requisição."}, status=400)

    dev = request.dispositivo
    dev.ultimo_heartbeat = timezone.now()
    dev.save(update_fields=["ultimo_heartbeat"])

    results = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        person_ref = ev.get("personRef") or ev.get("personId")
        person_obj = None
        person_tipo = None
        if person_ref not in (None, ""):
            try:
                person_obj, person_tipo = _find_person(person_ref)
            except (Aluno.DoesNotExist, Funcionario.DoesNotExist, ValueError):
                person_obj, person_tipo = None, None

        data_hora = None
        if ev.get("timestamp"):
            try:
                data_hora = datetime.fromisoformat(str(ev["timestamp"]).replace("Z", "+00:00"))
            except ValueError:
                data_hora = None

        tipo_solicitado = ev.get("tipo") or dev.sentido_padrao or "auto"
        portal = clean_str(ev.get("portal") or dev.portal, 100)
        conf_val = None
        if ev.get("confianca") is not None:
            try:
                conf_val = max(0.0, min(1.0, float(ev["confianca"])))
            except (TypeError, ValueError):
                conf_val = None
        res = processar_passagem(
            person=person_obj,
            person_tipo=person_tipo,
            tipo_solicitado=tipo_solicitado,
            portal=portal,
            dispositivo=dev,
            confianca=conf_val,
            data_hora=data_hora,
            client_event_id=clean_str(ev.get("clientEventId"), 64) or None,
        )
        results.append(res)

    return JsonResponse({"processed": len(results), "results": results}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
@require_device_auth
def portaria_heartbeat(request):
    try:
        body = _json_body(request)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)

    dev = request.dispositivo
    dev.ultimo_heartbeat = timezone.now()
    dev.telemetria = {
        "fps": body.get("fps"),
        "aiMs": body.get("aiMs"),
        "cameraOk": bool(body.get("cameraOk", True)),
        "enrolledCount": body.get("enrolledCount", 0),
        "pendingQueue": body.get("pendingQueue", 0),
    }
    dev.save(update_fields=["ultimo_heartbeat", "telemetria"])
    return JsonResponse({"ok": True, "serverTime": timezone.now().isoformat()})
