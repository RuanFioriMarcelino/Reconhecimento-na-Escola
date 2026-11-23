# 08 — Testes Automatizados e Pipeline CI/CD

O projeto conta com uma suíte automatizada em **6 camadas complementares**, cobrindo desde unidades criptográficas isoladas até testes HTTP ponta a ponta contra o PostgreSQL real.

---

## Visão Geral das 6 Camadas

| Camada | Ferramenta | Escopo Coberto | Quantidade / Arquivo(s) |
|---|---|---|---|
| **1. Integridade Django & Migrations** | `manage.py check` + `makemigrations --check` | Consistência de models, settings, URLs e detecção de alterações sem migration | Automático |
| **2. BackEnd (PostgreSQL real)** | `django.test` (`core/tests/`) | Criptografia AES-256-GCM/HKDF/HMAC, RBAC, serviços passivos, biometria, API e implantação (`pg_trgm` + índices + `seed_mock` idempotente + JSON 500) | **34 testes** em 4 arquivos |
| **3. Portaria (Offline & Visão)** | `python -m unittest` (`portaria/tests/`) | `config`, `FaceTracker` multi-rosto, matching vetorizado NumPy (500 vetores), confirmação/cooldown, fila offline SQLite WAL e `HudRenderer` | **11 testes** em [test_portaria.py](../portaria/tests/test_portaria.py) |
| **4. FrontEnd (UI & Fluxos)** | `Vitest` + `Testing Library` + `jsdom` | Helpers defensivos (`seed.js`), cliente HTTP/Bearer/401 (`api.js`), componentes (`PaginationBar`, `Pills`, `ErrorBoundary`, `CameraCaptura`) e fluxos das páginas | **16 testes** em 4 suítes |
| **5. Build de Produção Web** | `Vite` (`npm.cmd run build`) | Empacotamento JS/CSS, resolução de imports e validação de bundle em `FrontEnd/dist/` | Build completo |
| **6. Smoke Test HTTP Pós-Deploy** | [scripts/smoke_deploy.py](../scripts/smoke_deploy.py) | Sobe servidor Django real em porta livre e executa 9 verificações HTTP reais contra o PostgreSQL | **9 verificações** ponta a ponta |

---

## Execução Completa e Individual

### Rodar todas as 6 camadas de uma vez (Windows PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\run_all_tests.ps1"
```
O script [run_all_tests.ps1](../scripts/run_all_tests.ps1) aborta imediatamente (`exit $LASTEXITCODE`) se qualquer etapa falhar.

### Rodar cada camada separadamente

**1 e 2. BackEnd:**
```powershell
cd BackEnd
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations core --check --dry-run
.\venv\Scripts\python.exe manage.py test core --verbosity=2
```
> **Importante**: execute `manage.py test core` estando dentro da pasta `BackEnd/` para garantir a descoberta correta do pacote `core.tests`.

**3. Portaria:**
```powershell
# Na raiz do repositório
.\BackEnd\venv\Scripts\python.exe -m py_compile portaria/*.py
.\BackEnd\venv\Scripts\python.exe -m unittest discover -s portaria/tests -t . -v
```

**4 e 5. FrontEnd (Vitest + Build):**
```powershell
cd FrontEnd
npm.cmd test
npm.cmd run build
```

**6. Smoke Test HTTP de Implantação:**
```powershell
# Na raiz do repositório (requer PostgreSQL rodando e schema migrado)
.\BackEnd\venv\Scripts\python.exe .\scripts\smoke_deploy.py
```

---

## Mapa dos Arquivos de Teste

### BackEnd ([BackEnd/core/tests/](../BackEnd/core/tests/))
- [test_crypto_and_security.py](../BackEnd/core/tests/test_crypto_and_security.py): round-trip de vetores 128-d, validação de dimensão/norma/NaN, falha em adulteração de AAD/tag GCM, rotação com `BIOMETRIC_PREVIOUS_KEYS`, `blind_index`, helpers `fields.py`, tokens expirados/revogados/inativos e rate limit de login.
- [test_services.py](../BackEnd/core/tests/test_services.py): `access_service` (atraso Tarde, `dwell_cooldown`, saída antecipada aluno vs. funcionário, cadastro inativo, desconhecido 20s) e `biometrics` (imagem corrompida, imagem sem face no YuNet real, mocks multi-quadro, divergência entre quadros e desativação de pessoa).
- [test_api_integration.py](../BackEnd/core/tests/test_api_integration.py): fluxo completo HTTP incluindo todos os papéis RBAC (`admin`, `coordenacao`, `secretaria`, `visualizador`), validação de `limiarConfianca` float JS, horários malformados em `/api/classes/`, lote `/api/portaria/events/`, paginação, `/api/live/`, export CSV e JSON `500` sem vazamento de HTML.
- [test_deployment.py](../BackEnd/core/tests/test_deployment.py): ausência de migrations pendentes, presença da extensão `pg_trgm` e dos 15 índices críticos em `pg_indexes`, idempotência de `seed_mock` executado duas vezes seguidas, headers de segurança e CORS whitelist.

### Portaria ([portaria/tests/test_portaria.py](../portaria/tests/test_portaria.py))
- Testa `load_config`, persistência/expiração de IDs em `FaceTracker`, throttle `needs_embedding`, produto matricial em galeria de 500 vetores + rejeição por margem ambígua, fila SQLite WAL persistindo offline e drenando em lote no HTTP 201, além de renderização HUD com acentuação.

### FrontEnd ([FrontEnd/src/__tests__/](../FrontEnd/src/__tests__/))
- [utils.test.js](../FrontEnd/src/__tests__/utils.test.js): `initials`, `avatarColor` e `fmtMin` com entradas nulas/inválidas.
- [api.test.js](../FrontEnd/src/__tests__/api.test.js): Bearer Token, limpeza em `401` e `FormData` biométrico.
- [components.test.jsx](../FrontEnd/src/__tests__/components.test.jsx): `PaginationBar`, `Pills`, `ErrorBoundary` e `CameraCaptura`.
- [pages.test.jsx](../FrontEnd/src/__tests__/pages.test.jsx): `Login`, `Dashboard` (KPIs + retry em erro), `PeopleList` (filtros/paginação), `CadastroFacial` (gate LGPD + retentativa com `savedPersonId`), `Alertas` e `Configuracoes` (modo somente leitura para `secretaria`).

---

## Boas Práticas para Novos Testes

- **Limpe o cache em `setUp()`**: sempre chame `cache.clear()` em testes Django que exercitem `/api/login/`, pois o rate limit persiste em memória entre testes.
- **Isole exceções `IntegrityError` no PostgreSQL**: se testar captura de erro de banco dentro de um `TestCase` (que já roda em transação), envolva a operação sujeita a falha em `with transaction.atomic():` no código de produção para usar savepoint e não abortar a transação principal.
- **Evite dependências de câmera física**: nos testes de portaria/FrontEnd, use mocks de `CameraStream`/`create_face_models`/`fetch` para execução determinística em CI headless.

---

## Pipeline CI/CD (GitHub Actions)

O workflow [.github/workflows/ci.yml](../.github/workflows/ci.yml) executa automaticamente em `push` e `pull_request` nas branches `main` e `desenvolvimento` com dois jobs paralelos:
1. **`backend-and-portaria`**: sobe um container `postgres:17`, aplica `migrate`, popula `seed_mock`, roda os 34 testes Django, os 11 testes da Portaria e o `smoke_deploy.py` HTTP real.
2. **`frontend`**: instala dependências com Node 20 (`npm ci`), roda os testes `Vitest` (`npm test`) e valida `npm run build`.
