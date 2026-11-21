import base64
import json
import os
from datetime import time, timedelta
from decimal import Decimal

import numpy as np
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .crypto.cipher import blind_index, decrypt_vector, encrypt_vector
from .models import (
    Alerta,
    Aluno,
    ConfiguracaoEscola,
    DadoBiometrico,
    DispositivoPortaria,
    LogAuditoria,
    PerfilUsuario,
    RegistroAcesso,
    Turma,
    Turno,
)
from .security import hash_secret


@override_settings(ALLOWED_HOSTS=["testserver"])
class CommercialV2Tests(TestCase):
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

        self.coord_user = User.objects.create_user(username="coord@escola.edu.br", password="StrongPassword!1")
        PerfilUsuario.objects.create(user=self.coord_user, nome_exibicao="Marina Coord", papel="coordenacao")

        self.sec_user = User.objects.create_user(username="sec@escola.edu.br", password="StrongPassword!2")
        PerfilUsuario.objects.create(user=self.sec_user, nome_exibicao="Carla Sec", papel="secretaria")

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
        # 5 falhas consecutivas devem disparar 429
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

        # Limpa cache e faz login real com sucesso
        cache.clear()
        token = self._login()
        auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        me_res = self.client.get("/api/me/", **auth_headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["papel"], "coordenacao")

        # Logout revoga o token
        out_res = self.client.post("/api/logout/", **auth_headers)
        self.assertEqual(out_res.status_code, 200)

        after_out = self.client.get("/api/me/", **auth_headers)
        self.assertEqual(after_out.status_code, 401)

    def test_rbac_protection(self):
        # Sem token -> 401
        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 401)

        # Secretaria pode cadastrar pessoa, mas recebe 403 em configurações/dispositivos/auditoria
        sec_token = self._login("sec@escola.edu.br", "StrongPassword!2")
        sec_headers = {"HTTP_AUTHORIZATION": f"Bearer {sec_token}"}

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

    def test_crypto_aes_gcm_aad_rotation_and_blind_index(self):
        vec = np.linspace(0.1, 1.0, 128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=self.aluno.pk)
        recovered = decrypt_vector(blob, key_id=key_id, owner_type="aluno", owner_id=self.aluno.pk)
        self.assertAlmostEqual(float(np.linalg.norm(recovered)), 1.0, places=5)
        self.assertGreater(float(np.dot(recovered, vec / np.linalg.norm(vec))), 0.9999)

        # AAD de outro titular deve falhar
        with self.assertRaises(Exception):
            decrypt_vector(blob, key_id=key_id, owner_type="aluno", owner_id=999999)

        # Rotação de chave usando BIOMETRIC_PREVIOUS_KEYS
        old_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        new_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        with override_settings(BIOMETRIC_MASTER_KEY=old_key, BIOMETRIC_KEY_ID="k0"):
            old_blob, old_kid = encrypt_vector(vec, owner_type="aluno", owner_id=self.aluno.pk)
        with override_settings(BIOMETRIC_MASTER_KEY=new_key, BIOMETRIC_KEY_ID="k1", BIOMETRIC_PREVIOUS_KEYS={"k0": old_key}):
            rot_recovered = decrypt_vector(old_blob, key_id=old_kid, owner_type="aluno", owner_id=self.aluno.pk)
            self.assertAlmostEqual(float(np.linalg.norm(rot_recovered)), 1.0, places=5)

        # Blind index determinístico
        h1 = blind_index("12345678900", "cpf")
        h2 = blind_index("12345678900", "cpf")
        h3 = blind_index("99999999999", "cpf")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_people_crud_validation_and_lgpd_revocation(self):
        token = self._login()
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

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

        # Cria template biométrico criptografado e revoga via DELETE LGPD
        vec = np.ones(128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=self.aluno.pk)
        DadoBiometrico.objects.create(
            aluno=self.aluno,
            qualidade=Decimal("0.92"),
            vetor_enc=blob,
            key_id=key_id,
            ativo=True,
        )
        rev = self.client.delete(f"/api/people/aluno-{self.aluno.pk}/biometrics/", **headers)
        self.assertEqual(rev.status_code, 200)
        self.assertEqual(rev.json()["removidos"], 1)
        self.aluno.refresh_from_db()
        self.assertFalse(self.aluno.consentimento_biometrico)
        self.assertTrue(LogAuditoria.objects.filter(tabela="dados_biometricos", operacao="DELETE", sensivel=True).exists())

    def test_portaria_device_auth_gallery_and_passive_flow(self):
        # Sem X-Portaria-Key -> 401
        self.assertEqual(self.client.get("/api/portaria/config/").status_code, 401)

        dev_headers = {"HTTP_X_PORTARIA_KEY": self.raw_device_key}

        # Heartbeat com telemetria
        hb = self.client.post(
            "/api/portaria/heartbeat/",
            data=json.dumps({"fps": 29.5, "aiMs": 18.2, "cameraOk": True}),
            content_type="application/json",
            **dev_headers,
        )
        self.assertEqual(hb.status_code, 200)
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.telemetria["fps"], 29.5)

        # Galeria biométrica e version unchanged
        vec = np.ones(128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=self.aluno.pk)
        DadoBiometrico.objects.create(
            aluno=self.aluno,
            qualidade=Decimal("0.90"),
            vetor_enc=blob,
            key_id=key_id,
            ativo=True,
        )
        gal1 = self.client.get("/api/portaria/biometrics/", **dev_headers)
        self.assertEqual(gal1.status_code, 200)
        self.assertFalse(gal1.json()["unchanged"])
        self.assertEqual(gal1.json()["total"], 1)
        version = gal1.json()["version"]

        gal2 = self.client.get(f"/api/portaria/biometrics/?version={version}", **dev_headers)
        self.assertEqual(gal2.status_code, 200)
        self.assertTrue(gal2.json()["unchanged"])

        # 1a passagem -> entrada (fixa horário local 07:10 para garantir entrada sem atraso)
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        dt_in = timezone.make_aware(timezone.datetime.combine(today, time(7, 10)), tz)

        ev1 = self.client.post(
            "/api/portaria/events/",
            data=json.dumps({
                "clientEventId": "evt-001",
                "personRef": f"aluno-{self.aluno.pk}",
                "tipo": "auto",
                "confianca": 0.65,
                "timestamp": dt_in.isoformat(),
            }),
            content_type="application/json",
            **dev_headers,
        )
        self.assertEqual(ev1.status_code, 201)
        res1 = ev1.json()["results"][0]
        self.assertEqual(res1["tipo"], "entrada")
        self.assertEqual(res1["status"], "reconhecido")

        # Reenvio idempotente -> deduplicated=True
        ev_dup = self.client.post(
            "/api/portaria/events/",
            data=json.dumps({
                "clientEventId": "evt-001",
                "personRef": f"aluno-{self.aluno.pk}",
                "tipo": "auto",
                "timestamp": dt_in.isoformat(),
            }),
            content_type="application/json",
            **dev_headers,
        )
        self.assertTrue(ev_dup.json()["results"][0]["deduplicated"])
        self.assertEqual(RegistroAcesso.objects.count(), 1)

        # Passagem 10s depois -> ignorada por cooldown
        ev_cd = self.client.post(
            "/api/portaria/events/",
            data=json.dumps({
                "clientEventId": "evt-002",
                "personRef": f"aluno-{self.aluno.pk}",
                "tipo": "auto",
                "timestamp": (dt_in + timedelta(seconds=10)).isoformat(),
            }),
            content_type="application/json",
            **dev_headers,
        )
        self.assertTrue(ev_cd.json()["results"][0]["ignored"])
        self.assertEqual(ev_cd.json()["results"][0]["reason"], "cooldown")

        # Passagem às 10:30 (após permanência e antes da saída normal 11:30) -> saida-antecipada + Alerta
        dt_out = timezone.make_aware(timezone.datetime.combine(today, time(10, 30)), tz)
        ev_out = self.client.post(
            "/api/portaria/events/",
            data=json.dumps({
                "clientEventId": "evt-003",
                "personRef": f"aluno-{self.aluno.pk}",
                "tipo": "auto",
                "confianca": 0.68,
                "timestamp": dt_out.isoformat(),
            }),
            content_type="application/json",
            **dev_headers,
        )
        res_out = ev_out.json()["results"][0]
        self.assertEqual(res_out["tipo"], "saida")
        self.assertEqual(res_out["status"], "saida-antecipada")
        self.assertTrue(Alerta.objects.filter(tipo="Saída antecipada").exists())

        # Rosto desconhecido -> nao-reconhecido + Alerta alta severidade
        ev_unk = self.client.post(
            "/api/portaria/events/",
            data=json.dumps({
                "clientEventId": "evt-004",
                "personRef": None,
                "tipo": "auto",
                "timestamp": dt_out.isoformat(),
            }),
            content_type="application/json",
            **dev_headers,
        )
        res_unk = ev_unk.json()["results"][0]
        self.assertEqual(res_unk["status"], "nao-reconhecido")
        self.assertTrue(Alerta.objects.filter(tipo="Tentativa não reconhecida", severidade="alta").exists())

    def test_settings_devices_alerts_and_csv_export(self):
        token = self._login()
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # Persistência de configurações
        s_res = self.client.patch(
            "/api/settings/",
            data=json.dumps({"cooldownSegundos": 60, "modoPassivo": True}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(s_res.status_code, 200)
        self.assertEqual(s_res.json()["settings"]["cooldownSegundos"], 60)

        # Criação e rotação de chave de dispositivo
        d_res = self.client.post(
            "/api/devices/",
            data=json.dumps({"nome": "Portão Fundos", "portal": "Fundos", "sentidoPadrao": "auto"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(d_res.status_code, 201)
        dev_id = d_res.json()["id"]
        first_key = d_res.json()["apiKey"]
        self.assertTrue(first_key.startswith("port_"))

        rot = self.client.patch(
            f"/api/devices/{dev_id}/",
            data=json.dumps({"rotacionarChave": True}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(rot.status_code, 200)
        self.assertNotEqual(rot.json()["apiKey"], first_key)

        # Fluxo de alerta em-analise -> resolvido
        alerta = Alerta.objects.create(
            pessoa_tipo="aluno",
            pessoa_id=self.aluno.pk,
            tipo="Atraso na entrada",
            descricao="Teste",
            severidade="media",
        )
        a_res = self.client.patch(
            f"/api/alerts/{alerta.pk}/",
            data=json.dumps({"status": "resolvido", "observacao": "Justificado pelo responsável"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(a_res.status_code, 200)
        self.assertEqual(a_res.json()["status"], "resolvido")
        alerta.refresh_from_db()
        self.assertEqual(alerta.resolvido_por, self.coord_user)

        # Exportação CSV e auditoria
        csv_res = self.client.get("/api/reports/export/", **headers)
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res["Content-Type"])
        self.assertTrue(LogAuditoria.objects.filter(tabela="registro_acesso", operacao="SELECT").exists())

    def test_pagination_search_dashboard_and_incremental_live(self):
        token = self._login()
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # Cria mais 2 alunos e registra biometria apenas em 1 deles
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

        # Paginação + filtro biométrico + busca trigram
        p1 = self.client.get("/api/people/?tipo=aluno&page=1&page_size=2", **headers)
        self.assertEqual(p1.status_code, 200)
        self.assertEqual(len(p1.json()["items"]), 2)
        self.assertEqual(p1.json()["pagination"]["total"], 3)
        self.assertTrue(p1.json()["pagination"]["hasNext"])

        p_bio = self.client.get("/api/people/?tipo=aluno&biometria=sim", **headers)
        self.assertEqual(p_bio.json()["pagination"]["total"], 1)
        self.assertEqual(p_bio.json()["items"][0]["nome"], "Bruno Paginado")

        p_search = self.client.get("/api/people/?tipo=aluno&search=Paginad", **headers)
        self.assertEqual(p_search.json()["pagination"]["total"], 2)

        # Registros de acesso e filtros paginados em /api/logs/ e /api/alerts/
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

        logs_res = self.client.get("/api/logs/?status=atraso&page=1&page_size=10", **headers)
        self.assertEqual(logs_res.status_code, 200)
        self.assertEqual(logs_res.json()["pagination"]["total"], 1)
        self.assertEqual(logs_res.json()["items"][0]["personName"], "Ana Teste")

        alerts_res = self.client.get("/api/alerts/?status=abertos&page=1&page_size=10", **headers)
        self.assertEqual(alerts_res.status_code, 200)
        self.assertEqual(alerts_res.json()["pagination"]["total"], 1)
        self.assertEqual(alerts_res.json()["items"][0]["personName"], "Ana Teste")
        self.assertEqual(alerts_res.json()["items"][0]["personGrupo"], "6º A")

        # Auditoria paginada com filtro sensivel=1
        LogAuditoria.objects.create(tabela="dados_biometricos", operacao="INSERT", chave="aluno:1", usuario="coord", sensivel=True)
        aud_res = self.client.get("/api/audit/?sensivel=1&page=1&page_size=10", **headers)
        self.assertEqual(aud_res.status_code, 200)
        self.assertGreaterEqual(aud_res.json()["pagination"]["total"], 1)
        self.assertTrue(all(x["sensivel"] for x in aud_res.json()["items"]))

        # Dashboard agregado via SQL
        dash = self.client.get("/api/dashboard/", **headers)
        self.assertEqual(dash.status_code, 200)
        dash_body = dash.json()
        self.assertEqual(dash_body["summary"]["alunosAtivos"], 3)
        self.assertEqual(dash_body["summary"]["naEscolaAlunos"], 2)
        self.assertEqual(len(dash_body["analytics"]["semana"]), 5)

        last_log_id = dash_body["cursor"]["lastLogId"]
        last_alert_id = dash_body["cursor"]["lastAlertId"]

        # /api/live/ sem alterações -> changed=False
        live_same = self.client.get(f"/api/live/?since_log_id={last_log_id}&since_alert_id={last_alert_id}", **headers)
        self.assertEqual(live_same.status_code, 200)
        self.assertFalse(live_same.json()["changed"])
        self.assertEqual(live_same.json()["newLogs"], [])

        # Novo evento chega -> /api/live/ retorna apenas o delta
        RegistroAcesso.objects.create(
            aluno=a2, data_hora=now, portal="Portaria principal", tipo="saida", status="reconhecido"
        )
        live_delta = self.client.get(f"/api/live/?since_log_id={last_log_id}&since_alert_id={last_alert_id}", **headers)
        self.assertEqual(live_delta.status_code, 200)
        self.assertTrue(live_delta.json()["changed"])
        self.assertEqual(len(live_delta.json()["newLogs"]), 1)
        self.assertEqual(live_delta.json()["newLogs"][0]["tipo"], "saida")

