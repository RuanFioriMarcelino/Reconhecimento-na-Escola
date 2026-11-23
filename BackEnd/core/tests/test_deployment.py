from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings

from ..models import Aluno, DispositivoPortaria, Funcionario, Turma, Turno


@override_settings(ALLOWED_HOSTS=["testserver"])
class DeploymentReadinessTests(TestCase):
    def test_no_pending_model_migrations(self):
        out = StringIO()
        call_command("makemigrations", "core", check=True, dry_run=True, stdout=out)

    def test_postgres_trgm_extension_and_performance_indexes_exist(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
            self.assertIsNotNone(cursor.fetchone(), "Extensão pg_trgm deve estar ativa no PostgreSQL.")

            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                """
            )
            indexes = {row[0] for row in cursor.fetchall()}

        expected_indexes = {
            "aluno_nome_trgm_idx",
            "aluno_doc_trgm_idx",
            "func_nome_trgm_idx",
            "func_doc_trgm_idx",
            "acesso_data_id_idx",
            "acesso_tipo_data_idx",
            "acesso_portal_data_idx",
            "acesso_desconhecido_portal_idx",
            "acesso_incidente_data_idx",
            "alerta_aberto_data_idx",
            "bio_aluno_only_ativo_idx",
            "bio_func_only_ativo_idx",
            "auditoria_sensivel_idx",
            "auth_token_ativo_hash_idx",
            "disp_ativo_key_idx",
        }
        missing = expected_indexes - indexes
        self.assertFalse(missing, f"Índices de desempenho ausentes no PostgreSQL: {sorted(missing)}")

    def test_seed_mock_command_is_idempotent(self):
        out1 = StringIO()
        out2 = StringIO()
        call_command("seed_mock", stdout=out1)
        counts_first = (
            Turno.objects.count(),
            Turma.objects.count(),
            Aluno.objects.count(),
            Funcionario.objects.count(),
            DispositivoPortaria.objects.count(),
        )
        self.assertGreater(counts_first[2], 0)
        self.assertGreater(counts_first[3], 0)

        # Segunda execução não deve duplicar dados nem falhar
        call_command("seed_mock", stdout=out2)
        counts_second = (
            Turno.objects.count(),
            Turma.objects.count(),
            Aluno.objects.count(),
            Funcionario.objects.count(),
            DispositivoPortaria.objects.count(),
        )
        self.assertEqual(counts_first, counts_second)

    def test_security_and_cache_headers_on_api(self):
        res = self.client.get("/api/health/", HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(res.status_code, 200)
        self.assertIn("X-Request-ID", res)
        self.assertIn("no-store", res["Cache-Control"])
        self.assertEqual(res["Permissions-Policy"], "camera=(self)")
        self.assertEqual(res.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.get("Access-Control-Allow-Origin"), "http://localhost:5173")

        # Origem não autorizada não recebe CORS allow-origin
        res_bad = self.client.get("/api/health/", HTTP_ORIGIN="https://evil.example.com")
        self.assertIsNone(res_bad.get("Access-Control-Allow-Origin"))
