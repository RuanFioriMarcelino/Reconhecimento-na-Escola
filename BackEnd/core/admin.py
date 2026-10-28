from django.contrib import admin
from .models import Alerta, Aluno, Funcionario, RegistroAcesso

admin.site.register([Aluno, Funcionario, RegistroAcesso, Alerta])
