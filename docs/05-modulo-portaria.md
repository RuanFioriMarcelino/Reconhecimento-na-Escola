# 05 — Módulo de Portaria Passiva e Cadastro Biométrico

O módulo `portaria/` concentra a visão computacional em tempo real baseada em **OpenCV 5** e modelos ONNX **YuNet** (detecção facial) e **SFace** (extração de assinatura 128-d), operando sob duas finalidades distintas: **Estação de Registro** e **Portaria Passiva Contínua**.

---

## Estação de Registro vs. Portaria Passiva

| Critério | Estação de Registro (`CameraCaptura.jsx` ou `portaria/cadastrar_rosto.py`) | Portaria Passiva (`portaria/reconhecimento.py`) |
|---|---|---|
| **Objetivo** | Cadastrar a biometria oficial com qualidade máxima | Reconhecer passagens contínuas sem interromper o fluxo |
| **Autenticação** | Usuário autenticado (`Bearer Token` + RBAC) | Terminal dedicado (`X-Portaria-Key`) |
| **Entrada de imagem** | 3 quadros parados via WebRTC / OpenCV ou foto enviada | Stream contínuo de webcam (`CAP_DSHOW`/`MJPG`), câmera IP (`RTSP`) ou vídeo |
| **Critérios de validação** | Rosto único, `det_score >= 0.80`, rosto `>= 60x60 px`, nitidez Laplaciana `>= 25.0`, consistência entre quadros `>= 0.45` | Rastreamento multi-rosto, redimensionamento para `480px`, confirmação em `2` quadros e similaridade cosseno com margem |
| **Persistência local** | Zero armazenamento em disco | Apenas fila de eventos offline SQLite WAL (`portaria/spool.db`); zero fotos em disco |

---

## Arquitetura Interna da Portaria (`portaria/`)

| Arquivo | Classe / Função | Responsabilidade |
|---|---|---|
| [config.py](../portaria/config.py) | `PortariaConfig`, `load_config` | Lê `portaria/.env` + overrides CLI (`--source`, `--portal`, `--modo`, `--headless`) e sanitiza `modo` (`auto`/`entrada`/`saida`). |
| [models_loader.py](../portaria/models_loader.py) | `ensure_models`, `create_face_models` | Verifica/baixa os modelos `face_detection_yunet_2023mar.onnx` e `face_recognition_sface_2021dec.onnx` em `portaria/models/` e instancia `cv2.FaceDetectorYN` + `cv2.FaceRecognizerSF`. |
| [camera.py](../portaria/camera.py) | `CameraStream` | Thread dedicada de captura sem fila acumulada (`BUFFERSIZE=1`, `MJPG`, `CAP_DSHOW` no Windows), cálculo de FPS real e reconexão automática com backoff exponencial. |
| [tracker.py](../portaria/tracker.py) | `FaceTracker`, `TrackedFace` | Associa rostos entre frames via IoU (`>= 0.25`) e distância normalizada de centróide (`<= 0.65`), expirando após `0.9s` e limitando reextrações SFace (`needs_embedding`). |
| [engine.py](../portaria/engine.py) | `RecognitionWorker` | Redimensiona frame para `detect_width` (padrão `480px`), executa YuNet, extrai embedding SFace em tracks pendentes, faz matching vetorizado em NumPy (`matrix @ q`) e dispara eventos/avisos após `confirm_frames`. |
| [sync_client.py](../portaria/sync_client.py) | `SyncClient` | Thread de sincronização com `spool.db` (SQLite WAL), flush em lotes de 25 eventos para `/api/portaria/events/`, hot-reload de vetores em RAM a cada `30s`, config remota e heartbeat a cada `20s`. |
| [hud.py](../portaria/hud.py) | `HudRenderer` | Desenha HUD passivo no OpenCV com cantoneiras, percentual de confiança, FPS, tempo de IA (`ms`), status `API ONLINE`/`OFFLINE (FILA: N)` e pilha discreta de avisos (ASCII seguro para fontes OpenCV). |
| [reconhecimento.py](../portaria/reconhecimento.py) | `main`, `executar_modo_demo` | Orquestrador CLI com modos gráfico, `--headless` e `--demo` (simulação sem câmera). |
| [cadastrar_rosto.py](../portaria/cadastrar_rosto.py) | `capturar_da_camera` | Estação CLI alternativa via OpenCV para capturar 3 quadros (`ESPAÇO`) ou enviar `--imagem` autenticando como operador humano. |

> **Nota sobre OpenCV 5**: a base utiliza exclusivamente `cv2.FaceDetectorYN` e `cv2.FaceRecognizerSF` (sem `cv2.CascadeClassifier`, removido nessa build do OpenCV), protegendo chamadas de inferência no servidor com `_INFERENCE_LOCK` em [biometrics.py](../BackEnd/core/services/biometrics.py).

---

## Algoritmo de Matching e Regras do Motor Passivo

### Matching Vetorizado na Portaria (`engine.py`)
1. A galeria ativa recebida do servidor é mantida em uma matriz NumPy contígua `(N, 128)` `float32` com vetores já L2-normalizados.
2. Para cada vetor consultado `q`, a similaridade cosseno com toda a escola é calculada em menos de 1 ms com um único produto matricial `scores = matrix @ q`.
3. Um candidato só é aceito quando atende **ambas** as condições:
   - `best_score >= cosine_threshold` (padrão `0.380`, sincronizado dinamicamente com `ConfiguracaoEscola.limiar_confianca`);
   - Caso haja mais de uma pessoa na galeria, diferença entre 1º e 2º colocados `margin >= margin_threshold` (padrão `0.04`), evitando falsos positivos em rostos ambíguos.
4. É necessária confirmação consistente em `confirm_frames` quadros (padrão `2`) antes de enfileirar o evento, respeitando cooldown local para não inundar o servidor enquanto a pessoa permanece em frente à câmera.
5. Um rosto não reconhecido que permaneça visível por `>= unknown_seconds` (padrão `2.5s`) envia evento passivo anônimo (`personRef = null`) com intervalo mínimo de `20s`.

### Regras no Servidor (`BackEnd/core/services/access_service.py`)
Ao receber o evento, `processar_passagem()` nunca bloqueia a passagem e aplica em sequência:
1. **Idempotência**: se `client_event_id` já existir em `registro_acesso`, retorna `deduplicated: True` sem duplicar linha.
2. **Cooldown anti-duplicidade**:
   - Pessoa cadastrada: ignora se houve passagem nos últimos `cooldown_segundos` (padrão `45s`).
   - Rosto não cadastrado: ignora se houve desconhecido no mesmo portal nos últimos `20s`.
3. **Alternância Entrada / Saída (`modo = auto`)**:
   - Sem registro prévio no dia (ou se o último foi `saida`): grava **`entrada`**.
   - Se já há `entrada` no dia e o intervalo for menor que `tempo_minimo_permanencia_min` (padrão `2 min`): ignora com motivo `dwell_cooldown`.
   - Após o tempo mínimo de permanência: grava **`saida`**.
4. **Classificação e Alertas Automáticos**:
   - **Cadastro inativo**: grava passagem com `incidente=True` e cria alerta `alta` ("Cadastro inativo na portaria").
   - **Atraso**: `entrada` após o `limite_entrada` do turno gera status `atraso` e alerta `media`.
   - **Saída antecipada**: `saida` de **aluno** antes de `limite_saida_antecipada` gera status `saida-antecipada` e alerta `media` (funcionários não disparam saída antecipada).
   - **Não reconhecido**: grava com `status="nao-reconhecido"` e cria alerta `alta` se `notif_nao_reconhecido` estiver ligado.

---

## Configuração (`portaria/.env`) e Execução CLI

| Variável | Padrão | Descrição |
|---|---|---|
| `PORTARIA_API_URL` | `http://localhost:8000/api` | URL base da API Django. |
| `PORTARIA_DEVICE_KEY` | *(vazio)* | Chave `X-Portaria-Key` gerada no painel Web. |
| `PORTARIA_SOURCE` | `0` | Índice da webcam (`0`, `1`), URL `rtsp://...` ou caminho de arquivo `.mp4`. |
| `PORTARIA_PORTAL` | `Portaria principal` | Nome exibido no HUD e fallback caso o servidor esteja offline. |
| `PORTARIA_MODO` | `auto` | Sentido padrão: `auto`, `entrada` ou `saida`. |
| `PORTARIA_WIDTH` / `PORTARIA_HEIGHT` | `960` / `540` | Resolução solicitada à câmera. |
| `PORTARIA_DETECT_WIDTH` | `480` | Largura de redimensionamento usada pela detecção YuNet. |
| `PORTARIA_CONFIRM_FRAMES` | `2` | Quadros consistentes antes de registrar passagem. |
| `PORTARIA_COOLDOWN` | `45` | Cooldown local (segundos) por pessoa reconhecida. |
| `PORTARIA_UNKNOWN_SECONDS` | `2.5` | Tempo mínimo em cena para reportar rosto desconhecido. |
| `PORTARIA_THRESHOLD` / `PORTARIA_MARGIN` | `0.380` / `0.04` | Limiar cosseno e margem mínima entre 1º e 2º candidato. |
| `PORTARIA_HEADLESS` | `0` | `1` executa sem abrir janela OpenCV (`cv2.imshow`). |

### Comandos Práticos e Atalhos
```powershell
# Portaria padrão (webcam 0 + janela HUD)
.\BackEnd\venv\Scripts\python.exe .\portaria\reconhecimento.py

# Câmera IP RTSP sem interface gráfica (totem/servidor Linux)
.\BackEnd\venv\Scripts\python.exe .\portaria\reconhecimento.py --source "rtsp://usuario:senha@192.168.0.50:554/stream" --portal "Catraca lateral" --headless

# Modo demonstração interativo no terminal (sem câmera)
.\BackEnd\venv\Scripts\python.exe .\portaria\reconhecimento.py --demo

# Estação CLI de cadastro biométrico
.\BackEnd\venv\Scripts\python.exe .\portaria\cadastrar_rosto.py --id aluno-1
```

Atalhos no teclado durante a janela do HUD:
- **`[M]`**: alterna entre `AUTO` → `ENTRADA` → `SAIDA`.
- **`[R]`**: força sincronização imediata da galeria biométrica em RAM.
- **`[T]`**: envia passagem de teste com um cadastro de amostra (`samplePeople`).
- **`[Q]`** ou **`[ESC]`**: encerra câmera, worker de IA e flush da fila `spool.db` com segurança.
