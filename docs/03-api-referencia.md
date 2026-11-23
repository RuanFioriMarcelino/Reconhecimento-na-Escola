# 03 — Referência da API REST v2.0

A API do **Reconhece+ v2.0** é servida pelo BackEnd Django sob o prefixo `/api/` e está definida em [BackEnd/school_api/urls.py](../BackEnd/school_api/urls.py) e [BackEnd/core/views.py](../BackEnd/core/views.py).

---

## Convenções Gerais

### Autenticação
- **Painel Web e Estação de Cadastro**: `Authorization: Bearer <token>` (emitido em `POST /api/login/`, armazenado como hash SHA-256 em `auth_token` com TTL padrão de `AUTH_TOKEN_TTL_HOURS=12`). Também aceita sessão cookie Django como fallback.
- **Terminais Autônomos da Portaria**: cabeçalho exclusivo `X-Portaria-Key: <chave>` vinculado a um registro ativo em `dispositivo_portaria`.

### Limites de Payload
- Requisições JSON: máximo **256 KB** (`JSON_BODY_MAX_BYTES`).
- Upload biométrico multipart: máximo **10 MB** no total, até **5 imagens** por envio, cada imagem com no máximo **5 MB** e `Content-Type` começando com `image/`.

### Paginação Padrão
Endpoints listáveis aceitam `?page=1&page_size=...` (`page >= 1`, `page_size` limitado até `max_size=100`, ou `50` no histórico individual de pessoa) e retornam:

```json
{
  "items": [ ... ],
  "pagination": {
    "page": 1,
    "pageSize": 25,
    "total": 142,
    "totalPages": 6,
    "hasNext": true,
    "hasPrev": false
  }
}
```

### Cabeçalhos de Resposta e Erros
Todas as respostas sob `/api/` recebem pelo `AuditMiddleware`:
- `X-Request-ID`: identificador único de rastreio da requisição.
- `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` e `Pragma: no-cache`.
- `Permissions-Policy: camera=(self)` e `X-Content-Type-Options: nosniff`.

Erros — inclusive exceções inesperadas `500` tratadas por `AuditMiddleware.process_exception` — sempre retornam JSON (nunca HTML):

```json
{
  "detail": "Descrição legível do erro",
  "requestId": "a1b2c3d4e5f60718"
}
```

---

## Matriz de Permissões (RBAC)

| Recurso / Operação | `admin` | `coordenacao` | `secretaria` | `visualizador` | Terminal (`X-Portaria-Key`) |
|---|---|---|---|---|---|
| `GET /api/health/` | Público | Público | Público | Público | Público |
| `GET /api/bootstrap/`, `/dashboard/`, `/live/`, `/logs/`, `/alerts/`, `/reports/export/` | Sim | Sim | Sim | Sim | Não |
| `GET /api/people/`, `/people/<ref>/` | Sim | Sim | Sim | Sim | Não |
| `POST /api/people/`, `PATCH /api/people/<ref>/`, `/status/`, `POST/DELETE /biometrics/` | Sim | Sim | Sim | **403** | Não |
| `PATCH /api/alerts/<id>/` | Sim | Sim | **403** | **403** | Não |
| `POST /api/classes/`, `GET/PATCH /api/settings/` (`PATCH`), `/devices/*`, `GET /api/audit/`, `POST /api/access/` | Sim | Sim | **403** | **403** | Não |
| `/api/portaria/config/`, `/biometrics/`, `/events/`, `/heartbeat/` | **401** | **401** | **401** | **401** | **Sim** |

> Observação: `GET /api/classes/` e `GET /api/settings/` são acessíveis a qualquer usuário autenticado; apenas criação/alteração (`POST`/`PATCH`) exige `admin` ou `coordenacao`.

---

## 1. Saúde e Autenticação

| Método & Rota | Auth / RBAC | Descrição |
|---|---|---|
| `GET /api/health/` | Público | Verifica conectividade com PostgreSQL (`SELECT 1`). Retorna `200` (`status: "ok"`) ou `503`. |
| `POST /api/login/` | Público (Rate limit 5/300s) | Autentica `email` + `senha`. Retorna `token`, `expiresAt` e objeto `user` (`id`, `email`, `nome`, `papel`). Retorna `429` após 5 falhas em 5 min por `(ip, email)`. |
| `POST /api/logout/` | Autenticado | Revoga o `AuthToken` atual (`revogado=True`), registra auditoria e encerra sessão Django. |
| `GET /api/me/` | Autenticado | Retorna dados do usuário logado (`id`, `email`, `nome`, `papel`). |

---

## 2. Painel, Tempo Real, Monitoramento e Relatórios

| Método & Rota | Auth / RBAC | Parâmetros & Retorno |
|---|---|---|
| `GET /api/bootstrap/` | Autenticado | Metadados iniciais: `turmas`, `turnos`, `dispositivos`, `settings`, `openAlertsCount` e `cursor` (`lastLogId`, `lastAlertId`). Com `?full=1` inclui listas limitadas para compatibilidade legada. |
| `GET /api/dashboard/` | Autenticado | Agrega no PostgreSQL `summary` (presentes agora via `DISTINCT ON`, atrasos, ausências, alertas abertos), `turmaStats`, últimos 8 `recentes`, 3 `abertos`, `analytics` (5 dias úteis via `TruncDate`), `dispositivos` e `cursor`. |
| `GET /api/live/` | Autenticado | Polling incremental leve. Query: `?since_log_id=0&since_alert_id=0`. Se não houver novidades retorna `changed: false` e arrays vazios; caso contrário retorna `newLogs` (até 50) e `newAlerts` (até 30) ordenados por `id`. |
| `GET /api/logs/` | Autenticado | Histórico paginado (`default=25`). Filtros: `search`, `tipo_pessoa` (`aluno`/`funcionario`), `tipo_evento` (`entrada`/`saida`), `status` (`reconhecido`/`atraso`/`saida-antecipada`/`nao-reconhecido`), `portal`, `de` (`YYYY-MM-DD`), `ate` (`YYYY-MM-DD`). |
| `GET /api/reports/export/` | Autenticado | Exporta até 5.000 linhas em CSV UTF-8 com BOM (`;` separador). Filtros opcionais: `?de=YYYY-MM-DD&ate=YYYY-MM-DD`. Grava auditoria `SELECT` sensível. |

---

## 3. Pessoas e Biometria (Estação de Registro)

`person_ref` aceita os formatos `aluno-<id>` (ex.: `aluno-12`), `funcionario-<id>` (ex.: `funcionario-4`), ou ID numérico legado (`>= 10000` mapeia para funcionário).

| Método & Rota | Auth / RBAC | Descrição e Contratos |
|---|---|---|
| `GET /api/people/` | Autenticado | Listagem paginada (`default=24`). Filtros: `tipo` (`aluno`/`funcionario` ou ambos), `search` (nome/documento com índice `GIN pg_trgm`), `grupo` (turma ou cargo), `status` (`ativo`/`inativo`), `biometria` (`sim`/`nao`). |
| `POST /api/people/` | `admin`, `coordenacao`, `secretaria` | Obrigatórios: `tipo`, `nome`, `documento`, `grupo`, `contatoNome`, `contatoTelefone`. Opcionais: `turmaId`, `turno`, `dataRef` (`YYYY-MM-DD` ou `DD/MM/YYYY`), `consentimentoBiometrico`, `consentimentoResponsavel`, `responsavelCpf` (cifrado em `Responsavel` se 11 dígitos). Retorna `201` ou `409` se documento duplicado. |
| `GET /api/people/<person_ref>/` | Autenticado | Detalhes completos da pessoa (`person`), histórico paginado de passagens (`history` + `historyPagination`, `default=15`, máx. `50`), até 20 `alerts` relacionados e metadados `biometria`. |
| `PATCH /api/people/<person_ref>/` | `admin`, `coordenacao`, `secretaria` | Atualiza `nome`, `documento`, `contatoNome`, `contatoTelefone`, `turno`, `grupo` e/ou `turmaId`. |
| `PATCH /api/people/<person_ref>/status/` | `admin`, `coordenacao`, `secretaria` | Corpo `{"status": "ativo" | "inativo"}`. Pessoas inativas são removidas da galeria ativa da portaria. |
| `POST /api/people/<person_ref>/biometrics/` *(alias `/api/people/<person_ref>/face/`)* | `admin`, `coordenacao`, `secretaria` | Recebe 1 a 5 imagens nos campos multipart `imagens` (ou `imagem`). Extrai template 128-d SFace em RAM, valida nitidez/consistência, cifra em AES-256-GCM e marca consentimento LGPD. Retorna `201` ou `422` com motivo legível se qualidade insuficiente. |
| `DELETE /api/people/<person_ref>/biometrics/` *(alias `/face/`)* | `admin`, `coordenacao`, `secretaria` | Revogação LGPD imediata: apaga vetores da pessoa em `dados_biometricos`, limpa `consentimento_biometrico=False` e grava auditoria `DELETE` sensível. |

---

## 4. Alertas, Turmas, Configurações, Dispositivos e Auditoria

| Método & Rota | Auth / RBAC | Descrição |
|---|---|---|
| `GET /api/alerts/` | Autenticado | Listagem paginada (`default=20`). Filtros: `status` (`abertos`, `novo`, `em-analise`, `resolvido`), `severidade` (`alta`, `media`, `baixa`). Retorna `openCount` e `lastAlertId`. |
| `PATCH /api/alerts/<alert_id>/` *(alias `/resolve/`)* | `admin`, `coordenacao` | Atualiza `status` (`novo`, `em-analise`, `resolvido`) e `observacao`. Ao resolver, registra `resolvido_por` e `resolvido_em`. |
| `GET /api/classes/` | Autenticado | Lista `turmas` e `turnos` ativos. |
| `POST /api/classes/` | `admin`, `coordenacao` | Se `tipo == "turno"`: cria `Turno` (`nome`, `inicio`, `limiteEntrada`, `termino`, `limiteSaidaAntecipada`). Caso contrário cria `Turma` (`nome`, `anoLetivo`, `turnoId`). Retorna `201`, `400` ou `409`. |
| `GET /api/settings/` | Autenticado | Retorna todas as regras globais em `settings`. |
| `PATCH /api/settings/` | `admin`, `coordenacao` | Atualiza configurações escolares (`nomeEscola`, flags `notif*`, `limiteManha`, `limiteTarde`, `saidaManha`, `saidaTarde`, `cooldownSegundos`, `tempoMinimoPermanenciaMin`, `limiarConfianca`, `retencaoLogsDias`, `modoPassivo`). |
| `GET /api/devices/` | `admin`, `coordenacao` | Lista câmeras/terminais cadastrados (`online` é `true` quando ativo e `ultimo_heartbeat <= 90s`). |
| `POST /api/devices/` | `admin`, `coordenacao` | Cria terminal (`nome`, `portal`, `sentidoPadrao`) e gera chave `port_...`, retornando `apiKey` em texto claro **uma única vez** no `201`. |
| `PATCH /api/devices/<device_id>/` | `admin`, `coordenacao` | Atualiza `ativo`, `portal`, `sentidoPadrao` e/ou rotaciona chave com `{"rotacionarChave": true}` (retorna novo `apiKey`). |
| `GET /api/audit/` | `admin`, `coordenacao` | Consulta paginada (`default=20`) de `log_auditoria`. Filtros: `operacao`, `tabela`, `sensivel` (`1`/`0`), `search` (`usuario` ou `chave`). |
| `POST /api/access/` | `admin`, `coordenacao` | Registro manual/teste no motor passivo (`personId`, `tipo`, `portal`, `confianca`, `clientEventId`, `status`). |

---

## 5. Endpoints dos Terminais da Portaria (`X-Portaria-Key`)

| Método & Rota | Descrição e Comportamento |
|---|---|
| `GET /api/portaria/config/` | Retorna `dispositivo` (portal e sentido padrão), `settings` (cooldown e limiar de confiança ativos) e `samplePeople` (até 5 alunos ativos para modo `--demo`/atalho `[T]`). |
| `GET /api/portaria/biometrics/` | Aceita `?version=<hash16>`. Se o hash coincidir com a galeria ativa atual, retorna `{"version": "...", "unchanged": true, "total": N}` sem trafegar vetores. Se diferente, retorna `entries` com vetores `128-d float32` em base64 descriptografados somente em RAM (apenas de pessoas `ativo=True`). |
| `POST /api/portaria/events/` | Recebe um único evento JSON ou `{"events": [...]}` (lote de até **100 eventos**). Atualiza `ultimo_heartbeat`, aplica idempotência por `clientEventId`, cooldown, entrada/saída automática e geração de alertas passivos. Retorna `201` com `results`. |
| `POST /api/portaria/heartbeat/` | Recebe telemetria (`fps`, `aiMs`, `cameraOk`, `enrolledCount`, `pendingQueue`), atualiza `ultimo_heartbeat` + `telemetria` e responde `{"ok": true, "serverTime": "..."}`. |

---

## Exemplos Práticos

### Login e consulta paginada de alunos
```bash
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"coordenacao@escola.edu.br","senha":"Coord@2026"}'

curl -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8000/api/people/?tipo=aluno&biometria=sim&page=1&page_size=24"
```

### Envio de lote da portaria (`X-Portaria-Key`)
```json
POST /api/portaria/events/
X-Portaria-Key: port_...

{
  "events": [
    {
      "clientEventId": "a9f8c7d6e5b443219876543210abcdef",
      "personRef": "aluno-1",
      "tipo": "auto",
      "portal": "Portaria principal",
      "confianca": 0.6842,
      "timestamp": "2026-11-23T10:14:22+00:00"
    }
  ]
}
```
Resposta `201 Created`:
```json
{
  "processed": 1,
  "results": [
    {
      "id": 105,
      "deduplicated": false,
      "ignored": false,
      "personUid": "aluno-1",
      "personName": "Ana Beatriz Silva",
      "personType": "aluno",
      "tipo": "entrada",
      "status": "reconhecido",
      "incidente": false,
      "portal": "Portaria principal",
      "confianca": 0.6842,
      "dataHora": "2026-11-23T07:14:22-03:00",
      "notice": "Entrada registrada: Ana Beatriz Silva",
      "noticeLevel": "ok"
    }
  ]
}
```
