import json

from django.test import TestCase, override_settings

from .models import Aluno


@override_settings(ALLOWED_HOSTS=["testserver"])
class ApiTests(TestCase):
    def setUp(self):
        self.aluno = Aluno.objects.create(
            nome="Ana Teste",
            documento="TESTE-001",
            turma="6º A",
            turno="Manhã",
            contato_nome="Responsável Teste",
            contato_telefone="48999999999",
        )

    def test_bootstrap_returns_people(self):
        response = self.client.get("/api/bootstrap/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["people"][0]["documento"], "TESTE-001")

    def test_create_person_rejects_missing_fields(self):
        response = self.client.post(
            "/api/people/",
            data=json.dumps({"tipo": "aluno", "nome": "Incompleto"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fields", response.json())

    def test_create_person_rejects_duplicate_document(self):
        response = self.client.post(
            "/api/people/",
            data=json.dumps({
                "tipo": "aluno",
                "nome": "Outra Pessoa",
                "documento": "TESTE-001",
                "grupo": "6º A",
                "turno": "Manhã",
                "contatoNome": "Responsável",
                "contatoTelefone": "48988888888",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)

    def test_status_update_rejects_unknown_person(self):
        response = self.client.patch(
            "/api/people/999999/status/",
            data=json.dumps({"status": "ativo"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
