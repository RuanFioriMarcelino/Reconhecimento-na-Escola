# 04 — Segurança e Conformidade LGPD

O **Reconhece+ v2.0** aplica controles criptográficos, isolamento de credenciais e princípios da **Lei Geral de Proteção de Dados (Lei nº 13.709/2018)** por padrão em todas as camadas.

---

## Arquitetura Criptográfica (`BackEnd/core/crypto/`)

Toda operação de cifragem simétrica e índice cego está centralizada em [cipher.py](../BackEnd/core/crypto/cipher.py) e [fields.py](../BackEnd/core/crypto/fields.py).

### 1. Derivação de Chave Mestra e Subchaves (HKDF-SHA256)
- A chave mestra de 32 bytes é lida de `BIOMETRIC_MASTER_KEY` (base64/urlsafe-base64 ou passphrase >= 32 bytes).
- **Em produção (`DJANGO_DEBUG=0`)**: a ausência de `BIOMETRIC_MASTER_KEY` bloqueia a inicialização da aplicação (`RuntimeError` em `settings.py` e `cipher.py`). Em desenvolvimento (`DJANGO_DEBUG=1`), existe fallback determinístico derivado de `SECRET_KEY`.
- A partir da chave mestra, subchaves isoladas de 256 bits são derivadas via **HKDF-SHA256** (`salt = b"reconhece-escola-v2"`), separando os contextos criptográficos por `info`:
  - `biometrics` — vetores biométricos faciais.
  - `pii` — dados pessoais de responsáveis (`cpf_enc`, `phone_enc`, `email_enc`).
  - `blind_index:<purpose>` — índice cego HMAC-SHA256 (ex.: `blind_index:cpf`).

### 2. Cifragem Autenticada de Vetores Biométricos (AES-256-GCM + AAD)
Antes de gravar na tabela `dados_biometricos`, o vetor 128-d `float32`:
1. É validado (128 dimensões exatas, valores finitos, norma > `1e-8`) e L2-normalizado.
2. Recebe um **nonce aleatório de 12 bytes** (`os.urandom(12)`).
3. É cifrado com **AES-256-GCM** vinculando o **AAD (Additional Authenticated Data)** igual a `<owner_type>:<owner_id>` (por exemplo, `aluno:42`).
4. É persistido no PostgreSQL como `nonce (12B) + ciphertext + tag GCM (16B)`, acompanhado do identificador `key_id`.

> **Por que AAD importa**: mesmo que um invasor com acesso direto ao banco copie a coluna `vetor_enc` do registro de um aluno para outro, a verificação da tag GCM falha imediatamente na descriptografia (`InvalidTag`), impedindo troca de identidade biométrica no banco.

### 3. Dados Sensíveis de Responsáveis e Índice Cego HMAC-SHA256
Quando o CPF de um responsável (11 dígitos) é informado no cadastro de aluno:
- CPF e telefone são cifrados com `encrypt_text(...)` usando propósito `"pii"`.
- A unicidade e busca em `responsavel.cpf_hash` usam `blind_index(cpf, purpose="cpf")`, calculado via **HMAC-SHA256** com subchave derivada de HKDF — permitindo localizar responsáveis existentes sem nunca armazenar o CPF em texto claro ou usar hash simples vulnerável a rainbow tables.
- Utilitários em `fields.py` oferecem normalização e mascaramento (`mask_cpf` → `***.456.789-**`, `mask_phone` → `***-7766`, `clean_str`).

### 4. Rotação de Chaves (`BIOMETRIC_KEY_ID` e `BIOMETRIC_PREVIOUS_KEYS`)
O esquema suporta rotação de chaves sem derrubar o sistema ou invalidar biometrias antigas:
1. Gere uma nova chave mestra de 32 bytes:
   ```powershell
   .\BackEnd\venv\Scripts\python.exe -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
   ```
2. Mova a chave atual para `BIOMETRIC_PREVIOUS_KEYS` mapeada pelo ID antigo e defina os novos valores em `BackEnd/.env`:
   ```env
   BIOMETRIC_MASTER_KEY=<NOVA_CHAVE_BASE64>
   BIOMETRIC_KEY_ID=k2
   BIOMETRIC_PREVIOUS_KEYS={"k1":"<CHAVE_ANTIGA_BASE64>"}
   ```
3. Novos cadastros passam a gravar com `key_id="k2"`, enquanto `decrypt_vector`/`decrypt_text` continuam lendo blobs `k1` transparentemente via `BIOMETRIC_PREVIOUS_KEYS`.

---

## Autenticação, Rate Limit e Controle de Acesso

Implementado em [BackEnd/core/security.py](../BackEnd/core/security.py):

- **Bearer Tokens Opacos com Hash SHA-256 (`AuthToken`)**:
  - Prefixo identificável `rne_` + 32 bytes aleatórios (`secrets.token_urlsafe(32)`).
  - Apenas `sha256(token)` vai para a tabela `auth_token`; o segredo bruto é devolvido ao cliente apenas no momento do login.
  - Expiração configurável via `AUTH_TOKEN_TTL_HOURS` (padrão `12h`), verificação de usuário ativo (`user.is_active`), atualização de `ultimo_uso_em` e revogação instantânea no `POST /api/logout/`.
- **Proteção contra Força Bruta no Login**:
  - `check_login_rate_limit` / `record_login_failure`: bloqueia após **5 tentativas falhas em 300 segundos** por par `(ip, email)` retornando HTTP `429` e gravando auditoria sensível (`rate_limited`).
  - Sucesso no login limpa o contador imediatamente (`clear_login_failures`).
- **RBAC por Papéis (`PerfilUsuario`)**:
  - Quatro perfis previstos no decorator `@require_auth([...])`: `admin`, `coordenacao`, `secretaria` e `visualizador`.
- **Chaves de Terminal da Portaria (`X-Portaria-Key`)**:
  - Geradas com prefixo `port_` (`generate_secret("port")`), armazenadas em SHA-256 (`api_key_hash`) em `dispositivo_portaria`.
  - Dispositivos desativados (`ativo=False`) passam a receber `401` imediatamente, e chaves comprometidas podem ser rotacionadas via `PATCH /api/devices/<id>/`.

---

## Conformidade com a LGPD (Lei nº 13.709/2018)

| Princípio / Direito LGPD | Implementação Técnica no Reconhece+ |
|---|---|
| **Consentimento Expresso** | Cadastro biométrico no FrontEnd exige marcação explícita do Termo LGPD antes de aceitar captura facial; backend registra `consentimento_biometrico`, `consentimento_em` e `consentimento_responsavel`. |
| **Minimização e Necessidade** | **Zero fotografias armazenadas** no PostgreSQL ou no disco da portaria. Os quadros são processados em memória RAM para gerar apenas o vetor matemático 128-d cifrado. |
| **Direito de Revogação / Eliminação** | Botão **Revogar biometria (LGPD)** no perfil (`DELETE /api/people/<ref>/biometrics/`) exclui os templates biométricos do titular, limpa flags de consentimento e remove o titular da próxima sincronização da portaria. |
| **Transparência e Rastreabilidade** | Toda operação sensível (login falho/bloqueado, cadastro/revogação biométrica, rotação de chave de câmera, alteração de configurações e exportação CSV) gera evento em `log_auditoria` com timestamp, autor, IP e flag `sensivel=True`. |
| **Limitação de Retenção** | Campo `retencao_logs_dias` (entre `30` e `3650` dias, padrão `365`) em `configuracao_escola` parametriza a janela de guarda operacional de logs da escola. |

---

## Hardening HTTP e Configurações de Produção

- **Middleware de Auditoria e Segurança** ([BackEnd/core/middleware/audit.py](../BackEnd/core/middleware/audit.py)):
  - Injeta `X-Request-ID` em toda resposta HTTP.
  - Envia `Permissions-Policy: camera=(self)` e `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` em toda rota `/api/`.
  - Intercepta exceções não tratadas em `/api/` retornando JSON `500` seguro sem vazar stack trace quando `DJANGO_DEBUG=0`.
- **CORS Estrito**: controlado por `FRONTEND_ORIGINS` (`CORS_ALLOW_CREDENTIALS = True`, `CORS_ALLOW_HEADERS` explícito incluindo `authorization` e `x-portaria-key`).
- **Headers de Produção (`DJANGO_DEBUG=0` em [settings.py](../BackEnd/school_api/settings.py))**:
  - Exige `DJANGO_SECRET_KEY` diferente do padrão e com >= 32 caracteres + `BIOMETRIC_MASTER_KEY` preenchida.
  - Ativa `SECURE_SSL_REDIRECT` (configurável via `DJANGO_SSL_REDIRECT`), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS = 31536000` e `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`.
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`, `X_FRAME_OPTIONS = "DENY"`, `SESSION_COOKIE_HTTPONLY = True`, `CSRF_COOKIE_HTTPONLY = True`.
