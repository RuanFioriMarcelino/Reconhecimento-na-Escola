from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..models import Alerta, ConfiguracaoEscola, RegistroAcesso, Turno
from ..security import registrar_auditoria


def get_school_config() -> ConfiguracaoEscola:
    config = ConfiguracaoEscola.objects.order_by("id").first()
    if config is None:
        config = ConfiguracaoEscola.objects.create()
    return config


def _parse_hhmm(value: str, fallback: time) -> time:
    try:
        parts = (value or "").strip().split(":")
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        return fallback


def _get_person_time_limits(person, person_tipo: str, config: ConfiguracaoEscola) -> tuple[time, time | None]:
    turno_obj = getattr(person, "turno_ref", None)
    if turno_obj is None and getattr(person, "turno", None):
        turno_obj = Turno.objects.filter(nome=person.turno, ativo=True).first()

    if turno_obj is not None:
        return turno_obj.limite_entrada, turno_obj.limite_saida_antecipada

    turno_nome = getattr(person, "turno", "Manhã")
    if turno_nome == "Tarde":
        return _parse_hhmm(config.limite_tarde, time(13, 20)), _parse_hhmm(config.saida_tarde, time(17, 30))
    return _parse_hhmm(config.limite_manha, time(7, 20)), _parse_hhmm(config.saida_manha, time(11, 30))


def _person_uid(person, person_tipo: str) -> str:
    return f"{person_tipo}-{person.pk}"


def _format_notice(status: str, tipo: str, person) -> tuple[str, str]:
    nome = person.nome if person else "Rosto não cadastrado"
    if status == RegistroAcesso.Status.NAO_RECONHECIDO:
        return "Aviso: Pessoa não cadastrada", "warn"
    if person and person.status == "inativo":
        return f"Aviso: Cadastro inativo ({nome})", "warn"
    if status == RegistroAcesso.Status.ATRASO:
        return f"Aviso: Atraso na entrada ({nome})", "warn"
    if status == RegistroAcesso.Status.SAIDA_ANTECIPADA:
        return f"Aviso: Saída antecipada ({nome})", "warn"
    acao = "Entrada registrada" if tipo == RegistroAcesso.Tipo.ENTRADA else "Saída registrada"
    return f"{acao}: {nome}", "ok"


def processar_passagem(
    person=None,
    person_tipo: str | None = None,
    tipo_solicitado: str = "auto",
    portal: str = "Portaria principal",
    dispositivo=None,
    confianca: float | None = None,
    data_hora: datetime | None = None,
    client_event_id: str | None = None,
    status_override: str | None = None,
) -> dict:
    """Processa uma passagem facial em modo passivo (nunca bloqueia, sempre registra e emite avisos)."""
    config = get_school_config()
    now = data_hora or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())
    local_now = timezone.localtime(now)
    local_date = local_now.date()

    # 1. Idempotência para eventos reenviados pela fila offline da portaria
    if client_event_id:
        existing = RegistroAcesso.objects.filter(client_event_id=client_event_id).first()
        if existing:
            p = existing.funcionario or existing.aluno
            p_tipo = "funcionario" if existing.funcionario_id else ("aluno" if existing.aluno_id else None)
            notice, level = _format_notice(existing.status, existing.tipo, p)
            return {
                "id": existing.pk,
                "deduplicated": True,
                "ignored": False,
                "personUid": _person_uid(p, p_tipo) if p else None,
                "personName": p.nome if p else None,
                "personType": p_tipo,
                "tipo": existing.tipo,
                "status": existing.status,
                "incidente": existing.incidente,
                "portal": existing.portal,
                "confianca": float(existing.confianca) if existing.confianca is not None else None,
                "dataHora": existing.data_hora.isoformat(),
                "notice": notice,
                "noticeLevel": level,
            }

    # 2. Cooldown anti-duplicidade
    if person is None:
        recent_unknown = (
            RegistroAcesso.objects.filter(
                aluno__isnull=True,
                funcionario__isnull=True,
                portal=portal,
                data_hora__gte=now - timedelta(seconds=20),
            )
            .order_by("-data_hora")
            .first()
        )
        if recent_unknown:
            return {
                "ignored": True,
                "reason": "unknown_cooldown",
                "notice": "Aviso: Pessoa não cadastrada",
                "noticeLevel": "warn",
            }
    else:
        owner_filter = {"aluno": person} if person_tipo == "aluno" else {"funcionario": person}
        last_any = (
            RegistroAcesso.objects.filter(**owner_filter)
            .order_by("-data_hora")
            .first()
        )
        if last_any and abs((now - last_any.data_hora).total_seconds()) < config.cooldown_segundos:
            return {
                "ignored": True,
                "reason": "cooldown",
                "personUid": _person_uid(person, person_tipo),
                "personName": person.nome,
                "tipo": last_any.tipo,
                "status": last_any.status,
                "notice": _format_notice(last_any.status, last_any.tipo, person)[0],
                "noticeLevel": _format_notice(last_any.status, last_any.tipo, person)[1],
            }

    # 3. Determinação automática de Entrada vs Saída (baseada no dia corrente)
    if person is None:
        tipo = "entrada" if tipo_solicitado not in {"entrada", "saida"} else tipo_solicitado
    elif tipo_solicitado == "auto":
        start_of_day = timezone.make_aware(
            datetime.combine(local_date, time.min), timezone.get_current_timezone()
        )
        last_today = (
            RegistroAcesso.objects.filter(
                data_hora__gte=start_of_day,
                data_hora__lte=now,
                **({"aluno": person} if person_tipo == "aluno" else {"funcionario": person}),
            )
            .order_by("-data_hora")
            .first()
        )
        if last_today is None or last_today.tipo == RegistroAcesso.Tipo.SAIDA:
            tipo = RegistroAcesso.Tipo.ENTRADA
        else:
            elapsed_min = (now - last_today.data_hora).total_seconds() / 60.0
            if elapsed_min < config.tempo_minimo_permanencia_min:
                return {
                    "ignored": True,
                    "reason": "dwell_cooldown",
                    "personUid": _person_uid(person, person_tipo),
                    "personName": person.nome,
                    "tipo": last_today.tipo,
                    "status": last_today.status,
                    "notice": f"Entrada já registrada: {person.nome}",
                    "noticeLevel": "ok",
                }
            tipo = RegistroAcesso.Tipo.SAIDA
    elif tipo_solicitado in {"entrada", "saida"}:
        tipo = tipo_solicitado
    else:
        raise ValueError("Tipo deve ser 'auto', 'entrada' ou 'saida'.")

    # 4. Classificação passiva e criação de avisos/alertas (nunca nega passagem)
    incidente = False
    alert_spec = None

    if person is None:
        status = RegistroAcesso.Status.NAO_RECONHECIDO
        incidente = True
        if config.notif_nao_reconhecido:
            alert_spec = (
                "Tentativa não reconhecida",
                f"Rosto não cadastrado detectado em {portal} às {local_now.strftime('%H:%M')}.",
                Alerta.Severidade.ALTA,
            )
    elif status_override in {"reconhecido", "atraso", "saida-antecipada", "nao-reconhecido"}:
        status = status_override
        incidente = status != "reconhecido"
    else:
        status = RegistroAcesso.Status.RECONHECIDO
        limite_entrada, limite_saida = _get_person_time_limits(person, person_tipo, config)
        local_t = local_now.time()

        if person.status == "inativo":
            incidente = True
            alert_spec = (
                "Cadastro inativo na portaria",
                f"{person.nome} possui cadastro inativo e passou por {portal} às {local_now.strftime('%H:%M')}.",
                Alerta.Severidade.ALTA,
            )
        elif tipo == RegistroAcesso.Tipo.ENTRADA and local_t > limite_entrada:
            status = RegistroAcesso.Status.ATRASO
            incidente = True
            if config.notif_atraso:
                alert_spec = (
                    "Atraso na entrada",
                    f"Entrada após o horário limite ({limite_entrada.strftime('%H:%M')}), registrada às {local_now.strftime('%H:%M')}.",
                    Alerta.Severidade.MEDIA,
                )
        elif (
            tipo == RegistroAcesso.Tipo.SAIDA
            and person_tipo == "aluno"
            and limite_saida is not None
            and local_t < limite_saida
        ):
            status = RegistroAcesso.Status.SAIDA_ANTECIPADA
            incidente = True
            if config.notif_saida_antecipada:
                alert_spec = (
                    "Saída antecipada",
                    f"Saída antes do término do turno ({limite_saida.strftime('%H:%M')}), registrada às {local_now.strftime('%H:%M')}.",
                    Alerta.Severidade.MEDIA,
                )

    conf_dec = None
    if confianca is not None:
        conf_val = max(0.0, min(1.0, float(confianca)))
        conf_dec = Decimal(f"{conf_val:.4f}")

    with transaction.atomic():
        owner_kwargs = (
            {"aluno": person, "funcionario": None}
            if person_tipo == "aluno"
            else ({"aluno": None, "funcionario": person} if person_tipo == "funcionario" else {"aluno": None, "funcionario": None})
        )
        registro = RegistroAcesso.objects.create(
            dispositivo=dispositivo,
            data_hora=now,
            portal=portal,
            tipo=tipo,
            status=status,
            confianca=conf_dec,
            incidente=incidente,
            client_event_id=client_event_id or None,
            **owner_kwargs,
        )
        if alert_spec is not None:
            Alerta.objects.create(
                pessoa_tipo=person_tipo if person else "",
                pessoa_id=person.pk if person else None,
                registro_acesso=registro,
                tipo=alert_spec[0],
                descricao=alert_spec[1],
                severidade=alert_spec[2],
                status=Alerta.Status.NOVO,
            )

    if dispositivo is not None:
        registrar_auditoria(
            tabela="registro_acesso",
            operacao="INSERT",
            chave=str(registro.pk),
            usuario=f"device:{dispositivo.nome}",
            ip=dispositivo.ip_ultimo_acesso,
            detalhes={"tipo": tipo, "status": status, "portal": portal},
            sensivel=False,
        )

    notice, level = _format_notice(status, tipo, person)
    return {
        "id": registro.pk,
        "deduplicated": False,
        "ignored": False,
        "personUid": _person_uid(person, person_tipo) if person else None,
        "personName": person.nome if person else None,
        "personType": person_tipo,
        "tipo": registro.tipo,
        "status": registro.status,
        "incidente": registro.incidente,
        "portal": registro.portal,
        "confianca": float(registro.confianca) if registro.confianca is not None else None,
        "dataHora": registro.data_hora.isoformat(),
        "notice": notice,
        "noticeLevel": level,
    }
