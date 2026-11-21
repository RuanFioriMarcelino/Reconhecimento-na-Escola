import threading
import time

import cv2
import numpy as np

from .models_loader import create_face_models
from .tracker import FaceTracker, TrackedFace


class RecognitionWorker:
    """Thread dedicada de detecção (YuNet redimensionado) e matching vetorizado (SFace + NumPy)."""

    def __init__(self, config, camera_stream, sync_client):
        self.config = config
        self.camera = camera_stream
        self.sync = sync_client

        self.detector, self.recognizer = create_face_models(config.models_dir, score_threshold=0.78)
        self.tracker = FaceTracker(max_lost_seconds=0.9)

        self._gallery_lock = threading.Lock()
        self._gallery_meta: list[dict] = []
        self._gallery_matrix: np.ndarray | None = None

        self._tracks_lock = threading.Lock()
        self._latest_tracks: list[dict] = []
        self._local_cooldown: dict[str, float] = {}

        self._running = False
        self._thread = None
        self.last_ai_ms = 0.0

    def update_gallery(self, entries: list[dict]):
        with self._gallery_lock:
            if not entries:
                self._gallery_meta = []
                self._gallery_matrix = None
                return
            self._gallery_meta = [
                {
                    "uid": e["uid"],
                    "id": e["id"],
                    "tipo": e["tipo"],
                    "nome": e["nome"],
                    "grupo": e["grupo"],
                    "turno": e["turno"],
                }
                for e in entries
            ]
            self._gallery_matrix = np.stack([e["vector"] for e in entries], axis=0).astype(np.float32)

    def update_config(self, payload: dict):
        settings = payload.get("settings") or {}
        if "cooldownSegundos" in settings:
            self.config.cooldown_seconds = int(settings["cooldownSegundos"])
        if "limiarConfianca" in settings:
            self.config.cosine_threshold = float(settings["limiarConfianca"])
        dev = payload.get("dispositivo") or {}
        if dev.get("portal"):
            self.config.portal = dev["portal"]

    def match_vector(self, query_vec: np.ndarray) -> tuple[dict | None, float]:
        """Compara vetor L2-normalizado contra toda a galeria em < 1ms usando produto escalar matricial."""
        with self._gallery_lock:
            matrix = self._gallery_matrix
            meta = self._gallery_meta

        if matrix is None or len(meta) == 0:
            return None, 0.0

        q = query_vec.reshape(-1).astype(np.float32)
        norm = float(np.linalg.norm(q))
        if norm <= 1e-8:
            return None, 0.0
        q /= norm

        scores = matrix @ q
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        second_score = -1.0
        if len(scores) > 1:
            masked = scores.copy()
            masked[best_idx] = -1.0
            second_score = float(np.max(masked))

        margin = best_score - second_score if second_score > -0.5 else 1.0
        if best_score >= self.config.cosine_threshold and (len(scores) == 1 or margin >= self.config.margin_threshold):
            return meta[best_idx], best_score
        return None, best_score

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, name="RecognitionWorker", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def get_tracks_snapshot(self) -> list[dict]:
        with self._tracks_lock:
            return list(self._latest_tracks)

    def _can_send_local(self, key: str, now: float, cooldown: float) -> bool:
        prev = self._local_cooldown.get(key)
        if prev is not None and (now - prev) < cooldown:
            return False
        self._local_cooldown[key] = now
        return True

    def _process_track(self, frame: np.ndarray, track: TrackedFace, now: float):
        if track.needs_embedding(now, revalidate_interval=2.2):
            track.last_embed_time = now
            aligned = self.recognizer.alignCrop(frame, track.raw_face)
            feat = self.recognizer.feature(aligned).reshape(-1).astype(np.float32)
            person, score = self.match_vector(feat)

            if person is not None:
                uid = person["uid"]
                if track.pending_uid == uid:
                    track.confirm_count += 1
                else:
                    track.pending_uid = uid
                    track.confirm_count = 1
                track.confidence = score

                if track.confirm_count >= self.config.confirm_frames:
                    track.matched_uid = uid
                    track.matched_person = person
                    if not track.event_sent and self._can_send_local(uid, now, self.config.cooldown_seconds):
                        track.event_sent = True
                        self.sync.enqueue_event(uid, self.config.modo, self.config.portal, score)
                        self.sync.push_notice(f"Registrando passagem: {person['nome']}", "ok")
            else:
                if track.matched_uid is None:
                    track.confidence = max(0.0, score)

        # Rosto desconhecido persistente (aviso passivo sem bloqueio)
        if (
            track.matched_uid is None
            and (now - track.first_seen_time) >= self.config.unknown_seconds
            and (now - track.unknown_sent_time) >= 20.0
            and self._can_send_local("__unknown__", now, 20.0)
        ):
            track.unknown_sent_time = now
            self.sync.enqueue_event(None, self.config.modo, self.config.portal, None)
            self.sync.push_notice("Aviso: Pessoa nao cadastrada na portaria", "warn")

    def _worker_loop(self):
        last_seq = -1

        while self._running:
            frame, seq = self.camera.read()
            if frame is None or seq == last_seq:
                time.sleep(0.008)
                continue
            last_seq = seq

            t0 = time.perf_counter()
            orig_h, orig_w = frame.shape[:2]
            det_w = min(orig_w, self.config.detect_width)
            scale = det_w / float(orig_w)
            det_h = max(120, int(orig_h * scale))

            small = cv2.resize(frame, (det_w, det_h), interpolation=cv2.INTER_LINEAR) if scale < 0.99 else frame
            self.detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = self.detector.detect(small)

            detections = []
            if faces is not None and len(faces) > 0:
                inv_scale = 1.0 / scale if scale < 0.99 else 1.0
                for raw in faces:
                    scaled = raw.copy()
                    if inv_scale != 1.0:
                        scaled[:14] *= inv_scale
                    bx, by, bw, bh = int(scaled[0]), int(scaled[1]), int(scaled[2]), int(scaled[3])
                    score = float(scaled[-1])
                    if bw < 50 or bh < 50 or score < 0.78:
                        continue
                    detections.append(((bx, by, bw, bh), scaled, score))

            now = time.monotonic()
            tracks = self.tracker.update(detections, now=now)
            for tr in tracks:
                self._process_track(frame, tr, now)

            snapshot = [
                {
                    "track_id": tr.track_id,
                    "bbox": tr.bbox,
                    "matched_person": tr.matched_person,
                    "confidence": tr.confidence,
                    "first_seen": tr.first_seen_time,
                    "event_sent": tr.event_sent,
                }
                for tr in tracks
            ]
            with self._tracks_lock:
                self._latest_tracks = snapshot

            self.last_ai_ms = (time.perf_counter() - t0) * 1000.0
