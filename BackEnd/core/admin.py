from django.contrib import admin

from .models import (
    Alerta,
    Aluno,
    AuthToken,
    ConfiguracaoEscola,
    DadoBiometrico,
    DispositivoPortaria,
    Funcionario,
    LogAuditoria,
    PerfilUsuario,
    RegistroAcesso,
    RelAlunoResponsavel,
    Responsavel,
    Turma,
    Turno,
)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("nome_exibicao", "papel", "user", "criado_em")
    list_filter = ("papel",)


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "prefixo", "criado_em", "expira_em", "revogado")
    list_filter = ("revogado",)
    readonly_fields = ("token_hash",)


@admin.register(DispositivoPortaria)
class DispositivoPortariaAdmin(admin.ModelAdmin):
    list_display = ("nome", "portal", "sentido_padrao", "api_key_prefixo", "ativo", "ultimo_heartbeat")
    list_filter = ("ativo", "sentido_padrao")
    readonly_fields = ("api_key_hash",)


@admin.register(DadoBiometrico)
class DadoBiometricoAdmin(admin.ModelAdmin):
    list_display = ("id", "aluno", "funcionario", "algoritmo", "dimensao", "qualidade", "key_id", "ativo", "criado_em")
    list_filter = ("algoritmo", "ativo", "key_id")
    readonly_fields = ("vetor_enc",)


@admin.register(Responsavel)
class ResponsavelAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "key_id", "criado_em")
    readonly_fields = ("cpf_enc", "email_enc", "phone_enc", "cpf_hash")


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("ocorrido_em", "tabela", "operacao", "chave", "usuario", "sensivel")
    list_filter = ("tabela", "operacao", "sensivel")


admin.site.register([ConfiguracaoEscola, Turno, Turma, Aluno, RelAlunoResponsavel, Funcionario, RegistroAcesso, Alerta])
