# Sistema de Monitoramento de Entrada e Saída por Reconhecimento Facial

Projeto Integrador do curso de Engenharia de Software do Centro Universitário UNISATC, desenvolvido para a **Escola Natálio Vassoler**.

---

## Sobre o projeto

A Escola Natálio Vassoler controla a entrada e a saída dos alunos de forma manual, com anotações em cadernos e listas de papel. A identificação depende do reconhecimento visual do funcionário da portaria, o que se torna inviável nos horários de pico. Como consequência, a escola não consegue saber em tempo real quais alunos estão dentro do prédio, o registro é lento e não existe histórico organizado de frequência.

Este sistema informatiza esse processo por meio de reconhecimento facial, e é composto por dois módulos integrados:

**Módulo de portaria** — captura a imagem no ponto de acesso, identifica o aluno pela comparação com a base cadastrada e registra automaticamente a passagem, com data, hora, sentido do movimento e grau de confiança da identificação.

**Painel web** — permite à direção e à secretaria consultar quem está na escola no momento, pesquisar o histórico de movimentações por aluno ou por período e gerar relatórios de frequência, atrasos e saídas antecipadas.

---

## Equipe

| Integrante | Função | Responsabilidades |
|---|---|---|
| Bruno Vieira Correa | Back-end e Banco de Dados | API, modelagem do banco, integração com o módulo de reconhecimento facial e segurança da aplicação |
| Ruan Fiori Marcelino | Gestão do Kanban e Cliente | Organização do quadro Kanban, acompanhamento das entregas e comunicação com a instituição |
| Guilherme Rodrigues | Front-end | Telas do painel web, experiência do usuário e integração com a API |

---

## Tecnologias

| Camada | Tecnologia | Motivo da escolha |
|---|---|---|
| Front-end | React, HTML5, CSS3, JavaScript | Atualização da interface sem recarregar a página, necessária no painel em tempo real |
| Back-end | Python, Django, Django REST Framework | Mesma linguagem do módulo de reconhecimento; autenticação, ORM e proteções de segurança nativas |
| Banco de dados | PostgreSQL | Modelo relacional, suporte a transações e sem custo de licenciamento para a escola |
| Reconhecimento facial | OpenCV com YuNet e SFace (ONNX) | Executa em processador comum, sem exigir placa de vídeo dedicada |

A justificativa completa de cada escolha está no documento de infraestrutura, em `docs/`.

---

## Estrutura do repositório

```
.
├── backend/       API em Django e regras de negócio
├── frontend/      Painel web em React
├── portaria/      Módulo de captura e reconhecimento facial
├── docs/          Diagramas, documentação e relatórios
└── README.md
```

---

## Como executar

> Instruções preliminares. Serão detalhadas conforme os módulos forem implementados.

### Pré-requisitos

- Python 3.11 ou 3.12
- Node.js 18 ou superior
- PostgreSQL 14 ou superior
- Webcam (para o módulo de portaria)

### Back-end

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # preencher as credenciais do banco
python manage.py migrate
python manage.py runserver
```

### Front-end

```bash
cd frontend
npm install
npm run dev
```

### Módulo de portaria

```bash
cd portaria
pip install -r requirements.txt
python reconhecimento.py
```

Os modelos de reconhecimento (YuNet e SFace) são baixados automaticamente na primeira execução.

---

## Proteção de dados

O sistema trata dados biométricos de estudantes menores de idade, classificados como dados pessoais sensíveis pela Lei nº 13.709/2018 (LGPD). As seguintes medidas fazem parte do projeto:

- Coleta de consentimento expresso dos responsáveis legais antes de qualquer cadastro biométrico
- Armazenamento do vetor matemático extraído do rosto, e não da fotografia
- Controle de acesso por perfil de usuário e registro de auditoria das consultas
- Meio alternativo de identificação para quem não autorizar o uso da biometria
- Prazo definido de retenção, com exclusão dos dados ao término do vínculo do aluno com a escola

---

## Gestão do projeto

A equipe utiliza a metodologia **Kanban**, com quadro hospedado no Trello.

Quadro do projeto: (https://trello.com/invite/b/6a7e46629e590c7bd6e3d664/ATTIc849a1a5f93ceacc0b951cad6656a649C132C1ED/sistema-de-monitoramento-de-acesso-escolar)

O quadro está organizado em seis colunas — Backlog, A fazer, Em desenvolvimento, Em revisão, Validação e Concluído — com limites de trabalho em progresso definidos por coluna.

---

## Situação atual

Fase de levantamento de requisitos e definição da infraestrutura de trabalho. Os módulos ainda não foram implementados.

---

## Licença

Projeto acadêmico desenvolvido sem fins comerciais para o Projeto Integrador do curso de Engenharia de Software da UNISATC.
