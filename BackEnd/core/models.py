from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone


class Aluno(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        INATIVO = "inativo", "Inativo"

    nome = models.TextField()
    documento = models.CharField(max_length=32, unique=True, validators=[MinLengthValidator(3)])
    turma = models.CharField(max_length=80, validators=[MinLengthValidator(2)])
    turno = models.CharField(max_length=20)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATIVO)
    contato_nome = models.TextField()
    contato_telefone = models.CharField(max_length=32)
    data_nascimento = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "aluno"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["ativo", "inativo"]),
                name="aluno_status_valido",
            ),
        ]


class Funcionario(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        INATIVO = "inativo", "Inativo"

    nome = models.TextField()
    documento = models.CharField(max_length=32, unique=True, validators=[MinLengthValidator(3)])
    cargo = models.CharField(max_length=100, validators=[MinLengthValidator(2)])
    turno = models.CharField(max_length=20)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATIVO)
    contato_nome = models.TextField()
    contato_telefone = models.CharField(max_length=32)
    data_admissao = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "funcionario"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["ativo", "inativo"]),
                name="funcionario_status_valido",
            ),
        ]


class RegistroAcesso(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"

    class Status(models.TextChoices):
        RECONHECIDO = "reconhecido", "Reconhecido"
        ATRASO = "atraso", "Atraso"
        NAO_RECONHECIDO = "nao-reconhecido", "Não reconhecido"

    aluno = models.ForeignKey(Aluno, null=True, blank=True, db_column="id_aluno", on_delete=models.SET_NULL)
    funcionario = models.ForeignKey(Funcionario, null=True, blank=True, db_column="id_funcionario", on_delete=models.SET_NULL)
    data_hora = models.DateTimeField(default=timezone.now)
    portal = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.ENTRADA)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECONHECIDO)

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
                condition=models.Q(status__in=["reconhecido", "atraso", "nao-reconhecido"]),
                name="registro_acesso_status_valido",
            ),
        ]
        indexes = [
            models.Index(fields=["-data_hora"], name="acesso_data_idx"),
            models.Index(fields=["status", "-data_hora"], name="acesso_status_data_idx"),
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
    tipo = models.CharField(max_length=100)
    descricao = models.TextField()
    severidade = models.CharField(max_length=20, choices=Severidade.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOVO)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alerta"
        ordering = ["status", "-criado_em"]
        indexes = [
            models.Index(fields=["status", "-criado_em"], name="alerta_status_data_idx"),
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
