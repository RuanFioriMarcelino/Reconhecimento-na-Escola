from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from django.test import TestCase
from django.utils import timezone

from ..models import (
    Alerta,
    Aluno,
    ConfiguracaoEscola,
    DadoBiometrico,
    Funcionario,
    RegistroAcesso,
    Turma,
    Turno,
)
from ..services.access_service import processar_passagem
from ..services.biometrics import (
    BiometricValidationError,
    enroll_person_biometrics,
    extract_biometric_template,
    get_active_gallery,
)


def _encode_jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def _sharp_checkerboard(w=240, h=240) -> bytes:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            if ((x // 8) + (y // 8)) % 2 == 0:
                img[y : y + 8, x : x + 8] = 240
    return _encode_jpeg(img)


class AccessServiceUnitTests(TestCase):
    def setUp(self):
        self.cfg = ConfiguracaoEscola.objects.create(
            nome_escola="Escola Service Test",
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
        self.turno_tarde = Turno.objects.create(
            nome="Tarde",
            inicio=time(13, 0),
            limite_entrada=time(13, 20),
            termino=time(17, 45),
            limite_saida_antecipada=time(17, 30),
        )
        self.turma_manha = Turma.objects.create(nome="6º A", turno=self.turno_manha, ano_letivo=2026)
        self.turma_tarde = Turma.objects.create(nome="9º A", turno=self.turno_tarde, ano_letivo=2026)

        self.aluno = Aluno.objects.create(
            nome="Lucas Serviço",
            documento="SRV-001",
            turma="6º A",
            turno="Manhã",
            turma_ref=self.turma_manha,
            turno_ref=self.turno_manha,
            contato_nome="Mãe",
            contato_telefone="48999990000",
        )
        self.aluno_tarde = Aluno.objects.create(
            nome="Helena Tarde",
            documento="SRV-002",
            turma="9º A",
            turno="Tarde",
            turma_ref=self.turma_tarde,
            turno_ref=self.turno_tarde,
            contato_nome="Pai",
            contato_telefone="48999991111",
        )
        self.func = Funcionario.objects.create(
            nome="Prof. Ricardo",
            documento="FUNC-SRV-1",
            cargo="Professor",
            turno="Manhã",
            turno_ref=self.turno_manha,
            contato_nome="Emergência",
            contato_telefone="48999992222",
        )

    def _today_dt(self, hour: int, minute: int, second: int = 0):
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        return timezone.make_aware(timezone.datetime.combine(today, time(hour, minute, second)), tz)

    def test_late_entry_tarde_generates_media_alert(self):
        res = processar_passagem(
            person=self.aluno_tarde,
            person_tipo="aluno",
            tipo_solicitado="auto",
            data_hora=self._today_dt(13, 35),
            confianca=0.62,
        )
        self.assertEqual(res["tipo"], "entrada")
        self.assertEqual(res["status"], "atraso")
        self.assertTrue(res["incidente"])
        alerta = Alerta.objects.get(registro_acesso_id=res["id"])
        self.assertEqual(alerta.tipo, "Atraso na entrada")
        self.assertEqual(alerta.severidade, "media")

    def test_dwell_cooldown_prevents_instant_exit(self):
        dt_in = self._today_dt(7, 10, 0)
        r1 = processar_passagem(person=self.aluno, person_tipo="aluno", tipo_solicitado="auto", data_hora=dt_in)
        self.assertEqual(r1["tipo"], "entrada")

        # 60s depois: passou cooldown (45s), mas ainda dentro de tempo_minimo_permanencia_min (2 min = 120s)
        r2 = processar_passagem(
            person=self.aluno,
            person_tipo="aluno",
            tipo_solicitado="auto",
            data_hora=dt_in + timedelta(seconds=60),
        )
        self.assertTrue(r2["ignored"])
        self.assertEqual(r2["reason"], "dwell_cooldown")

        # 5 horas depois (12:10, após saída normal 11:30) -> saída reconhecida sem incidente
        r3 = processar_passagem(
            person=self.aluno,
            person_tipo="aluno",
            tipo_solicitado="auto",
            data_hora=self._today_dt(12, 10),
        )
        self.assertFalse(r3["ignored"])
        self.assertEqual(r3["tipo"], "saida")
        self.assertEqual(r3["status"], "reconhecido")
        self.assertFalse(r3["incidente"])

    def test_staff_early_exit_does_not_trigger_student_early_exit_alert(self):
        processar_passagem(person=self.func, person_tipo="funcionario", tipo_solicitado="auto", data_hora=self._today_dt(7, 5))
        res_out = processar_passagem(
            person=self.func,
            person_tipo="funcionario",
            tipo_solicitado="auto",
            data_hora=self._today_dt(10, 0),
        )
        self.assertEqual(res_out["tipo"], "saida")
        self.assertEqual(res_out["status"], "reconhecido")
        self.assertFalse(res_out["incidente"])
        self.assertFalse(Alerta.objects.filter(tipo="Saída antecipada").exists())

    def test_inactive_person_still_logged_passively_with_high_alert(self):
        self.aluno.status = "inativo"
        self.aluno.save(update_fields=["status"])
        res = processar_passagem(
            person=self.aluno,
            person_tipo="aluno",
            tipo_solicitado="auto",
            data_hora=self._today_dt(7, 15),
        )
        self.assertFalse(res["ignored"])
        self.assertTrue(res["incidente"])
        self.assertIn("inativo", res["notice"].lower())
        self.assertTrue(Alerta.objects.filter(tipo="Cadastro inativo na portaria", severidade="alta").exists())

    def test_unknown_person_20s_cooldown_and_invalid_tipo(self):
        dt = self._today_dt(8, 0, 0)
        u1 = processar_passagem(person=None, person_tipo=None, portal="Portão A", data_hora=dt)
        self.assertFalse(u1["ignored"])
        self.assertEqual(u1["status"], "nao-reconhecido")

        u2 = processar_passagem(
            person=None,
            person_tipo=None,
            portal="Portão A",
            data_hora=dt + timedelta(seconds=10),
        )
        self.assertTrue(u2["ignored"])
        self.assertEqual(u2["reason"], "unknown_cooldown")

        with self.assertRaises(ValueError):
            processar_passagem(person=self.aluno, person_tipo="aluno", tipo_solicitado="invalido", data_hora=dt)


class BiometricsServiceUnitTests(TestCase):
    def setUp(self):
        self.aluno = Aluno.objects.create(
            nome="Biometria Teste",
            documento="BIO-UNIT-1",
            turma="6º A",
            turno="Manhã",
            contato_nome="Resp",
            contato_telefone="48999993333",
        )

    def test_empty_and_corrupt_images_raise_validation_error(self):
        with self.assertRaises(BiometricValidationError):
            extract_biometric_template([])
        with self.assertRaises(BiometricValidationError):
            extract_biometric_template([b"not-a-valid-jpeg"])

    def test_black_image_without_face_raises_validation_error(self):
        black = _encode_jpeg(np.zeros((240, 240, 3), dtype=np.uint8))
        with self.assertRaises(BiometricValidationError):
            extract_biometric_template([black])

    def test_mocked_multiframe_validation_and_enrollment_rotation(self):
        sharp_jpg = _sharp_checkerboard()
        face_row = np.array([40, 40, 120, 120, 70, 80, 130, 80, 100, 110, 75, 135, 125, 135, 0.96], dtype=np.float32)

        det_mock = MagicMock()
        det_mock.detect.return_value = (1, np.array([face_row], dtype=np.float32))

        rec_mock = MagicMock()
        rec_mock.alignCrop.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        v1 = np.linspace(0.1, 1.0, 128, dtype=np.float32)
        v2 = v1 + 0.01
        rec_mock.feature.side_effect = [v1.reshape(1, 128), v2.reshape(1, 128)]

        with patch("core.services.biometrics._get_models", return_value=(det_mock, rec_mock)):
            vec, quality, meta = extract_biometric_template([sharp_jpg, sharp_jpg])
            self.assertEqual(vec.shape, (128,))
            self.assertAlmostEqual(float(np.linalg.norm(vec)), 1.0, places=5)
            self.assertGreater(quality, 0.7)
            self.assertEqual(meta["frames"], 2)

        # Múltiplos rostos -> erro
        det_mock.detect.return_value = (2, np.array([face_row, face_row], dtype=np.float32))
        with patch("core.services.biometrics._get_models", return_value=(det_mock, rec_mock)):
            with self.assertRaises(BiometricValidationError):
                extract_biometric_template([sharp_jpg])

        # Quadros divergentes -> erro
        det_mock.detect.return_value = (1, np.array([face_row], dtype=np.float32))
        orth1 = np.zeros(128, dtype=np.float32)
        orth1[0] = 1.0
        orth2 = np.zeros(128, dtype=np.float32)
        orth2[1] = 1.0
        rec_mock.feature.side_effect = [orth1.reshape(1, 128), orth2.reshape(1, 128)]
        with patch("core.services.biometrics._get_models", return_value=(det_mock, rec_mock)):
            with self.assertRaises(BiometricValidationError):
                extract_biometric_template([sharp_jpg, sharp_jpg])

        # Cadastro substitui template antigo (ativo=False) e galeria ignora inativos
        rec_mock.feature.side_effect = [v1.reshape(1, 128), v2.reshape(1, 128)]
        with patch("core.services.biometrics._get_models", return_value=(det_mock, rec_mock)):
            bio1 = enroll_person_biometrics(self.aluno, "aluno", [sharp_jpg], usuario="tester")
            bio2 = enroll_person_biometrics(self.aluno, "aluno", [sharp_jpg], usuario="tester")

        bio1.refresh_from_db()
        self.assertFalse(bio1.ativo)
        self.assertTrue(bio2.ativo)
        self.assertEqual(DadoBiometrico.objects.filter(aluno=self.aluno, ativo=True).count(), 1)

        _, entries = get_active_gallery()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["uid"], f"aluno-{self.aluno.pk}")

        # Ao desativar aluno, sai da galeria ativa da portaria
        self.aluno.status = "inativo"
        self.aluno.save(update_fields=["status"])
        _, entries_after = get_active_gallery()
        self.assertEqual(entries_after, [])
