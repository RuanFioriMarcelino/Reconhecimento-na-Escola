-- =====================================================================
-- Reconhece+ v2.0 — Esquema Relacional PostgreSQL (Referência DDL)
-- O gerenciamento oficial de migrações é feito via Django ORM (BackEnd/core/models.py)
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE perfil_usuario (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,
    nome_exibicao VARCHAR(120) NOT NULL,
    papel VARCHAR(20) NOT NULL DEFAULT 'coordenacao'
        CHECK (papel IN ('admin', 'coordenacao', 'secretaria', 'visualizador')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth_token (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    prefixo VARCHAR(12) NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    expira_em TIMESTAMPTZ NOT NULL,
    ultimo_uso_em TIMESTAMPTZ,
    ip_origem INET,
    revogado BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE configuracao_escola (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_escola VARCHAR(150) NOT NULL DEFAULT 'Escola Natálio Vassoler',
    notif_atraso BOOLEAN NOT NULL DEFAULT TRUE,
    notif_ausencia BOOLEAN NOT NULL DEFAULT TRUE,
    notif_nao_reconhecido BOOLEAN NOT NULL DEFAULT TRUE,
    notif_saida_antecipada BOOLEAN NOT NULL DEFAULT TRUE,
    limite_manha VARCHAR(5) NOT NULL DEFAULT '07:20',
    limite_tarde VARCHAR(5) NOT NULL DEFAULT '13:20',
    saida_manha VARCHAR(5) NOT NULL DEFAULT '11:30',
    saida_tarde VARCHAR(5) NOT NULL DEFAULT '17:30',
    cooldown_segundos INT NOT NULL DEFAULT 45 CHECK (cooldown_segundos BETWEEN 5 AND 600),
    tempo_minimo_permanencia_min INT NOT NULL DEFAULT 2 CHECK (tempo_minimo_permanencia_min BETWEEN 1 AND 120),
    limiar_confianca NUMERIC(4,3) NOT NULL DEFAULT 0.380 CHECK (limiar_confianca BETWEEN 0.250 AND 0.850),
    retencao_logs_dias INT NOT NULL DEFAULT 365 CHECK (retencao_logs_dias BETWEEN 30 AND 3650),
    modo_passivo BOOLEAN NOT NULL DEFAULT TRUE,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dispositivo_portaria (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    portal VARCHAR(100) NOT NULL,
    sentido_padrao VARCHAR(12) NOT NULL DEFAULT 'auto'
        CHECK (sentido_padrao IN ('auto', 'entrada', 'saida')),
    api_key_hash VARCHAR(64) NOT NULL UNIQUE,
    api_key_prefixo VARCHAR(16) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_heartbeat TIMESTAMPTZ,
    ip_ultimo_acesso INET,
    telemetria JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE turno (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(20) NOT NULL UNIQUE,
    inicio TIME NOT NULL,
    limite_entrada TIME NOT NULL,
    termino TIME,
    limite_saida_antecipada TIME,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE turma (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(80) NOT NULL UNIQUE,
    turno_id BIGINT NOT NULL REFERENCES turno(id) ON DELETE RESTRICT,
    ano_letivo INT NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE responsavel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    cpf_enc BYTEA NOT NULL,
    email_enc BYTEA,
    phone_enc BYTEA,
    cpf_hash BYTEA NOT NULL UNIQUE,
    key_id VARCHAR(16) NOT NULL DEFAULT 'k1',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE aluno (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    documento VARCHAR(32) NOT NULL UNIQUE,
    turma VARCHAR(80) NOT NULL,
    turno VARCHAR(20) NOT NULL,
    turma_ref_id BIGINT REFERENCES turma(id) ON DELETE RESTRICT,
    turno_ref_id BIGINT REFERENCES turno(id) ON DELETE RESTRICT,
    status VARCHAR(12) NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'inativo')),
    contato_nome TEXT NOT NULL,
    contato_telefone VARCHAR(32) NOT NULL,
    data_nascimento DATE,
    consentimento_biometrico BOOLEAN NOT NULL DEFAULT FALSE,
    consentimento_em TIMESTAMPTZ,
    consentimento_responsavel VARCHAR(150) NOT NULL DEFAULT '',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rel_aluno_responsavel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aluno_id BIGINT NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
    responsavel_id BIGINT NOT NULL REFERENCES responsavel(id) ON DELETE CASCADE,
    CONSTRAINT uq_rel_aluno_responsavel UNIQUE (aluno_id, responsavel_id)
);

CREATE TABLE funcionario (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    documento VARCHAR(32) NOT NULL UNIQUE,
    cargo VARCHAR(100) NOT NULL,
    turno VARCHAR(20) NOT NULL,
    turno_ref_id BIGINT REFERENCES turno(id) ON DELETE RESTRICT,
    status VARCHAR(12) NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'inativo')),
    contato_nome TEXT NOT NULL,
    contato_telefone VARCHAR(32) NOT NULL,
    data_admissao DATE,
    consentimento_biometrico BOOLEAN NOT NULL DEFAULT FALSE,
    consentimento_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dados_biometricos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_aluno BIGINT REFERENCES aluno(id) ON DELETE CASCADE,
    id_funcionario BIGINT REFERENCES funcionario(id) ON DELETE CASCADE,
    algoritmo VARCHAR(20) NOT NULL DEFAULT 'SFace'
        CHECK (algoritmo IN ('SFace', 'FaceNet', 'ArcFace', 'Outro')),
    versao VARCHAR(32) NOT NULL DEFAULT '2021dec',
    dimensao INT NOT NULL DEFAULT 128 CHECK (dimensao IN (128, 512)),
    qualidade NUMERIC(3,2) NOT NULL CHECK (qualidade >= 0 AND qualidade <= 1),
    vetor_enc BYTEA NOT NULL,
    key_id VARCHAR(16) NOT NULL DEFAULT 'k1',
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT biometria_um_dono CHECK (
        (id_aluno IS NOT NULL AND id_funcionario IS NULL)
        OR (id_aluno IS NULL AND id_funcionario IS NOT NULL)
    )
);

CREATE TABLE registro_acesso (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_aluno BIGINT REFERENCES aluno(id) ON DELETE SET NULL,
    id_funcionario BIGINT REFERENCES funcionario(id) ON DELETE SET NULL,
    dispositivo_id BIGINT REFERENCES dispositivo_portaria(id) ON DELETE SET NULL,
    data_hora TIMESTAMPTZ NOT NULL DEFAULT now(),
    portal VARCHAR(100) NOT NULL,
    tipo VARCHAR(10) NOT NULL DEFAULT 'entrada' CHECK (tipo IN ('entrada', 'saida')),
    status VARCHAR(20) NOT NULL DEFAULT 'reconhecido'
        CHECK (status IN ('reconhecido', 'atraso', 'saida-antecipada', 'nao-reconhecido')),
    confianca NUMERIC(5,4),
    incidente BOOLEAN NOT NULL DEFAULT FALSE,
    client_event_id VARCHAR(64) UNIQUE,
    CONSTRAINT registro_acesso_uma_pessoa_ou_nao_reconhecido CHECK (
        (id_aluno IS NOT NULL AND id_funcionario IS NULL)
        OR (id_aluno IS NULL AND id_funcionario IS NOT NULL)
        OR (id_aluno IS NULL AND id_funcionario IS NULL AND status = 'nao-reconhecido')
    )
);

CREATE TABLE alerta (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pessoa_tipo VARCHAR(20) NOT NULL DEFAULT '',
    pessoa_id BIGINT,
    registro_acesso_id BIGINT REFERENCES registro_acesso(id) ON DELETE SET NULL,
    tipo VARCHAR(100) NOT NULL,
    descricao TEXT NOT NULL,
    severidade VARCHAR(20) NOT NULL CHECK (severidade IN ('baixa', 'media', 'alta')),
    status VARCHAR(20) NOT NULL DEFAULT 'novo' CHECK (status IN ('novo', 'em-analise', 'resolvido')),
    resolvido_por_id BIGINT REFERENCES auth_user(id) ON DELETE SET NULL,
    resolvido_em TIMESTAMPTZ,
    observacao TEXT NOT NULL DEFAULT '',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE log_auditoria (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tabela VARCHAR(80) NOT NULL,
    operacao VARCHAR(16) NOT NULL
        CHECK (operacao IN ('INSERT', 'UPDATE', 'DELETE', 'SELECT', 'AUTH', 'SYNC')),
    chave VARCHAR(100) NOT NULL DEFAULT '',
    usuario VARCHAR(150) NOT NULL DEFAULT '',
    ip_origem INET,
    detalhes JSONB NOT NULL DEFAULT '{}'::jsonb,
    sensivel BOOLEAN NOT NULL DEFAULT FALSE,
    ocorrido_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX auth_token_user_idx ON auth_token (user_id, revogado, expira_em DESC);
CREATE INDEX auth_token_ativo_hash_idx ON auth_token (token_hash) WHERE revogado = FALSE;
CREATE INDEX disp_ativo_key_idx ON dispositivo_portaria (api_key_hash) WHERE ativo = TRUE;

CREATE INDEX aluno_nome_trgm_idx ON aluno USING gin (nome gin_trgm_ops);
CREATE INDEX aluno_doc_trgm_idx ON aluno USING gin (documento gin_trgm_ops);
CREATE INDEX aluno_status_turma_nome_idx ON aluno (status, turma, nome);
CREATE INDEX aluno_status_turno_idx ON aluno (status, turno);

CREATE INDEX func_nome_trgm_idx ON funcionario USING gin (nome gin_trgm_ops);
CREATE INDEX func_doc_trgm_idx ON funcionario USING gin (documento gin_trgm_ops);
CREATE INDEX func_status_cargo_nome_idx ON funcionario (status, cargo, nome);

CREATE INDEX bio_aluno_ativo_idx ON dados_biometricos (id_aluno, ativo);
CREATE INDEX bio_func_ativo_idx ON dados_biometricos (id_funcionario, ativo);
CREATE INDEX bio_aluno_only_ativo_idx ON dados_biometricos (id_aluno) WHERE ativo = TRUE AND id_aluno IS NOT NULL;
CREATE INDEX bio_func_only_ativo_idx ON dados_biometricos (id_funcionario) WHERE ativo = TRUE AND id_funcionario IS NOT NULL;

CREATE INDEX acesso_data_idx ON registro_acesso (data_hora DESC);
CREATE INDEX acesso_data_id_idx ON registro_acesso (data_hora DESC, id DESC);
CREATE INDEX acesso_status_data_idx ON registro_acesso (status, data_hora DESC);
CREATE INDEX acesso_tipo_data_idx ON registro_acesso (tipo, data_hora DESC);
CREATE INDEX acesso_portal_data_idx ON registro_acesso (portal, data_hora DESC);
CREATE INDEX acesso_aluno_data_idx ON registro_acesso (id_aluno, data_hora DESC);
CREATE INDEX acesso_func_data_idx ON registro_acesso (id_funcionario, data_hora DESC);
CREATE INDEX acesso_desconhecido_portal_idx ON registro_acesso (portal, data_hora DESC)
    WHERE id_aluno IS NULL AND id_funcionario IS NULL;
CREATE INDEX acesso_incidente_data_idx ON registro_acesso (data_hora DESC) WHERE incidente = TRUE;

CREATE INDEX alerta_status_data_idx ON alerta (status, criado_em DESC);
CREATE INDEX alerta_aberto_data_idx ON alerta (criado_em DESC) WHERE status <> 'resolvido';
CREATE INDEX alerta_pessoa_data_idx ON alerta (pessoa_tipo, pessoa_id, criado_em DESC);

CREATE INDEX auditoria_data_idx ON log_auditoria (ocorrido_em DESC);
CREATE INDEX auditoria_tabela_op_idx ON log_auditoria (tabela, operacao, ocorrido_em DESC);
CREATE INDEX auditoria_sensivel_idx ON log_auditoria (ocorrido_em DESC) WHERE sensivel = TRUE;
CREATE INDEX auditoria_usuario_idx ON log_auditoria (usuario, ocorrido_em DESC);
