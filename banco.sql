CREATE TABLE aluno (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE responsavel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    cpf_enc BYTEA NOT NULL,
    email_enc BYTEA,
    phone_enc BYTEA,
    cpf_hash BYTEA NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_responsavel_cpf_hash
        UNIQUE (cpf_hash)
);
CREATE TABLE rel_aluno_responsavel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_aluno BIGINT NOT NULL
        REFERENCES aluno(id)
        ON DELETE CASCADE,
    id_responsavel BIGINT NOT NULL
        REFERENCES responsavel(id)
        ON DELETE CASCADE,
    UNIQUE (id_aluno, id_responsavel)
);
CREATE TABLE dados_biometricos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_aluno BIGINT NOT NULL
        REFERENCES aluno(id)
        ON DELETE CASCADE,
    algoritmo TEXT NOT NULL
        CHECK (algoritmo IN ('FaceNet', 'ArcFace', 'Outro')),
    versao TEXT NOT NULL,
    dimensao INT NOT NULL
        CHECK (dimensao IN (128, 512)),
    qualidade NUMERIC(3,2) NOT NULL
        CHECK (qualidade >= 0.75 AND qualidade <= 1.00),
    vetor_enc BYTEA NOT NULL,
    key_id TEXT NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE registro_acesso (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_aluno BIGINT
        REFERENCES aluno(id)
        ON DELETE SET NULL,
    data_hora TIMESTAMPTZ NOT NULL DEFAULT now(),
    portal TEXT NOT NULL,
    incidente BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE notificacao_responsavel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_responsavel BIGINT NOT NULL
        REFERENCES responsavel(id)
        ON DELETE CASCADE,
    id_aluno BIGINT NOT NULL
        REFERENCES aluno(id)
        ON DELETE CASCADE,
    mensagem TEXT NOT NULL,
    enviado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE log_auditoria (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tabela TEXT NOT NULL,
    operacao TEXT NOT NULL
        CHECK (operacao IN ('INSERT', 'UPDATE', 'DELETE', 'SELECT')),
    chave TEXT,
    usuario TEXT,
    detalhes JSONB,
    sensivel BOOLEAN NOT NULL DEFAULT FALSE,
    ocorrido_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rel_aluno_responsavel_aluno
    ON rel_aluno_responsavel (id_aluno);
CREATE INDEX idx_rel_aluno_responsavel_responsavel
    ON rel_aluno_responsavel (id_responsavel);
CREATE INDEX idx_biometria_aluno
    ON dados_biometricos (id_aluno);
CREATE INDEX idx_biometria_aluno_ativo
    ON dados_biometricos (id_aluno)
    WHERE ativo = TRUE;
CREATE INDEX idx_acesso_aluno_data
    ON registro_acesso (id_aluno, data_hora DESC);
CREATE INDEX idx_acesso_data
    ON registro_acesso (data_hora DESC);
CREATE INDEX idx_acesso_incidente
    ON registro_acesso (incidente, data_hora DESC)
    WHERE incidente = TRUE;
CREATE INDEX idx_notificacao_responsavel
    ON notificacao_responsavel (id_responsavel, enviado_em DESC);
CREATE INDEX idx_notificacao_aluno
    ON notificacao_responsavel (id_aluno, enviado_em DESC);
CREATE INDEX idx_auditoria_data
    ON log_auditoria (ocorrido_em DESC);
CREATE INDEX idx_auditoria_tabela_operacao
    ON log_auditoria (tabela, operacao, ocorrido_em DESC);