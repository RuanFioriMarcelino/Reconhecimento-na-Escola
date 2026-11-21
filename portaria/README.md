# Módulo de Portaria Passiva v2.0 (Alta Performance)

Este módulo opera de forma **totalmente autônoma e passiva** na portaria escolar: ele identifica alunos e funcionários em tempo real, determina automaticamente **Entrada** ou **Saída**, e registra avisos sem bloquear ou exigir autorização manual.

---

## Diferença entre Câmera de Registro e Câmera da Portaria

| Aspecto | Câmera de Registro (Web / `cadastrar_rosto.py`) | Módulo de Portaria (`reconhecimento.py`) |
|---|---|---|
| **Onde roda** | Navegador (`CameraCaptura.jsx`) ou estação CLI da secretaria | Computador/totem dedicado na entrada da escola |
| **Autenticação** | Bearer Token de usuário (`coordenação`/`secretaria`/`admin`) | Chave exclusiva do dispositivo (`X-Portaria-Key`) |
| **O que faz** | Captura 3 quadros nítidos, valida qualidade no servidor e salva vetor 128-d criptografado (AES-256-GCM) no PostgreSQL | Baixa apenas os vetores em RAM, detecta rostos em fluxo contínuo e envia eventos passivos de entrada/saída |
| **Armazenamento em disco** | **Zero** fotos ou vetores salvos em disco | **Zero** fotos em disco; apenas fila offline SQLite WAL (`spool.db`) para eventos pendentes |

---

## Arquitetura Interna (`portaria/`)

- `camera.py` (`CameraStream`): Thread dedicada de captura com `CAP_DSHOW` + `MJPG` no Windows, `BUFFERSIZE=1`, suporte a RTSP e reconexão automática.
- `tracker.py` (`FaceTracker`): Rastreamento multi-rosto por IoU e proximidade para evitar reprocessamento SFace em pessoas já confirmadas.
- `engine.py` (`RecognitionWorker`): Redimensiona o frame para detecção rápida YuNet (`PORTARIA_DETECT_WIDTH=480`) e executa matching vetorizado em NumPy (`matrix @ query`) em < 1 ms.
- `sync_client.py` (`SyncClient`): Fila offline resiliente (`spool.db`), hot-reload da galeria em RAM a cada 30s e heartbeat com telemetria a cada 20s.
- `hud.py` (`HudRenderer`): Interface limpa com FPS, latência da IA, status da conexão e pilha de avisos passivos.

---

## Como Executar

1. Configure `portaria/.env` (copie de `.env.example` e informe a `PORTARIA_DEVICE_KEY`).
2. Inicie a portaria passiva:
```bash
cd portaria
..\BackEnd\venv\Scripts\python.exe reconhecimento.py
```

### Opções CLI úteis
- `--source 1` ou `--source rtsp://usuario:senha@ip:554/stream`: escolhe webcam secundária ou câmera IP.
- `--portal "Catraca lateral"`: sobrescreve o nome do portal.
- `--modo auto|entrada|saida`: força sentido fixo ou mantém alternância automática.
- `--headless`: roda sem abrir janela gráfica (modo servidor/totem).
- `--demo`: modo interativo de terminal para testes sem câmera física.

### Atalhos na janela
- **`[M]`**: Alterna entre `AUTO` (Entrada/Saída automática), `ENTRADA` e `SAIDA`.
- **`[R]`**: Força atualização imediata da galeria biométrica em RAM.
- **`[T]`**: Envia um evento de teste para o backend.
- **`[Q]` ou `[ESC]`**: Encerra todas as threads com segurança.
