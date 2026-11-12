import json
from datetime import date, datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import Alerta, Aluno, Funcionario, RegistroAcesso


def _person(person, tipo):
    funcionario = tipo == "funcionario"
    return {
        "id": person.pk + (10000 if funcionario else 0),
        "tipo": tipo,
        "nome": person.nome,
        "documento": person.documento,
        "grupo": person.cargo if funcionario else person.turma,
        "turno": person.turno,
        "status": person.status,
        "contatoNome": person.contato_nome,
        "contatoTelefone": person.contato_telefone,
        "dataCadastro": person.criado_em.strftime("%d/%m/%Y"),
        "dataRef": (person.data_admissao if funcionario else person.data_nascimento).strftime("%d/%m/%Y")
        if (person.data_admissao if funcionario else person.data_nascimento) else "—",
    }


def _json_body(request):
    if not request.body:
        return {}
    if len(request.body) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
        raise ValueError("Corpo da requisição muito grande.")
    body = json.loads(request.body)
    if not isinstance(body, dict):
        raise ValueError("O corpo deve ser um objeto JSON.")
    return body


def _find_person(person_id):
    if person_id >= 10000:
        return Funcionario.objects.get(pk=person_id - 10000), "funcionario"
    return Aluno.objects.get(pk=person_id), "aluno"


def _logs():
    result = []
    for item in RegistroAcesso.objects.all():
        person = item.funcionario or item.aluno
        tipo = "funcionario" if item.funcionario_id else "aluno"
        person_id = (item.funcionario_id + 10000) if item.funcionario_id else item.aluno_id
        local_time = timezone.localtime(item.data_hora)
        result.append({
            "id": item.pk,
            "personId": person_id,
            "tipo": item.tipo,
            "horaMin": local_time.hour * 60 + local_time.minute,
            "status": item.status,
            "local": item.portal,
            "dataHora": item.data_hora.isoformat(),
            "personType": tipo,
            "personName": person.nome if person else None,
        })
    return result


def _alerts():
    return [{
        "id": item.pk,
        "personId": item.pessoa_id if item.pessoa_tipo == "aluno" else (
            item.pessoa_id + 10000 if item.pessoa_id else None
        ),
        "tipo": item.tipo,
        "descricao": item.descricao,
        "severidade": item.severidade,
        "status": item.status,
    } for item in Alerta.objects.all()]


@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok", "service": "reconhecimento-na-escola"})


@require_http_methods(["GET"])
def bootstrap(request):
    people = [_person(p, "aluno") for p in Aluno.objects.all()]
    people += [_person(p, "funcionario") for p in Funcionario.objects.all()]
    return JsonResponse({
        "people": people,
        "logs": _logs(),
        "alerts": _alerts(),
        "settings": {
            "notifAtraso": True, "notifAusencia": True,
            "notifNaoReconhecido": False, "limiteManha": "07:20", "limiteTarde": "13:20",
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    try:
        body = _json_body(request)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)
    if not body.get("email") or not body.get("senha"):
        return JsonResponse({"detail": "E-mail e senha são obrigatórios."}, status=400)
    if not settings.DEMO_LOGIN:
        return JsonResponse({"detail": "Autenticação de produção ainda não configurada."}, status=503)
    return JsonResponse({"token": "mock-session", "user": {"nome": "Marina", "perfil": "coordenação"}})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def people(request):
    if request.method == "GET":
        return bootstrap(request)
    try:
        body = _json_body(request)
        required = ["tipo", "nome", "documento", "grupo", "turno", "contatoNome", "contatoTelefone"]
        missing = [field for field in required if not body.get(field)]
        if missing:
            return JsonResponse({"detail": "Campos obrigatórios ausentes.", "fields": missing}, status=400)
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
        common = {
            "nome": body["nome"], "documento": body["documento"], "turno": body["turno"],
            "status": "ativo", "contato_nome": body["contatoNome"],
            "contato_telefone": body["contatoTelefone"],
        }
        if body["tipo"] not in {"funcionario", "aluno"}:
            return JsonResponse({"detail": "Tipo de pessoa inválido."}, status=400)
        with transaction.atomic():
            if body["tipo"] == "funcionario":
                person = Funcionario.objects.create(cargo=body["grupo"], data_admissao=parsed_date, **common)
            else:
                person = Aluno.objects.create(turma=body["grupo"], data_nascimento=parsed_date, **common)
        return JsonResponse(_person(person, body["tipo"]), status=201)
    except IntegrityError:
        return JsonResponse({"detail": "Documento já cadastrado."}, status=409)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)


@csrf_exempt
@require_http_methods(["PATCH"])
def person_status(request, person_id):
    try:
        person, _ = _find_person(person_id)
        body = _json_body(request)
        status = body.get("status")
        if status not in {"ativo", "inativo"}:
            return JsonResponse({"detail": "Status deve ser ativo ou inativo."}, status=400)
        person.status = status
        person.save(update_fields=["status"])
        return JsonResponse({"id": person_id, "status": status})
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"detail": "Dados inválidos."}, status=400)
    except (Aluno.DoesNotExist, Funcionario.DoesNotExist):
        return JsonResponse({"detail": "Pessoa não encontrada."}, status=404)


@csrf_exempt
@require_http_methods(["PATCH"])
def resolve_alert(request, alert_id):
    try:
        alert = Alerta.objects.get(pk=alert_id)
    except Alerta.DoesNotExist:
        return JsonResponse({"detail": "Alerta não encontrado."}, status=404)
    alert.status = "resolvido"
    alert.save(update_fields=["status"])
    return JsonResponse({"id": alert.id, "status": alert.status})


@csrf_exempt
@require_http_methods(["POST"])
def access_register(request):
    try:
        body = _json_body(request)
        person_id = body.get("personId")
        tipo = body.get("tipo", "entrada")
        portal = body.get("portal", "Portaria principal")
        status_req = body.get("status")

        if tipo not in {"entrada", "saida"}:
            return JsonResponse({"detail": "Tipo deve ser 'entrada' ou 'saida'."}, status=400)

        person = None
        person_tipo = None
        if person_id:
            try:
                person, person_tipo = _find_person(int(person_id))
            except (Aluno.DoesNotExist, Funcionario.DoesNotExist, ValueError):
                return JsonResponse({"detail": "Pessoa informada não existe."}, status=404)

        now = timezone.now()
        local_now = timezone.localtime(now)
        current_time_str = local_now.strftime("%H:%M")

        if not person:
            status = "nao-reconhecido"
        elif status_req in {"reconhecido", "atraso", "nao-reconhecido"}:
            status = status_req
        else:
            status = "reconhecido"
            if tipo == "entrada":
                turno = getattr(person, "turno", "Manhã")
                if turno == "Manhã" and current_time_str > "07:20":
                    status = "atraso"
                elif turno == "Tarde" and current_time_str > "13:20":
                    status = "atraso"

        with transaction.atomic():
            kwargs = {}
            if person:
                if person_tipo == "funcionario":
                    kwargs["funcionario"] = person
                else:
                    kwargs["aluno"] = person
            else:
                kwargs["aluno"] = None
                kwargs["funcionario"] = None

            registro = RegistroAcesso.objects.create(
                portal=portal,
                tipo=tipo,
                status=status,
                data_hora=now,
                **kwargs,
            )

            if status in {"atraso", "nao-reconhecido"}:
                Alerta.objects.create(
                    pessoa_tipo=person_tipo if person else "",
                    pessoa_id=person.pk if person else None,
                    tipo="Atraso na entrada" if status == "atraso" else "Tentativa não reconhecida",
                    descricao=(
                        f"Entrada com atraso registrada às {local_now.strftime('%H:%M')}."
                        if status == "atraso"
                        else "Reconhecimento facial não identificou nenhum cadastro na portaria."
                    ),
                    severidade="media" if status == "atraso" else "alta",
                    status="novo",
                )

        return JsonResponse({
            "id": registro.pk,
            "personId": person_id,
            "personName": person.nome if person else None,
            "personType": person_tipo,
            "tipo": registro.tipo,
            "status": registro.status,
            "portal": registro.portal,
            "dataHora": registro.data_hora.isoformat(),
        }, status=201)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"detail": str(error)}, status=400)

