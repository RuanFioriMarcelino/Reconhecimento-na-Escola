# 01 — Arquitetura do Sistema

O **Reconhece+ v2.0** foi projetado como uma plataforma desacoplada em três subsistemas independentes que se comunicam exclusivamente via HTTP/JSON sobre API REST autenticada, permitindo escalar o painel web, o servidor central e múltiplos terminais físicos de portaria sem acoplamento de código ou banco compartilhado em rede local.

---

## Visão Macro dos Subsistemas

```mermaid
flowchart LR
    subgraph Estacao["Estação Administrativa (Navegador)"]
        FE["FrontEnd React 18 + Vite"]
        REG["CameraCaptura.jsx (WebRTC 3 quadros)"]
    end

    subgraph Portaria["Módulo de Portaria Passiva (Python / Totem)"]
        CAM["CameraStream (CAP_DSHOW / RTSP)"]
        TRK["FaceTracker (IoU multi-rosto)"]
        ENG["RecognitionWorker (YuNet + SFace + NumPy)"]
        SYN["SyncClient (Spool SQLite WAL + RAM)"]
        CAM --> TRK --> ENG --> SYN
    end

    subgraph Core["BackEnd API & Persistência"]
        MW["AuditMiddleware + SecurityMiddleware"]
        API["Django 5 Views + RBAC + Rate Limit"]
        BIO["biometrics.py & access_service.py"]
        CRP["crypto/cipher.py (AES-256-GCM + HKDF)"]
        PG[("PostgreSQL 14+ (14 tabelas + pg_trgm)")]
        MW --> API --> BIO --> CRP --> PG
    end

    FE -- "Bearer Token (CORS Restrito)" --> MW
    REG -- "POST /api/people/<ref>/biometrics/" --> MW
    SYN -- "X-Portaria-Key (/api/portaria/*)" --> MW
```

### Papéis de cada componente
1. **Estação Web (`FrontEnd/`)**: interface SPA em React 18 para gestão de alunos, funcionários, cadastro biométrico com consentimento LGPD, monitoramento em tempo real, tratamento de alertas, exportação de relatórios CSV, administração de dispositivos de portaria e consulta de auditoria.
2. **Core API & Regras (`BackEnd/`)**: servidor Django 5 sem SQLite (exclusivo **PostgreSQL**), responsável por autenticação (`AuthToken` SHA-256 + sessão Django), autorização por papéis (RBAC), extração e validação biométrica no cadastro, criptografia **AES-256-GCM**, regras passivas de acesso (`access_service.py`), agregações SQL e exposição de `/api/portaria/*`.
3. **Terminal Passivo de Portaria (`portaria/`)**: processo Python multi-thread projetado para rodar localmente junto à câmera da entrada/saída (webcam USB ou stream RTSP IP). Opera em alta taxa de quadros com detecção redimensionada, rastreamento multi-rosto e matching vetorizado em memória RAM — continuando operacional mesmo se a rede com o servidor cair temporariamente.

---

## Fluxo 1 — Estação de Cadastro Biométrico

Diferentemente da portaria, o cadastro exige qualidade rigorosa e consentimento expresso antes de gerar o template biométrico oficial:

```mermaid
sequenceDiagram
    actor Op as Operador (Secretaria / Coordenação)
    participant FE as FrontEnd (CadastroFacial + CameraCaptura)
    participant API as Django Views (/api/people/)
    participant BIO as biometrics.py (YuNet + SFace RAM)
    participant CRP as crypto/cipher.py (AES-256-GCM)
    participant DB as PostgreSQL

    Op->>FE: Preenche dados cadastrais + marca Termo LGPD
    Op->>FE: Captura 3 quadros via WebRTC (ou envia foto)
    FE->>API: POST /api/people/ (JSON)
    API->>DB: Cria Aluno/Funcionario + Responsavel cifrado (HMAC cpf_hash)
    DB-->>API: personId (ex: aluno-12)
    API-->>FE: HTTP 201 Created

    FE->>API: POST /api/people/aluno-12/biometrics/ (multipart até 5 imagens)
    Note over FE,API: Se a validação biométrica falhar (422), savedPersonId é preservado para retentativa sem duplicar a pessoa.
    API->>BIO: extract_biometric_template(raw_images em RAM)
    BIO->>BIO: Valida rosto único, det_score >= 0.80, >= 60px, Laplacian >= 25.0, consistência >= 0.45
    BIO->>BIO: Calcula média dos 3 vetores SFace e normaliza L2 (128-d float32)
    BIO->>CRP: encrypt_vector(vetor, AAD="aluno:12")
    CRP-->>BIO: blob (nonce 12B + ciphertext + tag GCM), key_id
    BIO->>DB: Desativa templates anteriores + insere DadoBiometrico ativo + registra LogAuditoria (sensivel=True)
    Note over BIO: Nenhuma imagem JPEG/PNG é gravada em disco.
    API-->>FE: HTTP 201 (biometriaId, qualidade, keyId)
```

---

## Fluxo 2 — Portaria Passiva em Tempo Real

Na portaria da escola, o fluxo nunca bloqueia passagens nem pede confirmação humana:

```mermaid
sequenceDiagram
    participant CAM as CameraStream (Thread 1)
    participant ENG as RecognitionWorker (Thread 2)
    participant SYN as SyncClient (Thread 3 + spool.db WAL)
    participant API as BackEnd (/api/portaria/*)
    participant SVC as access_service.py + PostgreSQL
    participant FE as Painel Web (/api/live/)

    Note over SYN,API: Boot + polling a cada 30s (GET /api/portaria/biometrics/?version=...)
    API-->>SYN: Vetores descriptografados em RAM (base64 float32 128-d)
    SYN-->>ENG: update_gallery() -> matriz NumPy (N x 128) em RAM

    loop Captura contínua sem buffer acumulado
        CAM-->>ENG: Frame mais recente
        ENG->>ENG: YuNet em largura detect_width (480px) -> FaceTracker (IoU)
        ENG->>ENG: Para tracks pendentes: SFace feature() -> matrix @ query (< 1ms)
        alt Reconhecido por confirm_frames (padrão 2) e fora do cooldown local
            ENG->>SYN: enqueue_event(uid, modo, portal, confianca)
        else Rosto desconhecido persistente (>= 2.5s)
            ENG->>SYN: enqueue_event(None, modo, portal, None)
        end
    end

    SYN->>SYN: Grava evento em SQLite WAL (spool.db) com clientEventId UUID
    SYN->>API: POST /api/portaria/events/ (lote até 25 eventos + X-Portaria-Key)
    API->>SVC: processar_passagem() (idempotência -> cooldown -> auto Entrada/Saída)
    SVC-->>API: RegistroAcesso + Alerta (se atraso / saída antecipada / desconhecido / inativo)
    API-->>SYN: notice + noticeLevel -> exibe aviso discreto no HUD e remove do spool

    loop Polling leve no FrontEnd a cada 3s (somente aba visível)
        FE->>API: GET /api/live/?since_log_id=X&since_alert_id=Y
        API-->>FE: Delta newLogs / newAlerts + status câmeras + liveTick
    end
```

---

## Principais Decisões Arquiteturais

### 1. Separação estrita entre Estação de Registro e Portaria
- **Por quê**: a estação de cadastro precisa exigir rosto único, imóvel, nítido e bem iluminado (3 quadros com consistência matemática verificada no servidor). Já a portaria precisa processar múltiplos alunos caminhando simultaneamente em 30 FPS com baixa latência, sem travar caso uma pessoa passe rápido.
- **Resultado**: cada ambiente tem sua própria câmera, algoritmo de validação, forma de autenticação (`Bearer Token` humano vs. `X-Portaria-Key` de máquina) e interface visual.

### 2. PostgreSQL exclusivo no servidor e zero SQLite em produção
- O servidor BackEnd (`BackEnd/school_api/settings.py`) utiliza exclusivamente `django.db.backends.postgresql`, garantindo integridade referencial forte (`CHECK constraints`), tipos nativos (`INET`, `JSONB`, `BYTEA`), extensão `pg_trgm` para buscas parciais indexadas e `DISTINCT ON` para cálculo instantâneo de quem está dentro da escola.
- O único SQLite existente no projeto fica **isolado no terminal de campo (`portaria/spool.db`)**, em modo `WAL`, atuando exclusivamente como buffer offline temporário caso o totem perca internet/Wi-Fi.

### 3. Privacidade by Design (Zero Fotos em Disco)
- Imagens capturadas na estação de registro são decodificadas e descartadas em memória RAM após extração do embedding SFace de 128 dimensões.
- No módulo de portaria, os quadros da webcam também trafegam apenas em RAM para extração de características e comparação contra a matriz NumPy carregada via API.

### 4. Escalabilidade de Consultas e Tempo Real Leve
- **Paginação server-side**: todas as listagens potencialmente grandes (`/api/people/`, `/api/logs/`, `/api/alerts/`, `/api/audit/`, histórico em `/api/people/<ref>/`) paginam no PostgreSQL com limites configuráveis (`page_size` até `100`).
- **Sync incremental (`/api/live/`)**: em vez de recarregar o banco inteiro a cada atualização, o FrontEnd envia `since_log_id` e `since_alert_id`. Quando não há eventos novos, a API responde com `changed: false` em ~250 bytes, e o polling pausa automaticamente quando a aba do navegador está em segundo plano (`document.visibilityState`).
