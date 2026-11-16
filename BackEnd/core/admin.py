from django.contrib import admin
from .models import Alerta, Aluno, Funcionario, RegistroAcesso, Turma, Turno

admin.site.register([Aluno, Funcionario, RegistroAcesso, Alerta, Turma, Turno])
