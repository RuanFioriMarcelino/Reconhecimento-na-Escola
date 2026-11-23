# Documentação Técnica — Reconhece+ v2.0

Bem-vindo à documentação oficial do **Reconhece+ v2.0**, uma plataforma comercial de controle de frequência e monitoramento escolar baseada em reconhecimento facial passivo, criptografia autenticada **AES-256-GCM**, conformidade com a **LGPD (Lei nº 13.709/2018)** e persistência exclusiva em **PostgreSQL 14+**.

---

## Mapa da Documentação

| Documento | Conteúdo Principal | Público-alvo |
|---|---|---|
| [01 — Arquitetura do Sistema](01-arquitetura.md) | Subsistemas desacoplados, diagramas de fluxo, cadastro vs. portaria passiva e decisões de engenharia | Arquitetos e Desenvolvedores |
| [02 — Banco de Dados (PostgreSQL)](02-banco-de-dados.md) | Diagrama ER (14 tabelas + `auth_user`), constraints, índices `GIN pg_trgm`/parciais, migrations e backup | DBAs e Desenvolvedores BackEnd |
| [03 — Referência da API REST](03-api-referencia.md) | Todos os 27 endpoints HTTP, matriz RBAC, paginação, limites de payload e exemplos JSON | Integradores e Desenvolvedores Full-Stack |
| [04 — Segurança e LGPD](04-seguranca-lgpd.md) | HKDF-SHA256 + AES-256-GCM com AAD, rotação de chaves, HMAC blind index, tokens SHA-256, rate limit e auditoria | Segurança, DPO / LGPD e Auditores |
| [05 — Módulo de Portaria e Biometria](05-modulo-portaria.md) | Pipeline OpenCV 5 (YuNet + SFace ONNX), tracker IoU, motor passivo Entrada/Saída e fila offline SQLite WAL | Engenharia de Visão e Implantação de Campo |
| [06 — Guia do Front-end](06-frontend-guia.md) | React 18 + Vite + Tailwind, cliente HTTP (`api.js`), polling incremental `/api/live/`, webcam WebRTC e resiliência de UI | Desenvolvedores FrontEnd |
| [07 — Instalação e Implantação](07-instalacao-implantacao.md) | Setup Windows/Linux, variáveis `.env`, checklist de produção (`DJANGO_DEBUG=0`, HTTPS/WSGI) e troubleshooting | DevOps e Implantadores |
| [08 — Testes e CI/CD](08-testes-ci.md) | Suíte automatizada em 6 camadas (61 testes + build + smoke HTTP), runner PowerShell e GitHub Actions | QA, Desenvolvedores e DevOps |

---

## Guias Rápidos por Perfil

### 1. Para Desenvolvedores (Onboarding rápido)
1. Leia a visão arquitetural em [01 — Arquitetura do Sistema](01-arquitetura.md).
2. Suba o ambiente local seguindo [07 — Instalação e Implantação](07-instalacao-implantacao.md).
3. Consulte o modelo relacional em [02 — Banco de Dados](02-banco-de-dados.md) e os contratos em [03 — Referência da API REST](03-api-referencia.md).
4. Execute todas as verificações com `.\scripts\run_all_tests.ps1` conforme [08 — Testes e CI/CD](08-testes-ci.md).

### 2. Para DevOps e Implantação em Produção
1. Siga o **Checklist de Produção** em [07 — Instalação e Implantação](07-instalacao-implantacao.md).
2. Configure `BIOMETRIC_MASTER_KEY`, rotação de chaves e políticas HTTP descritas em [04 — Segurança e LGPD](04-seguranca-lgpd.md).
3. Cadastre cada câmera/totem da portaria gerando uma chave `X-Portaria-Key` individual e valide o deploy com [scripts/smoke_deploy.py](../scripts/smoke_deploy.py).

### 3. Para Operação Escolar (Coordenação e Secretaria)
- **Estação de Cadastro (`FrontEnd` ou `portaria/cadastrar_rosto.py`)**: registra alunos e funcionários com termo de consentimento LGPD e extrai o vetor facial em 3 quadros. Consulte [05 — Módulo de Portaria e Biometria](05-modulo-portaria.md) e [06 — Guia do Front-end](06-frontend-guia.md).
- **Portaria Passiva (`portaria/reconhecimento.py`)**: identifica entradas e saídas automaticamente em movimento contínuo, sem travar a fila nem pedir autorização manual, gerando avisos discretos e alertas para a coordenação.

### 4. Para Auditoria e Conformidade (LGPD)
- Nenhuma fotografia é gravada em disco no servidor ou nos terminais da portaria — apenas vetores numéricos de 128 dimensões cifrados com **AES-256-GCM** e AAD por titular.
- Consulte todos os mecanismos técnicos, trilha `log_auditoria`, retenção configurável e revogação imediata de biometria em [04 — Segurança e LGPD](04-seguranca-lgpd.md).
