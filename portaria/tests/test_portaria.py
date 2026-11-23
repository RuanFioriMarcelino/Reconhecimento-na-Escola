import base64
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import requests

from portaria.config import _parse_source, load_config
from portaria.engine import RecognitionWorker
from portaria.hud import HudRenderer, _ascii
from portaria.sync_client import SyncClient
from portaria.tracker import FaceTracker, TrackedFace


class ConfigTests(unittest.TestCase):
    def test_parse_source_digit_and_rtsp(self):
        self.assertEqual(_parse_source("0"), 0)
        self.assertEqual(_parse_source("2"), 2)
        self.assertEqual(_parse_source("rtsp://192.168.0.10/stream1"), "rtsp://192.168.0.10/stream1")
        self.assertEqual(_parse_source(""), 0)

    def test_load_config_sanitizes_invalid_modo_and_applies_overrides(self):
        cfg = load_config(
            source_override="1",
            portal_override="Portão Sul",
            modo_override="modo_invalido",
            headless_override=True,
        )
        self.assertEqual(cfg.source, 1)
        self.assertEqual(cfg.portal, "Portão Sul")
        self.assertEqual(cfg.modo, "auto")
        self.assertTrue(cfg.headless)
        self.assertGreaterEqual(cfg.confirm_frames, 1)


class TrackerTests(unittest.TestCase):
    def test_multiface_tracking_persistence_and_expiration(self):
        tracker = FaceTracker(max_lost_seconds=0.9)

        # Frame 1: dois rostos distintos
        t1 = tracker.update(
            [
                ((100, 100, 120, 120), "rawA", 0.95),
                ((400, 120, 110, 110), "rawB", 0.91),
            ],
            now=10.0,
        )
        self.assertEqual(len(t1), 2)
        id_a, id_b = t1[0].track_id, t1[1].track_id
        self.assertNotEqual(id_a, id_b)

        # Frame 2 (pequeno deslocamento): deve manter os mesmos track_ids
        t2 = tracker.update(
            [
                ((108, 104, 120, 120), "rawA2", 0.96),
                ((405, 118, 110, 110), "rawB2", 0.92),
            ],
            now=10.2,
        )
        self.assertEqual([t.track_id for t in t2], [id_a, id_b])

        # Frame 2b (0.6s depois): apenas A aparece, B desaparece temporariamente
        t2b = tracker.update([((109, 105, 120, 120), "rawA2b", 0.96)], now=10.8)
        self.assertEqual([t.track_id for t in t2b], [id_a])

        # Frame 3 após expiração de B (> 0.9s sem B, mas A ainda ativo): A mantém ID, novo rosto recebe novo ID
        t3 = tracker.update(
            [
                ((110, 105, 120, 120), "rawA3", 0.95),
                ((405, 118, 110, 110), "rawC", 0.90),
            ],
            now=11.3,
        )
        self.assertEqual(t3[0].track_id, id_a)
        self.assertNotEqual(t3[1].track_id, id_b)

    def test_needs_embedding_throttles_cpu(self):
        tr = TrackedFace(track_id=1, bbox=(0, 0, 100, 100), raw_face=None, score=0.95, last_embed_time=10.0)
        self.assertFalse(tr.needs_embedding(10.1))
        self.assertTrue(tr.needs_embedding(10.3))

        tr.matched_uid = "aluno-1"
        self.assertFalse(tr.needs_embedding(11.0, revalidate_interval=2.0))
        self.assertTrue(tr.needs_embedding(12.1, revalidate_interval=2.0))


class EngineVectorMatchingAndFlowTests(unittest.TestCase):
    def _build_worker(self):
        cfg = load_config(modo_override="auto", portal_override="Portaria principal", headless_override=True)
        cfg.confirm_frames = 2
        cfg.cooldown_seconds = 45
        cfg.unknown_seconds = 2.0
        cfg.cosine_threshold = 0.38
        cfg.margin_threshold = 0.04

        cam = MagicMock()
        sync = MagicMock()
        det = MagicMock()
        rec = MagicMock()
        with patch("portaria.engine.create_face_models", return_value=(det, rec)):
            worker = RecognitionWorker(cfg, cam, sync)
        return worker, sync, rec

    def test_vectorized_matching_500_gallery_fast_and_margin_rejection(self):
        worker, _, _ = self._build_worker()
        rng = np.random.default_rng(42)
        entries = []
        for i in range(500):
            v = rng.normal(size=128).astype(np.float32)
            v /= np.linalg.norm(v)
            entries.append({
                "uid": f"aluno-{i}",
                "id": i,
                "tipo": "aluno",
                "nome": f"Aluno {i}",
                "grupo": "6º A",
                "turno": "Manhã",
                "vector": v,
            })
        worker.update_gallery(entries)

        query = entries[123]["vector"].copy()
        t0 = time.perf_counter()
        matched, score = worker.match_vector(query)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.assertIsNotNone(matched)
        self.assertEqual(matched["uid"], "aluno-123")
        self.assertGreater(score, 0.999)
        self.assertLess(elapsed_ms, 50.0)

        # Vetor ambíguo (média exata entre dois candidatos) -> rejeitado por margem
        v_a = np.zeros(128, dtype=np.float32)
        v_a[0] = 1.0
        v_b = np.zeros(128, dtype=np.float32)
        v_b[1] = 1.0
        worker.update_gallery([
            {"uid": "aluno-1", "id": 1, "tipo": "aluno", "nome": "A", "grupo": "6º A", "turno": "Manhã", "vector": v_a},
            {"uid": "aluno-2", "id": 2, "tipo": "aluno", "nome": "B", "grupo": "6º A", "turno": "Manhã", "vector": v_b},
        ])
        ambiguous = (v_a + v_b) / np.linalg.norm(v_a + v_b)
        m_amb, _ = worker.match_vector(ambiguous)
        self.assertIsNone(m_amb)

    def test_multiframe_confirmation_cooldown_and_persistent_unknown(self):
        worker, sync, rec = self._build_worker()
        v_target = np.zeros(128, dtype=np.float32)
        v_target[0] = 1.0
        v_unknown = np.zeros(128, dtype=np.float32)
        v_unknown[5] = 1.0

        worker.update_gallery([
            {"uid": "aluno-7", "id": 7, "tipo": "aluno", "nome": "Ana Clara", "grupo": "6º A", "turno": "Manhã", "vector": v_target}
        ])
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        rec.alignCrop.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        rec.feature.return_value = v_target.reshape(1, 128)

        tr = TrackedFace(track_id=1, bbox=(50, 50, 120, 120), raw_face=np.zeros(15, dtype=np.float32), score=0.95, first_seen_time=100.0)
        # 1a confirmação -> ainda não envia (confirm_frames=2)
        worker._process_track(frame, tr, now=100.5)
        self.assertEqual(tr.confirm_count, 1)
        sync.enqueue_event.assert_not_called()

        # 2a confirmação -> confirma e enfileira evento
        worker._process_track(frame, tr, now=101.0)
        self.assertEqual(tr.matched_uid, "aluno-7")
        self.assertTrue(tr.event_sent)
        sync.enqueue_event.assert_called_once()

        # Novo track da mesma pessoa 5s depois -> bloqueado por cooldown local (45s)
        tr2 = TrackedFace(track_id=2, bbox=(50, 50, 120, 120), raw_face=np.zeros(15, dtype=np.float32), score=0.95, first_seen_time=105.0)
        worker._process_track(frame, tr2, now=105.5)
        worker._process_track(frame, tr2, now=106.0)
        self.assertEqual(sync.enqueue_event.call_count, 1)

        # Rosto desconhecido persistente por >= 2s -> enfileira evento com person_uid=None
        rec.feature.return_value = v_unknown.reshape(1, 128)
        tr_unk = TrackedFace(track_id=3, bbox=(200, 50, 120, 120), raw_face=np.zeros(15, dtype=np.float32), score=0.95, first_seen_time=200.0)
        worker._process_track(frame, tr_unk, now=202.5)
        self.assertEqual(sync.enqueue_event.call_count, 2)
        self.assertIsNone(sync.enqueue_event.call_args[0][0])

    def test_update_config_updates_runtime_thresholds(self):
        worker, _, _ = self._build_worker()
        worker.update_config({
            "settings": {"cooldownSegundos": 90, "limiarConfianca": 0.42},
            "dispositivo": {"portal": "Portão Lateral"},
        })
        self.assertEqual(worker.config.cooldown_seconds, 90)
        self.assertAlmostEqual(worker.config.cosine_threshold, 0.42, places=3)
        self.assertEqual(worker.config.portal, "Portão Lateral")


class SyncClientOfflineSpoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_spool.db"
        self.gallery_cb = MagicMock()
        self.config_cb = MagicMock()
        self.client = SyncClient(
            api_url="http://localhost:8000/api",
            device_key="port_test_key",
            spool_db_path=self.db_path,
            on_gallery_updated=self.gallery_cb,
            on_config_updated=self.config_cb,
        )

    def tearDown(self):
        self.client.stop()
        self.tmp.cleanup()

    def test_offline_queue_persists_on_error_and_flushes_on_recovery(self):
        ev_id = self.client.enqueue_event("aluno-1", "auto", "Portaria principal", 0.72)
        self.assertTrue(len(ev_id) > 0)
        self.assertEqual(self.client.pending_count, 1)

        # Falha de rede mantém evento salvo no SQLite WAL
        self.client._running = True
        with patch.object(self.client._session, "post", side_effect=requests.ConnectionError("offline")):
            self.client._flush_events()
        self.assertFalse(self.client.api_online)
        self.assertEqual(self.client.pending_count, 1)

        # Servidor volta com 201 -> fila limpa e aviso propagado
        ok_resp = MagicMock(ok=True, status_code=201)
        ok_resp.json.return_value = {
            "processed": 1,
            "results": [{"notice": "Entrada registrada: Ana Clara", "noticeLevel": "ok", "deduplicated": False}],
        }
        with patch.object(self.client._session, "post", return_value=ok_resp):
            self.client._flush_events()
        self.assertTrue(self.client.api_online)
        self.assertEqual(self.client.pending_count, 0)
        notices = self.client.get_recent_notices()
        self.assertEqual(len(notices), 1)
        self.assertIn("Ana Clara", notices[0]["text"])

    def test_gallery_sync_decodes_vectors_and_respects_unchanged(self):
        vec = np.linspace(0.1, 1.0, 128, dtype=np.float32)
        vec_b64 = base64.b64encode(vec.tobytes()).decode("ascii")

        resp1 = MagicMock(ok=True, status_code=200)
        resp1.json.return_value = {
            "version": "abc123",
            "unchanged": False,
            "total": 1,
            "entries": [{
                "uid": "aluno-1",
                "id": 1,
                "tipo": "aluno",
                "nome": "João Silva",
                "grupo": "6º A",
                "turno": "Manhã",
                "vector_b64": vec_b64,
            }],
        }
        with patch.object(self.client._session, "get", return_value=resp1):
            self.client._sync_gallery()

        self.assertTrue(self.client.api_online)
        self.assertEqual(self.client.gallery_version, "abc123")
        self.assertEqual(self.client.enrolled_count, 1)
        self.gallery_cb.assert_called_once()
        decoded_vec = self.gallery_cb.call_args[0][0][0]["vector"]
        self.assertAlmostEqual(float(np.linalg.norm(decoded_vec)), 1.0, places=5)

        # Segunda chamada com unchanged=True não dispara callback novamente
        resp2 = MagicMock(ok=True, status_code=200)
        resp2.json.return_value = {"version": "abc123", "unchanged": True, "total": 1}
        with patch.object(self.client._session, "get", return_value=resp2):
            self.client._sync_gallery()
        self.assertEqual(self.gallery_cb.call_count, 1)

    def test_config_sync_handles_401_gracefully(self):
        resp_401 = MagicMock(ok=False, status_code=401)
        with patch.object(self.client._session, "get", return_value=resp_401):
            self.client._sync_config()
        self.assertFalse(self.client.api_online)
        self.config_cb.assert_not_called()


class HudRendererTests(unittest.TestCase):
    def test_ascii_normalization_and_hud_render_online_and_offline(self):
        self.assertEqual(_ascii("João Conceição — Saída 6º A"), "Joao Conceicao — Saida 6o A")

        renderer = HudRenderer()
        cfg = load_config(portal_override="Portaria Principal — Entrada", modo_override="auto", headless_override=True)
        sync = MagicMock()
        sync.api_online = True
        sync.pending_count = 0
        sync.enrolled_count = 18
        sync.get_recent_notices.return_value = [
            {"text": "Entrada registrada: João Conceição", "level": "ok"},
            {"text": "Aviso: Saída antecipada (Maria Eduarda)", "level": "warn"},
        ]

        tracks = [
            {
                "track_id": 1,
                "bbox": (80, 90, 140, 140),
                "matched_person": {"nome": "João Conceição", "grupo": "6º A", "turno": "Manhã"},
                "confidence": 0.68,
                "event_sent": True,
            },
            {
                "track_id": 2,
                "bbox": (300, 100, 130, 130),
                "matched_person": None,
                "confidence": 0.15,
                "event_sent": False,
            },
        ]

        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        out = renderer.render(frame, tracks, cfg, sync, fps=30.0, ai_ms=15.4)
        self.assertEqual(out.shape, (540, 960, 3))
        self.assertGreater(int(out.sum()), 0)

        sync.api_online = False
        sync.pending_count = 3
        out_off = renderer.render(np.zeros((540, 960, 3), dtype=np.uint8), [], cfg, sync, fps=28.0, ai_ms=10.0)
        self.assertEqual(out_off.shape, (540, 960, 3))


if __name__ == "__main__":
    unittest.main()
