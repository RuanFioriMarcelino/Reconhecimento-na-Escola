import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.crypto.cipher import blind_index, encrypt_text
from core.models import (
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
from core.security import generate_secret, hash_secret

ALUNOS = [
    "Ana Beatriz Silva",
    "Bruno Costa Lima",
    "Carla Eduarda Santos",
    "Davi Henrique Oliveira",
    "Elisa Fernandes Rocha",
    "Felipe Augusto Souza",
    "Gabriela Martins Alves",
    "Heitor Ribeiro Dias",
    "Isabela Cristina Pereira",
    "João Pedro Nascimento",
    "Larissa Gomes Teixeira",
    "Matheus Vinícius Barbosa",
]
FUNCIONARIOS = [
    "Camila Ferreira Rocha",
    "Eduardo Santos Lima",
    "Beatriz Nogueira Alves",
    "Marcelo Andrade Souza",
    "Renata Vieira Costa",
    "Fábio Henrique Moreira",
]
TURMAS = ["6º A", "6º B", "7º A", "7º B", "9º A"]
CARGOS = [
    "Professor(a) — Matemática",
    "Professor(a) — Português",
    "Professor(a) — Ciências",
    "Coordenador(a) Pedagógico(a)",
    "Secretário(a) Escolar",
    "Porteiro(a)",
]


class Command(BaseCommand):
    help = "Popula o PostgreSQL com dados iniciais comerciais, usuários com RBAC, turnos, dispositivos e histórico real."

    def handle(self, *args, **options):
        ConfiguracaoEscola.objects.all().delete()
        ConfiguracaoEscola.objects.create(
            nome_escola="Escola Natálio Vassoler",
            notif_atraso=True,
            notif_ausencia=True,
            notif_nao_reconhecido=True,
            notif_saida_antecipada=True,
            limite_manha="07:20",
            limite_tarde="13:20",
            saida_manha="11:30",
            saida_tarde="17:30",
            cooldown_segundos=45,
            tempo_minimo_permanencia_min=2,
            limiar_confianca=Decimal("0.380"),
            retencao_logs_dias=365,
            modo_passivo=True,
        )

        turnos = {
            nome: Turno.objects.update_or_create(
                nome=nome,
                defaults={
                    "inicio": inicio,
                    "limite_entrada": limite_ent,
                    "termino": termino,
                    "limite_saida_antecipada": limite_sai,
                    "ativo": True,
                },
            )[0]
            for nome, inicio, limite_ent, termino, limite_sai in [
                ("Manhã", time(7, 0), time(7, 20), time(11, 45), time(11, 30)),
                ("Tarde", time(13, 0), time(13, 20), time(17, 45), time(17, 30)),
                ("Integral", time(7, 0), time(7, 20), time(16, 45), time(16, 30)),
            ]
        }

        for nome in TURMAS:
            Turma.objects.update_or_create(
                nome=nome,
                defaults={"ano_letivo": 2026, "turno": turnos["Tarde" if nome.startswith("9") else "Manhã"], "ativo": True},
            )

        # Usuários reais com perfis RBAC
        AuthToken.objects.all().delete()
        contas = [
            ("admin@escola.edu.br", "Admin@2026", "Administrador Escolar", "admin", True),
            ("coordenacao@escola.edu.br", "Coord@2026", "Marina Coutinho", "coordenacao", True),
            ("secretaria@escola.edu.br", "Sec@2026", "Carla Secretaria", "secretaria", False),
        ]
        for email, password, nome_exib, papel, is_staff in contas:
            user, _ = User.objects.update_or_create(
                username=email,
                defaults={
                    "email": email,
                    "first_name": nome_exib.split()[0],
                    "last_name": " ".join(nome_exib.split()[1:]),
                    "is_staff": is_staff,
                    "is_superuser": papel == "admin",
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save()
            PerfilUsuario.objects.update_or_create(
                user=user,
                defaults={"nome_exibicao": nome_exib, "papel": papel},
            )

        # Dispositivos de portaria
        dev_key = os.getenv("PORTARIA_DEV_KEY", "portaria-dev-key-2026-trocar-em-producao").strip()
        DispositivoPortaria.objects.all().delete()
        DispositivoPortaria.objects.create(
            nome="Portaria Principal - Câmera 01",
            portal="Portaria principal",
            sentido_padrao="auto",
            api_key_hash=hash_secret(dev_key),
            api_key_prefixo=dev_key[:12],
            ativo=True,
        )
        _, lat_prefix, lat_hash = generate_secret("port")
        DispositivoPortaria.objects.create(
            nome="Portaria Lateral - Câmera 02",
            portal="Catraca lateral",
            sentido_padrao="auto",
            api_key_hash=lat_hash,
            api_key_prefixo=lat_prefix,
            ativo=True,
        )

        # Limpa dados escolares para repopular com consistência
        LogAuditoria.objects.all().delete()
        Alerta.objects.all().delete()
        RegistroAcesso.objects.all().delete()
        DadoBiometrico.objects.all().delete()
        RelAlunoResponsavel.objects.all().delete()
        Responsavel.objects.all().delete()
        Aluno.objects.all().delete()
        Funcionario.objects.all().delete()

        now = timezone.now()
        alunos = []
        funcionarios = []

        for i, nome in enumerate(ALUNOS):
            turma_nome = TURMAS[i % len(TURMAS)]
            turma_obj = Turma.objects.get(nome=turma_nome)
            resp_nome = f"Responsável de {nome.split()[0]}"
            resp_fone = f"(48) 9{8000 + i:04d}-{1000 + i:04d}"

            aluno = Aluno.objects.create(
                nome=nome,
                documento=f"2026{1000 + i}",
                turma=turma_nome,
                turno=turma_obj.turno.nome,
                turma_ref=turma_obj,
                turno_ref=turma_obj.turno,
                status="inativo" if i == 8 else "ativo",
                contato_nome=resp_nome,
                contato_telefone=resp_fone,
                data_nascimento=date(2012 + i % 4, 3 + i % 8, 3 + i % 20),
                consentimento_biometrico=(i != 8),
                consentimento_em=now if i != 8 else None,
                consentimento_responsavel=resp_nome if i != 8 else "",
            )
            alunos.append(aluno)

            cpf_ficticio = f"{100 + i:03d}{200 + i:03d}{300 + i:03d}{10 + i:02d}"
            cpf_enc, key_id = encrypt_text(cpf_ficticio)
            phone_enc, _ = encrypt_text(resp_fone)
            resp_obj = Responsavel.objects.create(
                nome=resp_nome,
                cpf_enc=cpf_enc,
                phone_enc=phone_enc,
                cpf_hash=blind_index(cpf_ficticio, purpose="cpf"),
                key_id=key_id,
            )
            RelAlunoResponsavel.objects.create(aluno=aluno, responsavel=resp_obj)

        for i, nome in enumerate(FUNCIONARIOS):
            turno_nome = "Integral" if i % 3 == 0 else ("Tarde" if i % 2 else "Manhã")
            funcionarios.append(
                Funcionario.objects.create(
                    nome=nome,
                    documento=f"FUNC-{300 + i}",
                    cargo=CARGOS[i],
                    turno=turno_nome,
                    turno_ref=turnos[turno_nome],
                    contato_nome=f"Contato de emergência de {nome.split()[0]}",
                    contato_telefone=f"(48) 9{7000 + i:04d}-{2000 + i:04d}",
                    data_admissao=date(2018 + i % 6, 1 + i % 9, 1 + i % 20),
                    consentimento_biometrico=True,
                    consentimento_em=now,
                )
            )

        # Histórico dos últimos 5 dias úteis (incluindo hoje)
        tz = timezone.get_current_timezone()
        local_today = timezone.localdate()
        weekdays = []
        cursor = local_today
        while len(weekdays) < 5:
            if cursor.weekday() < 5:
                weekdays.append(cursor)
            cursor -= timedelta(days=1)
        weekdays.reverse()

        disp_principal = DispositivoPortaria.objects.get(nome="Portaria Principal - Câmera 01")
        disp_lateral = DispositivoPortaria.objects.get(nome="Portaria Lateral - Câmera 02")

        for day_idx, dia in enumerate(weekdays):
            is_today = dia == local_today
            for i, person in enumerate(alunos + funcionarios):
                if person.status == "inativo":
                    continue
                # Simula ausência pontual realista
                if (i + day_idx) % 7 == 4:
                    continue

                is_tarde = person.turno == "Tarde"
                base_h = 13 if is_tarde else 7
                minute_offset = (i * 3 + day_idx * 2) % 28
                dt_entrada = timezone.make_aware(datetime.combine(dia, time(base_h, minute_offset)), tz)
                is_atraso = minute_offset > 20
                kwargs = {"aluno": person} if isinstance(person, Aluno) else {"funcionario": person}

                reg_in = RegistroAcesso.objects.create(
                    dispositivo=disp_principal,
                    data_hora=dt_entrada,
                    portal="Portaria principal",
                    tipo="entrada",
                    status="atraso" if is_atraso else "reconhecido",
                    confianca=Decimal("0.6420"),
                    incidente=is_atraso,
                    **kwargs,
                )

                # Nos dias anteriores ou em parte dos alunos hoje, registra saída
                if not is_today or i % 5 == 0:
                    early = (i % 6 == 0) and isinstance(person, Aluno)
                    out_h = (17 if is_tarde else 11) if not early else (16 if is_tarde else 10)
                    out_m = 45 if not early else 50
                    dt_saida = timezone.make_aware(datetime.combine(dia, time(out_h, out_m)), tz)
                    reg_out = RegistroAcesso.objects.create(
                        dispositivo=disp_principal,
                        data_hora=dt_saida,
                        portal="Portaria principal",
                        tipo="saida",
                        status="saida-antecipada" if early else "reconhecido",
                        confianca=Decimal("0.6180"),
                        incidente=early,
                        **kwargs,
                    )
                    if is_today and early:
                        Alerta.objects.create(
                            pessoa_tipo="aluno",
                            pessoa_id=person.pk,
                            registro_acesso=reg_out,
                            tipo="Saída antecipada",
                            descricao=f"Saída antes do término do turno registrada às {dt_saida.strftime('%H:%M')}.",
                            severidade="media",
                            status="novo",
                        )

                if is_today and is_atraso:
                    Alerta.objects.create(
                        pessoa_tipo="aluno" if isinstance(person, Aluno) else "funcionario",
                        pessoa_id=person.pk,
                        registro_acesso=reg_in,
                        tipo="Atraso na entrada",
                        descricao=f"Entrada após o horário limite registrada às {dt_entrada.strftime('%H:%M')}.",
                        severidade="media",
                        status="novo",
                    )

        # Tentativa não reconhecida hoje na Catraca lateral
        dt_unk = timezone.make_aware(datetime.combine(local_today, time(7, 14)), tz)
        reg_unk = RegistroAcesso.objects.create(
            dispositivo=disp_lateral,
            data_hora=dt_unk,
            portal="Catraca lateral",
            tipo="entrada",
            status="nao-reconhecido",
            incidente=True,
        )
        Alerta.objects.create(
            pessoa_tipo="",
            pessoa_id=None,
            registro_acesso=reg_unk,
            tipo="Tentativa não reconhecida",
            descricao="Reconhecimento facial não identificou nenhum cadastro na portaria.",
            severidade="alta",
            status="novo",
        )

        LogAuditoria.objects.create(
            tabela="sistema",
            operacao="SYNC",
            chave="seed_mock_v2",
            usuario="system",
            detalhes={"alunos": len(alunos), "funcionarios": len(funcionarios)},
            sensivel=False,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed v2.0 concluído: {len(alunos)} alunos, {len(funcionarios)} funcionários, "
                f"{DispositivoPortaria.objects.count()} dispositivos, "
                f"{RegistroAcesso.objects.count()} registros de acesso e {Alerta.objects.count()} alertas."
            )
        )
