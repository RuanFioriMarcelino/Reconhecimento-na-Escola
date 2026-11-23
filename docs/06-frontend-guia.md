# 06 — Guia do Front-end (Painel Web)

O painel administrativo e estação web de cadastro biométrico é uma SPA construída com **React 18.3**, **Vite 5.4** e **Tailwind CSS 4.3** (com tokens migrados gradualmente de `legacy.css` em `FrontEnd/src/index.css`).

---

## Organização de Diretórios (`FrontEnd/src/`)

| Caminho | Finalidade |
|---|---|
| [main.jsx](../FrontEnd/src/main.jsx) | Ponto de entrada React envolvido em `ErrorBoundary` e `React.StrictMode`. |
| [App.jsx](../FrontEnd/src/App.jsx) | Estado global de sessão, metadados (`turmas`, `turnos`, `dispositivos`, `settings`), polling `/api/live/` e roteamento. |
| [router/useHashRoute.js](../FrontEnd/src/router/useHashRoute.js) | Roteamento leve por `window.location.hash` (`#/dashboard`, `#/pessoa/aluno/aluno-1`, etc.) + array `NAV`. |
| [lib/api.js](../FrontEnd/src/lib/api.js) | Cliente HTTP `fetch` com Bearer Token em `sessionStorage`, interceptação global de `401`, upload `FormData` e download CSV. |
| [components/](../FrontEnd/src/components/) | `ErrorBoundary.jsx`, `CameraCaptura.jsx`, `PaginationBar.jsx`, `Pills.jsx`, `Avatar.jsx`, `RingChart.jsx`, `Sidebar.jsx`, `Topbar.jsx`, `Toast.jsx`. |
| [data/seed.js](../FrontEnd/src/data/seed.js) | Constantes de domínio (`PERSON_CONFIG`, `CARGOS`, `TURMAS`) e helpers formatadores defensivos (`initials`, `avatarColor`, `fmtMin`). |
| [pages/](../FrontEnd/src/pages/) | Páginas funcionais agrupadas por domínio. |

---

## Mapa de Telas e Funcionalidades

| Rota Hash | Componente | Funcionalidades Principais |
|---|---|---|
| *(não autenticado)* | [Login.jsx](../FrontEnd/src/pages/login/Login.jsx) | Autenticação institucional por e-mail/senha, exibição de erro (`401`/`429`) e armazenamento do Bearer Token. |
| `#/dashboard` | [Dashboard.jsx](../FrontEnd/src/pages/dashboard/Dashboard.jsx) | KPIs do dia (presentes agora, atrasos, ausências, alertas abertos), status online das câmeras, passagens recentes, frequência por turma e resumo de equipe. |
| `#/alunos` / `#/funcionarios` | [PeopleList.jsx](../FrontEnd/src/pages/pessoas/PeopleList.jsx) | Listagem paginada no servidor, busca com debounce de `300ms`, filtro por turma/cargo e filtro de status biométrico (`ativa`/`pendente`). |
| `#/cadastro` | [CadastroFacial.jsx](../FrontEnd/src/pages/cadastro/CadastroFacial.jsx) | Formulário completo + `CameraCaptura.jsx` + checkbox obrigatório do Termo LGPD ao enviar biometria + proteção `savedPersonId`. |
| `#/pessoa/<tipo>/<id>` | [PerfilPessoa.jsx](../FrontEnd/src/pages/perfil/PerfilPessoa.jsx) | Edição cadastral, ativação/inativação, captura/atualização ou **revogação LGPD** da biometria, alertas relacionados e histórico paginado de passagens. |
| `#/monitoramento` | [Monitoramento.jsx](../FrontEnd/src/pages/monitoramento/Monitoramento.jsx) | Tabela paginada (`25/pág` padrão) com filtros por nome/portal, tipo de pessoa, movimento, status e intervalo de datas (`de`/`ate`), além de telemetria FPS das câmeras. |
| `#/alertas` | [Alertas.jsx](../FrontEnd/src/pages/alertas/Alertas.jsx) | Fila paginada de incidentes com filtros de severidade/status e ações (`Em análise` / `Resolver`) atualizando o contador global. |
| `#/relatorios` | [Relatorios.jsx](../FrontEnd/src/pages/relatorios/Relatorios.jsx) | Gráfico de frequência dos últimos 5 dias úteis, anel de taxa de reconhecimento hoje e exportação de planilha CSV (`downloadReportCsv`). |
| `#/configuracoes` | [Configuracoes.jsx](../FrontEnd/src/pages/configuracoes/Configuracoes.jsx) | Regras de horário/cooldown/limiar SFace, gestão de terminais e chaves `X-Portaria-Key`, cadastro de turmas/turnos e trilha de auditoria LGPD paginada. |

---

## Camada HTTP e Segurança (`src/lib/api.js`)

- **Base URL**: configurada via `VITE_API_URL` (padrão `http://localhost:8000/api`).
- **Armazenamento de Token**: utiliza `sessionStorage` (`reconhece_auth_token`) para isolar o token à aba/sessão do navegador.
- **Handler Global de 401**: qualquer resposta `401` fora de `/login/` limpa imediatamente `sessionStorage` e dispara `unauthorizedHandler()`, redirecionando o usuário de volta ao `Login`.
- **Upload Biométrico (`enrollBiometrics`)**: monta `FormData` com múltiplos quadros (`imagens`) sem definir `Content-Type` manualmente, permitindo ao navegador incluir o `boundary` correto.
- **Exportação CSV (`downloadReportCsv`)**: realiza `fetch` autenticado com Bearer Token, cria Blob temporário e dispara download de `frequencia-escolar.csv` revogando o `ObjectURL` em seguida.

---

## Sincronização Incremental em Tempo Real (`/api/live/`)

Implementado em [App.jsx](../FrontEnd/src/App.jsx):
1. Após autenticação e carregamento inicial (`/api/bootstrap/`), `cursorRef` guarda `lastLogId` e `lastAlertId`.
2. Um intervalo de **3 segundos** executa `api.live(lastLogId, lastAlertId)` **apenas se `document.visibilityState === 'visible'`**.
3. Quando a aba retorna ao foco (`visibilitychange`), uma sincronização imediata é disparada.
4. Se `data.changed === true`, `App.jsx` atualiza os cursores, incrementa `liveTick` (recarregando a tela ativa, por exemplo `Dashboard`, `Monitoramento` página 1, `Alertas` página 1, `PerfilPessoa` ou `Relatorios`) e exibe toast automático se houver alerta de severidade **`alta`** em aberto.

---

## Resiliência, Webcam WebRTC e UX

- **`ErrorBoundary`** ([ErrorBoundary.jsx](../FrontEnd/src/components/ErrorBoundary.jsx)): envolve toda a aplicação no [main.jsx](../FrontEnd/src/main.jsx), evitando "tela branca" caso ocorra erro inesperado de renderização e oferecendo botão **Recarregar painel**.
- **Tratamento explícito de erros de rede nas páginas**: `Dashboard`, `PeopleList`, `Monitoramento`, `Alertas` e `Relatorios` capturam falhas nas chamadas `api.*`, exibem banner `role="alert"` com a mensagem da API e botão **Tentar novamente** sem gerar *unhandled promise rejections*.
- **`CameraCaptura.jsx`** ([CameraCaptura.jsx](../FrontEnd/src/components/CameraCaptura.jsx)):
  - Vincula `videoRef.current.srcObject` reativamente via `useEffect([cameraOn])` + `.play().catch(() => {})`, evitando tela preta em StrictMode ou câmeras lentas.
  - Captura 3 quadros JPEG (`640x480` ideal, qualidade `0.92`, intervalo `180ms`) com guia oval centralizado e para automaticamente os tracks de mídia após capturar ou desmontar o componente.
  - Revoga URLs temporárias anteriores (`URL.revokeObjectURL`) a cada nova captura/upload.
  - Exibe aviso claro se `navigator.mediaDevices.getUserMedia` não estiver disponível (contexto HTTP não seguro fora de `localhost`) e mantém fallback para upload de arquivo de imagem.
- **Retentativa sem duplicidade (`savedPersonId`) em `CadastroFacial.jsx`**:
  - Se a criação cadastral (`POST /api/people/`) tiver sucesso mas a validação biométrica (`POST /api/people/<id>/biometrics/`) falhar (ex.: HTTP `422` por foto desfocada ou mais de um rosto), `App.jsx` anexa `err.savedPersonId = targetId`.
  - A tela bloqueia os campos já salvos no PostgreSQL e permite reenviar apenas a nova captura facial para o mesmo registro sem duplicar matrícula.
- **Consistência RBAC na UI**: em `Configuracoes.jsx`, perfis sem permissão de escrita (`secretaria`, `visualizador`) visualizam aviso de **Modo somente leitura** com botões e switches (`ToggleRow`) desabilitados/ocultos, evitando erros `403` desnecessários.
