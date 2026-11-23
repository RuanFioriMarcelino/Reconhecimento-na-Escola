# 07 — Instalação, Configuração e Implantação

Este guia cobre desde a configuração local de desenvolvimento (Windows PowerShell e Linux/macOS) até o checklist completo de produção.

---

## 1. Pré-requisitos

- **Python**: 3.11 ou 3.12 (`BackEnd/venv` isolado recomendado)
- **Node.js**: 18+ com npm
- **PostgreSQL**: 14 ou superior (testado no PostgreSQL 17.4) com extensão `pg_trgm` disponível no `contrib` padrão
- **Hardware de câmera**: webcam USB ou câmera IP RTSP (opcional em modo `--demo`)

---

## 2. Configuração Passo a Passo (Desenvolvimento)

### Passo 1 — Criar o Banco de Dados PostgreSQL
No psql ou pgAdmin:
```sql
CREATE DATABASE escola;
```

### Passo 2 — BackEnd (Django + PostgreSQL)

**Windows (PowerShell):**
```powershell
cd BackEnd
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt
Copy-Item .env.example .env
```

**Linux / macOS:**
```bash
cd BackEnd
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edite `BackEnd/.env` ajustando `DATABASE_URL` (ex.: `postgresql://postgres:sua_senha@localhost:5432/escola`) e, em seguida, aplique migrations e dados iniciais:
```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_mock
.\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

> **Credenciais criadas pelo `seed_mock` (somente para desenvolvimento):**
> | Papel RBAC | E-mail | Senha |
> |---|---|---|
> | `admin` | `admin@escola.edu.br` | `Admin@2026` |
> | `coordenacao` | `coordenacao@escola.edu.br` | `Coord@2026` |
> | `secretaria` | `secretaria@escola.edu.br` | `Sec@2026` |

### Passo 3 — FrontEnd (React + Vite)

```powershell
cd FrontEnd
npm.cmd install   # Em PowerShell com ExecutionPolicy restritiva use sempre npm.cmd
npm.cmd run dev
```
> Para apontar o FrontEnd para um servidor remoto ou outra porta, crie `FrontEnd/.env` com `VITE_API_URL=https://api.suaescola.com.br/api`.

### Passo 4 — Módulo de Portaria Passiva

```powershell
cd portaria
Copy-Item .env.example .env
```
Preencha `PORTARIA_DEVICE_KEY` no `portaria/.env` com a chave do dispositivo configurada em `PORTARIA_DEV_KEY` (desenvolvimento) ou gerada no painel Web (**Configurações → Câmeras e terminais de portaria**), e execute:
```powershell
..\BackEnd\venv\Scripts\python.exe reconhecimento.py
```

*(Na primeira execução, se `portaria/models/*.onnx` ainda não estiverem presentes, `models_loader.py` baixa automaticamente os modelos oficiais YuNet ~232 KB e SFace ~38,6 MB do OpenCV Zoo.)*

---

## 3. Referência Completa de Variáveis de Ambiente

### `BackEnd/.env`
| Variável | Padrão (`.env.example`) | Obrigatória em Prod? | Descrição |
|---|---|---|---|
| `DJANGO_DEBUG` | `1` | Sim (`0`) | Modo debug; quando `0` exige HTTPS/HSTS e segredos fortes. |
| `DJANGO_SECRET_KEY` | *(dev-only)* | **Sim** | Mínimo 32 caracteres distintos do valor padrão. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | **Sim** | Lista CSV de domínios/IPs permitidos. |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/escola` | **Sim** | String de conexão PostgreSQL (ou `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`). |
| `FRONTEND_ORIGINS` | `http://localhost:5173,...` | **Sim** | Origens CORS autorizadas (CSV). |
| `BIOMETRIC_MASTER_KEY` | *(vazio em dev)* | **Sim** | Chave Base64 de 32 bytes para AES-256-GCM e HKDF-SHA256. |
| `BIOMETRIC_KEY_ID` | `k1` | Sim | Identificador da chave ativa de criptografia. |
| `BIOMETRIC_PREVIOUS_KEYS` | `{}` | Não | Mapa JSON `{key_id: base64}` com chaves antigas durante rotação. |
| `AUTH_TOKEN_TTL_HOURS` | `12` | Não | Tempo de validade (horas) de cada Bearer Token emitido. |
| `DJANGO_SSL_REDIRECT` | `1` *(quando DEBUG=0)* | Não | Redireciona HTTP→HTTPS; use `0` apenas se proxy já terminar SSL e encaminhar cabeçalho próprio. |
| `PORTARIA_DEV_KEY` | `portaria-dev-key-2026-...` | Não | Chave inicial criada pelo `seed_mock` para a Câmera 01. |

### `FrontEnd/.env` (opcional)
| Variável | Padrão | Descrição |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL da API consumida durante `vite` e embutida no bundle `vite build`. |

### `portaria/.env`
Consulte a tabela detalhada de variáveis `PORTARIA_*` em [05 — Módulo de Portaria e Biometria](05-modulo-portaria.md#configuração-portariaenv-e-execução-cli).

---

## 4. Checklist de Implantação em Produção

1. **Gerar segredos criptográficos exclusivos**:
   ```powershell
   .\BackEnd\venv\Scripts\python.exe -c "import os,base64; print('BIOMETRIC_MASTER_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode()); print('DJANGO_SECRET_KEY=' + base64.urlsafe_b64encode(os.urandom(36)).decode())"
   ```
2. **Ativar modo produção no Django**:
   - Defina `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` com os domínios reais e `FRONTEND_ORIGINS` com a origem HTTPS exata do painel.
   - Sirva o BackEnd via servidor WSGI de produção (`gunicorn school_api.wsgi:application` no Linux ou `waitress-serve` no Windows) atrás de proxy reverso **HTTPS** (Nginx/Caddy), pois `getUserMedia` (WebRTC da webcam no navegador) exige contexto seguro (`https://` ou `localhost`).
3. **Compilar e publicar o FrontEnd**:
   - Defina `VITE_API_URL=https://sua-escola.com.br/api` antes do build.
   - Execute `npm.cmd run build` dentro de `FrontEnd/` e publique `FrontEnd/dist/` no servidor estático/CDN.
4. **Hardening de usuários e dispositivos**:
   - Crie usuários administrativos reais e **desative ou altere as senhas** das contas geradas pelo `seed_mock`.
   - Cadastre cada terminal físico em **Configurações → Câmeras e terminais de portaria** para obter chaves `X-Portaria-Key` exclusivas por porta/totem.
5. **Validar implantação pós-deploy**:
   - Execute `.\BackEnd\venv\Scripts\python.exe manage.py check --deploy`
   - Execute a verificação HTTP ponta a ponta descrita em [08 — Testes e CI/CD](08-testes-ci.md).

---

## 5. Solução de Problemas Comuns (Troubleshooting)

| Sintoma | Causa Provável | Resolução |
|---|---|---|
| `psql` / Django não conecta ao banco | Serviço PostgreSQL parado ou credenciais incorretas no `BackEnd/.env` | Verifique se o serviço `postgresql-x64-*` está em execução e confirme `DATABASE_URL` em `BackEnd/.env`. |
| Erro `UnauthorizedAccess` ao rodar `npm` no PowerShell | Política de execução do Windows bloqueando `npm.ps1` | Use `npm.cmd` (ex.: `npm.cmd run dev`, `npm.cmd run build`, `npm.cmd test`). |
| `AttributeError: module 'cv2' has no attribute 'CascadeClassifier'` | Build recente do OpenCV 5 sem módulo Haar clássico | Este projeto já usa `cv2.FaceDetectorYN` + `cv2.FaceRecognizerSF`. Mantenha os modelos ONNX em `portaria/models/`. |
| Modelos `.onnx` pequenos (~130 bytes) ou falha ao carregar `FaceDetectorYN` | Download antigo de ponteiro Git LFS | Remova os arquivos `.onnx` inválidos e rode `ensure_models` (usa `github.com/opencv/opencv_zoo/raw/main/...` com `allow_redirects=True`). |
| Botão "Abrir câmera de registro" informa contexto não seguro | FrontEnd acessado via `http://IP-DA-REDE:5173` em vez de HTTPS ou `localhost` | Use `http://localhost:5173` localmente, sirva via HTTPS em rede, ou envie uma foto pelo botão **Enviar foto**. |
| Portaria exibe `[!] X-Portaria-Key inválida ou dispositivo desativado` | Chave divergente no `portaria/.env` ou dispositivo desativado | Gere/rotacione a chave no painel Web e atualize `PORTARIA_DEVICE_KEY` no terminal. |
