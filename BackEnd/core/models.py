from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class PerfilUsuario(models.Model):
    class Papel(models.TextChoices):
        ADMIN = "admin", "Administrador"
        COORDENACAO = "coordenacao", "Coordenação"
        SECRETARIA = "secretaria", "Secretaria"
        VISUALIZADOR = "visualizador", "Visualizador"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    nome_exibicao = models.CharField(max_length=120)
    papel = models.CharField(max_length=20, choices=Papel.choices, default=Papel.COORDENACAO)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "perfil_usuario"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(papel__in=["admin", "coordenacao", "secretaria", "visualizador"]),
                name="perfil_usuario_papel_valido",
            ),
        ]

    def __str__(self):
        return f"{self.nome_exibicao} ({self.papel})"


class AuthToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    prefixo = models.CharField(max_length=12)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    ultimo_uso_em = models.DateTimeField(null=True, blank=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    revogado = models.BooleanField(default=False)

    class Meta:
        db_table = "auth_token"
        indexes = [
            models.Index(fields=["user", "revogado", "-expira_em"], name="auth_token_user_idx"),
            models.Index(
                fields=["token_hash"],
                condition=models.Q(revogado=False),
                name="auth_token_ativo_hash_idx",
            ),
        ]


class ConfiguracaoEscola(models.Model):
    nome_escola = models.CharField(max_length=150, default="Escola Natálio Vassoler")
    notif_atraso = models.BooleanField(default=True)
    notif_ausencia = models.BooleanField(default=True)
    notif_nao_reconhecido = models.BooleanField(default=True)
    notif_saida_antecipada = models.BooleanField(default=True)
    limite_manha = models.CharField(max_length=5, default="07:20")
    limite_tarde = models.CharField(max_length=5, default="13:20")
    saida_manha = models.CharField(max_length=5, default="11:30")
    saida_tarde = models.CharField(max_length=5, default="17:30")
    cooldown_segundos = models.PositiveIntegerField(default=45, validators=[MinValueValidator(5), MaxValueValidator(600)])
    tempo_minimo_permanencia_min = models.PositiveIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(120)])
    limiar_confianca = models.DecimalField(
        max_digits=4, decimal_places=3, default=0.380, validators=[MinValueValidator(0.25), MaxValueValidator(0.85)]
    )
    retencao_logs_dias = models.PositiveIntegerField(default=365, validators=[MinValueValidator(30), MaxValueValidator(3650)])
    modo_passivo = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "configuracao_escola"


class DispositivoPortaria(models.Model):
    class Sentido(models.TextChoices):
        AUTO = "auto", "Automático (Entrada/Saída)"
        ENTRADA = "entrada", "Somente Entrada"
        SAIDA = "saida", "Somente Saída"

    nome = models.CharField(max_length=100, unique=True)
    portal = models.CharField(max_length=100)
    sentido_padrao = models.CharField(max_length=12, choices=Sentido.choices, default=Sentido.AUTO)
    api_key_hash = models.CharField(max_length=64, unique=True)
    api_key_prefixo = models.CharField(max_length=16)
    ativo = models.BooleanField(default=True)
    ultimo_heartbeat = models.DateTimeField(null=True, blank=True)
    ip_ultimo_acesso = models.GenericIPAddressField(null=True, blank=True)
    telemetria = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dispositivo_portaria"
        ordering = ["nome"]
        indexes = [
            models.Index(
                fields=["api_key_hash"],
                condition=models.Q(ativo=True),
                name="disp_ativo_key_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(sentido_padrao__in=["auto", "entrada", "saida"]),
                name="dispositivo_sentido_valido",
            ),
        ]

    def __str__(self):
        return f"{self.nome} ({self.portal})"


class Turno(models.Model):
    nome = models.CharField(max_length=20, unique=True)
    inicio = models.TimeField()
    limite_entrada = models.TimeField()
    termino = models.TimeField(null=True, blank=True)
    limite_saida_antecipada = models.TimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "turno"
        ordering = ["inicio", "nome"]

    def __str__(self):
        return self.nome


class Turma(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="turmas")
    ano_letivo = models.PositiveIntegerField()
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "turma"
        ordering = ["ano_letivo", "nome"]

    def __str__(self):
        return f"{self.nome} ({self.ano_letivo})"


class Responsavel(models.Model):
    nome = models.TextField()
    cpf_enc = models.BinaryField()
    email_enc = models.BinaryField(null=True, blank=True)
    phone_enc = models.BinaryField(null=True, blank=True)
    cpf_hash = models.BinaryField(unique=True)
    key_id = models.CharField(max_length=16, default="k1")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "responsavel"

    def __str__(self):
        return self.nome


class Aluno(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        INATIVO = "inativo", "Inativo"

    nome = models.TextField()
    documento = models.CharField(max_length=32, unique=True, validators=[MinLengthValidator(3)])
    turma = models.CharField(max_length=80, validators=[MinLengthValidator(2)])
    turno = models.CharField(max_length=20)
    turma_ref = models.ForeignKey(
        Turma, null=True, blank=True, on_delete=models.PROTECT, related_name="alunos"
    )
    turno_ref = models.ForeignKey(
        Turno, null=True, blank=True, on_delete=models.PROTECT, related_name="alunos"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATIVO)
    contato_nome = models.TextField()
    contato_telefone = models.CharField(max_length=32)
    data_nascimento = models.DateField(null=True, blank=True)
    consentimento_biometrico = models.BooleanField(default=False)
    consentimento_em = models.DateTimeField(null=True, blank=True)
    consentimento_responsavel = models.CharField(max_length=150, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "aluno"
        indexes = [
            GinIndex(fields=["nome"], name="aluno_nome_trgm_idx", opclasses=["gin_trgm_ops"]),
            GinIndex(fields=["documento"], name="aluno_doc_trgm_idx", opclasses=["gin_trgm_ops"]),
            models.Index(fields=["status", "turma", "nome"], name="aluno_status_turma_nome_idx"),
            models.Index(fields=["status", "turno"], name="aluno_status_turno_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["ativo", "inativo"]),
                name="aluno_status_valido",
            ),
        ]

    def __str__(self):
        return f"{self.nome} ({self.documento})"


class RelAlunoResponsavel(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="responsaveis_rel")
    responsavel = models.ForeignKey(Responsavel, on_delete=models.CASCADE, related_name="alunos_rel")

    class Meta:
        db_table = "rel_aluno_responsavel"
        constraints = [
            models.UniqueConstraint(fields=["aluno", "responsavel"], name="uq_rel_aluno_responsavel"),
        ]


class Funcionario(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        INATIVO = "inativo", "Inativo"

    nome = models.TextField()
    documento = models.CharField(max_length=32, unique=True, validators=[MinLengthValidator(3)])
    cargo = models.CharField(max_length=100, validators=[MinLengthValidator(2)])
    turno = models.CharField(max_length=20)
    turno_ref = models.ForeignKey(
        Turno, null=True, blank=True, on_delete=models.PROTECT, related_name="funcionarios"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATIVO)
    contato_nome = models.TextField()
    contato_telefone = models.CharField(max_length=32)
    data_admissao = models.DateField(null=True, blank=True)
    consentimento_biometrico = models.BooleanField(default=False)
    consentimento_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "funcionario"
        indexes = [
            GinIndex(fields=["nome"], name="func_nome_trgm_idx", opclasses=["gin_trgm_ops"]),
            GinIndex(fields=["documento"], name="func_doc_trgm_idx", opclasses=["gin_trgm_ops"]),
            models.Index(fields=["status", "cargo", "nome"], name="func_status_cargo_nome_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["ativo", "inativo"]),
                name="funcionario_status_valido",
            ),
        ]

    def __str__(self):
        return f"{self.nome} ({self.documento})"


class DadoBiometrico(models.Model):
    class Algoritmo(models.TextChoices):
        SFACE = "SFace", "SFace"
        FACENET = "FaceNet", "FaceNet"
        ARCFACE = "ArcFace", "ArcFace"
        OUTRO = "Outro", "Outro"

    aluno = models.ForeignKey(
        Aluno, null=True, blank=True, db_column="id_aluno", on_delete=models.CASCADE, related_name="biometrias"
    )
    funcionario = models.ForeignKey(
        Funcionario, null=True, blank=True, db_column="id_funcionario", on_delete=models.CASCADE, related_name="biometrias"
    )
    algoritmo = models.CharField(max_length=20, choices=Algoritmo.choices, default=Algoritmo.SFACE)
    versao = models.CharField(max_length=32, default="2021dec")
    dimensao = models.PositiveIntegerField(default=128)
    qualidade = models.DecimalField(max_digits=3, decimal_places=2)
    vetor_enc = models.BinaryField()
    key_id = models.CharField(max_length=16, default="k1")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dados_biometricos"
        indexes = [
            models.Index(fields=["aluno", "ativo"], name="bio_aluno_ativo_idx"),
            models.Index(fields=["funcionario", "ativo"], name="bio_func_ativo_idx"),
            models.Index(
                fields=["aluno"],
                condition=models.Q(ativo=True, aluno__isnull=False),
                name="bio_aluno_only_ativo_idx",
            ),
            models.Index(
                fields=["funcionario"],
                condition=models.Q(ativo=True, funcionario__isnull=False),
                name="bio_func_only_ativo_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(aluno__isnull=False, funcionario__isnull=True)
                    | models.Q(aluno__isnull=True, funcionario__isnull=False)
                ),
                name="biometria_um_dono",
            ),
            models.CheckConstraint(
                condition=models.Q(algoritmo__in=["SFace", "FaceNet", "ArcFace", "Outro"]),
                name="biometria_algoritmo_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(dimensao__in=[128, 512]),
                name="biometria_dimensao_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(qualidade__gte=0, qualidade__lte=1),
                name="biometria_qualidade_valida",
            ),
        ]


class RegistroAcesso(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"

    class Status(models.TextChoices):
        RECONHECIDO = "reconhecido", "Reconhecido"
        ATRASO = "atraso", "Atraso"
        SAIDA_ANTECIPADA = "saida-antecipada", "Saída antecipada"
        NAO_RECONHECIDO = "nao-reconhecido", "Não reconhecido"

    aluno = models.ForeignKey(Aluno, null=True, blank=True, db_column="id_aluno", on_delete=models.SET_NULL)
    funcionario = models.ForeignKey(Funcionario, null=True, blank=True, db_column="id_funcionario", on_delete=models.SET_NULL)
    dispositivo = models.ForeignKey(
        DispositivoPortaria, null=True, blank=True, on_delete=models.SET_NULL, related_name="registros"
    )
    data_hora = models.DateTimeField(default=timezone.now)
    portal = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.ENTRADA)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECONHECIDO)
    confianca = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    incidente = models.BooleanField(default=False)
    client_event_id = models.CharField(max_length=64, null=True, blank=True, unique=True)

    class Meta:
        db_table = "registro_acesso"
        ordering = ["data_hora"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(aluno__isnull=False, funcionario__isnull=True)
                    | models.Q(aluno__isnull=True, funcionario__isnull=False)
                    | models.Q(aluno__isnull=True, funcionario__isnull=True, status="nao-reconhecido")
                ),
                name="registro_acesso_uma_pessoa_ou_nao_reconhecido",
            ),
            models.CheckConstraint(
                condition=models.Q(tipo__in=["entrada", "saida"]),
                name="registro_acesso_tipo_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["reconhecido", "atraso", "saida-antecipada", "nao-reconhecido"]),
                name="registro_acesso_status_valido",
            ),
        ]
        indexes = [
            models.Index(fields=["-data_hora"], name="acesso_data_idx"),
            models.Index(fields=["-data_hora", "-id"], name="acesso_data_id_idx"),
            models.Index(fields=["status", "-data_hora"], name="acesso_status_data_idx"),
            models.Index(fields=["tipo", "-data_hora"], name="acesso_tipo_data_idx"),
            models.Index(fields=["portal", "-data_hora"], name="acesso_portal_data_idx"),
            models.Index(fields=["aluno", "-data_hora"], name="acesso_aluno_data_idx"),
            models.Index(fields=["funcionario", "-data_hora"], name="acesso_func_data_idx"),
            models.Index(
                fields=["portal", "-data_hora"],
                condition=models.Q(aluno__isnull=True, funcionario__isnull=True),
                name="acesso_desconhecido_portal_idx",
            ),
            models.Index(
                fields=["-data_hora"],
                condition=models.Q(incidente=True),
                name="acesso_incidente_data_idx",
            ),
        ]


class Alerta(models.Model):
    class Status(models.TextChoices):
        NOVO = "novo", "Novo"
        EM_ANALISE = "em-analise", "Em análise"
        RESOLVIDO = "resolvido", "Resolvido"

    class Severidade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        MEDIA = "media", "Média"
        ALTA = "alta", "Alta"

    pessoa_tipo = models.CharField(max_length=20, blank=True)
    pessoa_id = models.PositiveBigIntegerField(null=True, blank=True)
    registro_acesso = models.ForeignKey(
        RegistroAcesso, null=True, blank=True, on_delete=models.SET_NULL, related_name="alertas"
    )
    tipo = models.CharField(max_length=100)
    descricao = models.TextField()
    severidade = models.CharField(max_length=20, choices=Severidade.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOVO)
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="alertas_resolvidos"
    )
    resolvido_em = models.DateTimeField(null=True, blank=True)
    observacao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alerta"
        ordering = ["status", "-criado_em"]
        indexes = [
            models.Index(fields=["status", "-criado_em"], name="alerta_status_data_idx"),
            models.Index(
                fields=["-criado_em"],
                condition=~models.Q(status="resolvido"),
                name="alerta_aberto_data_idx",
            ),
            models.Index(fields=["pessoa_tipo", "pessoa_id", "-criado_em"], name="alerta_pessoa_data_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["novo", "em-analise", "resolvido"]),
                name="alerta_status_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(severidade__in=["baixa", "media", "alta"]),
                name="alerta_severidade_valida",
            ),
        ]


class LogAuditoria(models.Model):
    class Operacao(models.TextChoices):
        INSERT = "INSERT", "INSERT"
        UPDATE = "UPDATE", "UPDATE"
        DELETE = "DELETE", "DELETE"
        SELECT = "SELECT", "SELECT"
        AUTH = "AUTH", "AUTH"
        SYNC = "SYNC", "SYNC"

    tabela = models.CharField(max_length=80)
    operacao = models.CharField(max_length=16, choices=Operacao.choices)
    chave = models.CharField(max_length=100, blank=True, default="")
    usuario = models.CharField(max_length=150, blank=True, default="")
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    detalhes = models.JSONField(default=dict, blank=True)
    sensivel = models.BooleanField(default=False)
    ocorrido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "log_auditoria"
        ordering = ["-ocorrido_em"]
        indexes = [
            models.Index(fields=["-ocorrido_em"], name="auditoria_data_idx"),
            models.Index(fields=["tabela", "operacao", "-ocorrido_em"], name="auditoria_tabela_op_idx"),
            models.Index(
                fields=["-ocorrido_em"],
                condition=models.Q(sensivel=True),
                name="auditoria_sensivel_idx",
            ),
            models.Index(fields=["usuario", "-ocorrido_em"], name="auditoria_usuario_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(operacao__in=["INSERT", "UPDATE", "DELETE", "SELECT", "AUTH", "SYNC"]),
                name="auditoria_operacao_valida",
            ),
        ]
