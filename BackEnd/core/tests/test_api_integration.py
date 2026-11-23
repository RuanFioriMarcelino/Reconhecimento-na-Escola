import json
from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch

import numpy as np
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from ..crypto.cipher import encrypt_vector
from ..models import (
    Alerta,
    Aluno,
    ConfiguracaoEscola,
    DadoBiometrico,
    DispositivoPortaria,
    Funcionario,
    LogAuditoria,
    PerfilUsuario,
    RegistroAcesso,
    Turma,
    Turno,
)
from ..security import hash_secret


@override_settings(ALLOWED_HOSTS=["testserver"])
class CommercialV2ApiIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cfg = ConfiguracaoEscola.objects.create(
            nome_escola="Escola Teste",
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
        )
        self.turno_manha = Turno.objects.create(
            nome="Manhã",
            inicio=time(7, 0),
            limite_entrada=time(7, 20),
            termino=time(11, 45),
            limite_saida_antecipada=time(11, 30),
        )
        self.turma = Turma.objects.create(nome="6º A", turno=self.turno_manha, ano_letivo=2026)

        self.admin_user = User.objects.create_user(username="admin@escola.edu.br", password="StrongPassword!0")
        PerfilUsuario.objects.create(user=self.admin_user, nome_exibicao="Admin Teste", papel="admin")

        self.coord_user = User.objects.create_user(username="coord@escola.edu.br", password="StrongPassword!1")
        PerfilUsuario.objects.create(user=self.coord_user, nome_exibicao="Marina Coord", papel="coordenacao")

        self.sec_user = User.objects.create_user(username="sec@escola.edu.br", password="StrongPassword!2")
        PerfilUsuario.objects.create(user=self.sec_user, nome_exibicao="Carla Sec", papel="secretaria")

        self.view_user = User.objects.create_user(username="view@escola.edu.br", password="StrongPassword!3")
        PerfilUsuario.objects.create(user=self.view_user, nome_exibicao="João View", papel="visualizador")

        self.aluno = Aluno.objects.create(
            nome="Ana Teste",
            documento="TESTE-001",
            turma="6º A",
            turno="Manhã",
            turma_ref=self.turma,
            turno_ref=self.turno_manha,
            contato_nome="Responsável Teste",
            contato_telefone="48999999999",
            consentimento_biometrico=True,
            consentimento_em=timezone.now(),
        )

        self.raw_device_key = "port_test_secret_key_123456"
        self.dispositivo = DispositivoPortaria.objects.create(
            nome="Portaria 01",
            portal="Portaria principal",
            sentido_padrao="auto",
            api_key_hash=hash_secret(self.raw_device_key),
            api_key_prefixo=self.raw_device_key[:12],
            ativo=True,
        )

    def _login(self, email="coord@escola.edu.br", password="StrongPassword!1"):
        res = self.client.post(
            "/api/login/",
            data=json.dumps({"email": email, "senha": password}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        return res.json()["token"]

    def test_health_endpoint(self):
        res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["version"], "2.0.0")

    def test_auth_login_rate_limit_and_logout(self):
        for _ in range(5):
            r = self.client.post(
                "/api/login/",
                data=json.dumps({"email": "coord@escola.edu.br", "senha": "errada"}),
                content_type="application/json",
            )
            self.assertEqual(r.status_code, 401)

        blocked = self.client.post(
            "/api/login/",
            data=json.dumps({"email": "coord@escola.edu.br", "senha": "StrongPassword!1"}),
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 429)

        cache.clear()
        token = self._login()
        auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        me_res = self.client.get("/api/me/", **auth_headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["papel"], "coordenacao")

        out_res = self.client.post("/api/logout/", **auth_headers)
        self.assertEqual(out_res.status_code, 200)
        self.assertEqual(self.client.get("/api/me/", **auth_headers).status_code, 401)

    def test_rbac_protection_across_all_roles(self):
        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 401)

        sec_headers = {"HTTP_AUTHORIZATION": f"Bearer {self._login('sec@escola.edu.br', 'StrongPassword!2')}"}
        self.assertEqual(self.client.get("/api/bootstrap/", **sec_headers).status_code, 200)
        self.assertEqual(
            self.client.patch(
                "/api/settings/",
                data=json.dumps({"cooldownSegundos": 30}),
                content_type="application/json",
                **sec_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/devices/",
                data=json.dumps({"nome": "Cam", "portal": "P2"}),
                content_type="application/json",
                **sec_headers,
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/audit/", **sec_headers).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/classes/",
                data=json.dumps({"tipo": "turno", "nome": "Noite", "inicio": "19:00", "limiteEntrada": "19:20"}),
                content_type="application/json",
                **sec_headers,
            ).status_code,
            403,
        )

        # Visualizador só lê, não cria/edita pessoas
        view_headers = {"HTTP_AUTHORIZATION": f"Bearer {self._login('view@escola.edu.br', 'StrongPassword!3')}"}
        self.assertEqual(self.client.get("/api/dashboard/", **view_headers).status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/people/",
                data=json.dumps({
                    "tipo": "aluno",
                    "nome": "Teste View",
                    "documento": "V-001",
                    "grupo": "6º A",
                    "contatoNome": "Resp",
                    "contatoTelefone": "48999999999",
                }),
                content_type="application/json",
                **view_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/people/aluno-{self.aluno.pk}/status/",
                data=json.dumps({"status": "inativo"}),
                content_type="application/json",
                **view_headers,
            ).status_code,
            403,
        )

    def test_people_crud_validation_edge_cases_and_lgpd_revocation(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self._login()}"}

        # Campos ausentes -> 400
        res_missing = self.client.post(
            "/api/people/",
            data=json.dumps({"tipo": "aluno", "nome": "Incompleto"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(res_missing.status_code, 400)
        self.assertIn("fields", res_missing.json())

        # Documento duplicado -> 409
        res_dup = self.client.post(
            "/api/people/",
            data=json.dumps({
                "tipo": "aluno",
                "nome": "Outro",
                "documento": "TESTE-001",
                "grupo": "6º A",
                "turno": "Manhã",
                "contatoNome": "Resp",
                "contatoTelefone": "48988888888",
            }),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(res_dup.status_code, 409)

        # PATCH com campo longo em documento/turno não dá 500 (trunca com segurança)
        res_patch = self.client.patch(
            f"/api/people/aluno-{self.aluno.pk}/",
            data=json.dumps({"turno": "X" * 60, "contatoNome": "Responsável Novo"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(res_patch.status_code, 200)
        self.assertEqual(len(res_patch.json()["turno"]), 20)

        # person_ref malformado em GET e status -> 404
        self.assertEqual(self.client.get("/api/people/invalido/", **headers).status_code, 404)
        self.assertEqual(
            self.client.patch(
                "/api/people/invalido/status/",
                data=json.dumps({"status": "inativo"}),
                content_type="application/json",
                **headers,
            ).status_code,
            404,
        )

        # GET /api/people/<ref>/ com histórico paginado e alertas relacionados
        r = RegistroAcesso.objects.create(
            aluno=self.aluno, data_hora=timezone.now(), portal="Portaria principal", tipo="entrada", status="reconhecido"
        )
        Alerta.objects.create(
            pessoa_tipo="aluno", pessoa_id=self.aluno.pk, registro_acesso=r,
            tipo="Atraso na entrada", descricao="Teste perfil", severidade="media", status="novo",
        )
        det = self.client.get(f"/api/people/aluno-{self.aluno.pk}/?page=1&page_size=5", **headers)
        self.assertEqual(det.status_code, 200)
        self.assertEqual(det.json()["historyPagination"]["total"], 1)
        self.assertEqual(len(det.json()["alerts"]), 1)

        # Revogação LGPD de biometria
        vec = np.ones(128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=self.aluno.pk)
        DadoBiometrico.objects.create(
            aluno=self.aluno, qualidade=Decimal("0.92"), vetor_enc=blob, key_id=key_id, ativo=True
        )
        rev = self.client.delete(f"/api/people/aluno-{self.aluno.pk}/biometrics/", **headers)
        self.assertEqual(rev.status_code, 200)
        self.assertEqual(rev.json()["removidos"], 1)
        self.aluno.refresh_from_db()
        self.assertFalse(self.aluno.consentimento_biometrico)
        self.assertTrue(LogAuditoria.objects.filter(tabela="dados_biometricos", operacao="DELETE", sensivel=True).exists())

    def test_classes_and_settings_validation_fixes(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self._login()}"}

        # Turno com hora malformada -> 400 (não 500)
        bad_time = self.client.post(
            "/api/classes/",
            data=json.dumps({"tipo": "turno", "nome": "Noite", "inicio": "99:99", "limiteEntrada": "19:20"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(bad_time.status_code, 400)

        # Turno com nome vazio -> 400
        empty_name = self.client.post(
            "/api/classes/",
            data=json.dumps({"tipo": "turno", "nome": "   ", "inicio": "19:00", "limiteEntrada": "19:20"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(empty_name.status_code, 400)

        # Turno válido -> 201 e duplicado -> 409
        ok_turno = self.client.post(
            "/api/classes/",
            data=json.dumps({"tipo": "turno", "nome": "Noite", "inicio": "19:00", "limiteEntrada": "19:20"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(ok_turno.status_code, 201)
        dup_turno = self.client.post(
            "/api/classes/",
            data=json.dumps({"tipo": "turno", "nome": "Noite", "inicio": "19:00", "limiteEntrada": "19:20"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(dup_turno.status_code, 409)

        # Settings com float de precisão longa (comum em JS) -> 200 arredondado para 3 casas
        ok_float = self.client.patch(
            "/api/settings/",
            data=json.dumps({"limiarConfianca": 0.38000000000000006, "cooldownSegundos": 50}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(ok_float.status_code, 200)
        self.assertAlmostEqual(ok_float.json()["settings"]["limiarConfianca"], 0.38, places=3)

        # Settings fora do intervalo -> 400
        bad_range = self.client.patch(
            "/api/settings/",
            data=json.dumps({"limiarConfianca": 1.5}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(bad_range.status_code, 400)

    def test_portaria_device_auth_batch_and_disabled_device(self):
        self.assertEqual(self.client.get("/api/portaria/config/").status_code, 401)
        dev_headers = {"HTTP_X_PORTARIA_KEY": self.raw_device_key}

        # Config inclui samplePeople dinâmico
        cfg_res = self.client.get("/api/portaria/config/", **dev_headers)
        self.assertEqual(cfg_res.status_code, 200)
        self.assertEqual(cfg_res.json()["samplePeople"][0]["uid"], f"aluno-{self.aluno.pk}")

        # Heartbeat + galeria
        hb = self.client.post(
            "/api/portaria/heartbeat/",
            data=json.dumps({"fps": 29.5, "aiMs": 18.2, "cameraOk": True}),
            content_type="application/json",
            **dev_headers,
        )
        self.assertEqual(hb.status_code, 200)

        vec = np.ones(128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=self.aluno.pk)
        DadoBiometrico.objects.create(
            aluno=self.aluno, qualidade=Decimal("0.90"), vetor_enc=blob, key_id=key_id, ativo=True
        )
        gal1 = self.client.get("/api/portaria/biometrics/", **dev_headers)
        self.assertEqual(gal1.status_code, 200)
        self.assertFalse(gal1.json()["unchanged"])
        version = gal1.json()["version"]
        self.assertTrue(self.client.get(f"/api/portaria/biometrics/?version={version}", **dev_headers).json()["unchanged"])

        # Lote de eventos com confiança inválida sanitizada + idempotência + saída antecipada + desconhecido
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        dt_in = timezone.make_aware(timezone.datetime.combine(today, time(7, 10)), tz)
        dt_out = timezone.make_aware(timezone.datetime.combine(today, time(10, 30)), tz)

        batch = self.client.post(
            "/api/portaria/events/",
            data=json.dumps({
                "events": [
                    {
                        "clientEventId": "evt-b1",
                        "personRef": f"aluno-{self.aluno.pk}",
                        "tipo": "auto",
                        "confianca": "nao-numerico",
                        "timestamp": dt_in.isoformat(),
                    },
                    {
                        "clientEventId": "evt-b1",
                        "personRef": f"aluno-{self.aluno.pk}",
                        "tipo": "auto",
                        "timestamp": dt_in.isoformat(),
                    },
                    {
                        "clientEventId": "evt-b2",
                        "personRef": f"aluno-{self.aluno.pk}",
                        "tipo": "auto",
                        "confianca": 0.68,
                        "timestamp": dt_out.isoformat(),
                    },
                    {
                        "clientEventId": "evt-b3",
                        "personRef": None,
                        "tipo": "auto",
                        "timestamp": dt_out.isoformat(),
                    },
                ]
            }),
            content_type="application/json",
            **dev_headers,
        )
        self.assertEqual(batch.status_code, 201)
        results = batch.json()["results"]
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]["tipo"], "entrada")
        self.assertIsNone(results[0]["confianca"])
        self.assertTrue(results[1]["deduplicated"])
        self.assertEqual(results[2]["status"], "saida-antecipada")
        self.assertEqual(results[3]["status"], "nao-reconhecido")

        # Dispositivo desativado -> 401
        self.dispositivo.ativo = False
        self.dispositivo.save(update_fields=["ativo"])
        self.assertEqual(self.client.get("/api/portaria/config/", **dev_headers).status_code, 401)

    def test_devices_alerts_reports_export_and_malformed_dates(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self._login()}"}

        d_res = self.client.post(
            "/api/devices/",
            data=json.dumps({"nome": "Portão Fundos", "portal": "Fundos", "sentidoPadrao": "auto"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(d_res.status_code, 201)
        dev_id = d_res.json()["id"]
        first_key = d_res.json()["apiKey"]

        rot = self.client.patch(
            f"/api/devices/{dev_id}/",
            data=json.dumps({"rotacionarChave": True}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(rot.status_code, 200)
        self.assertNotEqual(rot.json()["apiKey"], first_key)

        alerta = Alerta.objects.create(
            pessoa_tipo="aluno", pessoa_id=self.aluno.pk, tipo="Atraso na entrada", descricao="Teste", severidade="media"
        )
        a_res = self.client.patch(
            f"/api/alerts/{alerta.pk}/",
            data=json.dumps({"status": "resolvido", "observacao": "Justificado"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(a_res.status_code, 200)
        alerta.refresh_from_db()
        self.assertEqual(alerta.resolvido_por, self.coord_user)

        self.assertEqual(self.client.get("/api/reports/export/?de=data-ruim", **headers).status_code, 400)
        csv_res = self.client.get("/api/reports/export/", **headers)
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res["Content-Type"])

    def test_pagination_search_dashboard_and_incremental_live(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self._login()}"}

        a2 = Aluno.objects.create(
            nome="Bruno Paginado",
            documento="PAG-002",
            turma="6º A",
            turno="Manhã",
            turma_ref=self.turma,
            turno_ref=self.turno_manha,
            contato_nome="Resp B",
            contato_telefone="48977777777",
        )
        Aluno.objects.create(
            nome="Carla Paginada",
            documento="PAG-003",
            turma="6º A",
            turno="Manhã",
            turma_ref=self.turma,
            turno_ref=self.turno_manha,
            contato_nome="Resp C",
            contato_telefone="48966666666",
        )
        vec = np.ones(128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=a2.pk)
        DadoBiometrico.objects.create(aluno=a2, qualidade=Decimal("0.91"), vetor_enc=blob, key_id=key_id, ativo=True)

        p1 = self.client.get("/api/people/?tipo=aluno&page=1&page_size=2", **headers)
        self.assertEqual(p1.status_code, 200)
        self.assertEqual(len(p1.json()["items"]), 2)
        self.assertEqual(p1.json()["pagination"]["total"], 3)
        self.assertTrue(p1.json()["pagination"]["hasNext"])

        p_bio = self.client.get("/api/people/?tipo=aluno&biometria=sim", **headers)
        self.assertEqual(p_bio.json()["pagination"]["total"], 1)

        p_search = self.client.get("/api/people/?tipo=aluno&search=Paginad", **headers)
        self.assertEqual(p_search.json()["pagination"]["total"], 2)

        now = timezone.now()
        r1 = RegistroAcesso.objects.create(
            aluno=self.aluno, data_hora=now, portal="Portaria principal", tipo="entrada", status="atraso", incidente=True
        )
        RegistroAcesso.objects.create(
            aluno=a2, data_hora=now, portal="Catraca lateral", tipo="entrada", status="reconhecido"
        )
        Alerta.objects.create(
            pessoa_tipo="aluno", pessoa_id=self.aluno.pk, registro_acesso=r1,
            tipo="Atraso na entrada", descricao="Atraso teste", severidade="media", status="novo",
        )

        self.assertEqual(self.client.get("/api/logs/?status=atraso&page=1&page_size=10", **headers).json()["pagination"]["total"], 1)
        self.assertEqual(self.client.get("/api/alerts/?status=abertos&page=1&page_size=10", **headers).json()["pagination"]["total"], 1)

        dash = self.client.get("/api/dashboard/", **headers)
        self.assertEqual(dash.status_code, 200)
        dash_body = dash.json()
        self.assertEqual(dash_body["summary"]["alunosAtivos"], 3)
        self.assertEqual(dash_body["summary"]["naEscolaAlunos"], 2)
        self.assertEqual(len(dash_body["analytics"]["semana"]), 5)

        last_log_id = dash_body["cursor"]["lastLogId"]
        last_alert_id = dash_body["cursor"]["lastAlertId"]
        self.assertFalse(
            self.client.get(f"/api/live/?since_log_id={last_log_id}&since_alert_id={last_alert_id}", **headers).json()["changed"]
        )

        RegistroAcesso.objects.create(
            aluno=a2, data_hora=now, portal="Portaria principal", tipo="saida", status="reconhecido"
        )
        live_delta = self.client.get(f"/api/live/?since_log_id={last_log_id}&since_alert_id={last_alert_id}", **headers)
        self.assertTrue(live_delta.json()["changed"])
        self.assertEqual(len(live_delta.json()["newLogs"]), 1)

    @override_settings(DEBUG=False)
    def test_api_unexpected_exception_returns_json_500_never_html(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self._login()}"}
        with patch("core.views._dashboard_summary", side_effect=RuntimeError("boom-simulado")):
            res = self.client.get("/api/dashboard/", **headers)
        self.assertEqual(res.status_code, 500)
        self.assertIn("application/json", res["Content-Type"])
        body = res.json()
        self.assertIn("requestId", body)
        self.assertNotIn("boom-simulado", body["detail"])
