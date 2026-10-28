from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Alerta, Aluno, Funcionario, RegistroAcesso


ALUNOS = ["Ana Beatriz Silva", "Bruno Costa Lima", "Carla Eduarda Santos", "Davi Henrique Oliveira",
          "Elisa Fernandes Rocha", "Felipe Augusto Souza", "Gabriela Martins Alves", "Heitor Ribeiro Dias",
          "Isabela Cristina Pereira", "João Pedro Nascimento", "Larissa Gomes Teixeira", "Matheus Vinícius Barbosa"]
FUNCIONARIOS = ["Camila Ferreira Rocha", "Eduardo Santos Lima", "Beatriz Nogueira Alves",
                "Marcelo Andrade Souza", "Renata Vieira Costa", "Fábio Henrique Moreira"]
TURMAS = ["6º A", "6º B", "7º A", "7º B", "9º A"]
CARGOS = ["Professor(a) — Matemática", "Professor(a) — Português", "Professor(a) — Ciências",
          "Coordenador(a) Pedagógico(a)", "Secretário(a) Escolar", "Porteiro(a)"]


class Command(BaseCommand):
    help = "Cria dados demonstrativos para validar o painel."

    def handle(self, *args, **options):
        RegistroAcesso.objects.all().delete()
        Alerta.objects.all().delete()
        Aluno.objects.all().delete()
        Funcionario.objects.all().delete()
        alunos = []
        funcionarios = []
        for i, nome in enumerate(ALUNOS):
            turma = TURMAS[i % len(TURMAS)]
            alunos.append(Aluno.objects.create(
                nome=nome, documento=f"2026{1000 + i}", turma=turma,
                turno="Tarde" if turma.startswith("9") else "Manhã",
                status="inativo" if i == 8 else "ativo",
                contato_nome=f"Responsável de {nome.split()[0]}",
                contato_telefone=f"(48) 9{8000 + i:04d}-{1000 + i:04d}",
                data_nascimento=date(2012 + i % 4, 3 + i % 8, 3 + i % 20),
            ))
        for i, nome in enumerate(FUNCIONARIOS):
            funcionarios.append(Funcionario.objects.create(
                nome=nome, documento=f"FUNC-{300 + i}", cargo=CARGOS[i],
                turno="Integral" if i % 3 == 0 else ("Tarde" if i % 2 else "Manhã"),
                contato_nome=f"Contato de emergência de {nome.split()[0]}",
                contato_telefone=f"(48) 9{7000 + i:04d}-{2000 + i:04d}",
                data_admissao=date(2018 + i % 6, 1 + i % 9, 1 + i % 20),
            ))
        now = timezone.now().replace(hour=7, minute=0, second=0, microsecond=0)
        for i, person in enumerate(alunos + funcionarios):
            if person.status == "inativo" or i % 7 == 4:
                continue
            at = now + timedelta(minutes=(i * 3) % 28)
            kwargs = {"aluno": person} if isinstance(person, Aluno) else {"funcionario": person}
            RegistroAcesso.objects.create(data_hora=at, portal="Portaria principal",
                                          tipo="entrada", status="atraso" if at.minute > 20 else "reconhecido", **kwargs)
            if i % 9 == 0:
                RegistroAcesso.objects.create(data_hora=at + timedelta(hours=3), portal="Portaria principal",
                                              tipo="saida", status="reconhecido", **kwargs)
        RegistroAcesso.objects.create(data_hora=now + timedelta(minutes=12), portal="Catraca lateral",
                                      tipo="entrada", status="nao-reconhecido")
        for log in RegistroAcesso.objects.filter(status__in=["atraso", "nao-reconhecido"]):
            pessoa = log.aluno or log.funcionario
            tipo = "aluno" if log.aluno_id else "funcionario"
            Alerta.objects.create(
                pessoa_tipo=tipo if pessoa else "", pessoa_id=pessoa.pk if pessoa else None,
                tipo="Atraso na entrada" if log.status == "atraso" else "Tentativa não reconhecida",
                descricao="Entrada após o horário limite." if log.status == "atraso"
                else "Reconhecimento facial não identificou nenhum cadastro.",
                severidade="media" if log.status == "atraso" else "alta", status="novo",
            )
        self.stdout.write(self.style.SUCCESS(
            f"Mock criado: {len(alunos)} alunos, {len(funcionarios)} funcionários, "
            f"{RegistroAcesso.objects.count()} acessos e {Alerta.objects.count()} alertas."
        ))
