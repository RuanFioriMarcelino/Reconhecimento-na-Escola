import base64
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone

import numpy as np
import requests


class SyncClient:
    """Cliente resiliente de sincronização em background com fila offline SQLite WAL e hot-reload em RAM."""

    def __init__(self, api_url: str, device_key: str, spool_db_path, on_gallery_updated=None, on_config_updated=None):
        self.api_url = api_url.rstrip("/")
        self.device_key = device_key
        self.spool_db_path = str(spool_db_path)
        self.on_gallery_updated = on_gallery_updated
        self.on_config_updated = on_config_updated

        self._session = requests.Session()
        if self.device_key:
            self._session.headers.update({"X-Portaria-Key": self.device_key})

        self._db_lock = threading.Lock()
        self._conn = sqlite3.connect(self.spool_db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_event_id TEXT UNIQUE NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

        self._wake_event = threading.Event()
        self._force_gallery = threading.Event()
        self._running = False
        self._thread = None

        self.api_online = False
        self.gallery_version = ""
        self.enrolled_count = 0
        self.sample_people: list[dict] = []
        self.pending_count = self._count_pending()

        self._notices_lock = threading.Lock()
        self._recent_notices: list[dict] = []
        self._telemetry_provider = None

    def set_telemetry_provider(self, fn):
        self._telemetry_provider = fn

    def _count_pending(self) -> int:
        with self._db_lock:
            row = self._conn.execute("SELECT COUNT(*) FROM pending_events").fetchone()
            return int(row[0]) if row else 0

    def push_notice(self, text: str, level: str = "ok"):
        if not text:
            return
        with self._notices_lock:
            now = time.monotonic()
            self._recent_notices.append({"text": text, "level": level, "ts": now})
            self._recent_notices = [n for n in self._recent_notices if (now - n["ts"]) < 6.0][-4:]

    def get_recent_notices(self) -> list[dict]:
        with self._notices_lock:
            now = time.monotonic()
            self._recent_notices = [n for n in self._recent_notices if (now - n["ts"]) < 5.5]
            return list(self._recent_notices)

    def enqueue_event(self, person_uid: str | None, tipo: str, portal: str, confianca: float | None) -> str:
        event_id = uuid.uuid4().hex
        payload = {
            "clientEventId": event_id,
            "personRef": person_uid,
            "tipo": tipo,
            "portal": portal,
            "confianca": round(float(confianca), 4) if confianca is not None else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._db_lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO pending_events (client_event_id, payload_json, created_at) VALUES (?, ?, ?)",
                (event_id, json.dumps(payload), time.time()),
            )
            self._conn.commit()
        self.pending_count = self._count_pending()
        self._wake_event.set()
        return event_id

    def force_gallery_sync(self):
        self._force_gallery.set()
        self._wake_event.set()

    def start(self):
        self._running = True
        self._sync_config()
        self._sync_gallery()
        self._thread = threading.Thread(target=self._loop, name="SyncWorker", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._wake_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        with self._db_lock:
            self._conn.close()

    def _sync_config(self):
        if not self.device_key:
            return
        try:
            resp = self._session.get(f"{self.api_url}/portaria/config/", timeout=4)
            if resp.ok:
                self.api_online = True
                payload = resp.json()
                self.sample_people = payload.get("samplePeople", [])
                if self.on_config_updated:
                    self.on_config_updated(payload)
            elif resp.status_code == 401:
                print("[!] X-Portaria-Key inválida ou dispositivo desativado no servidor.")
                self.api_online = False
        except Exception:
            self.api_online = False

    def _sync_gallery(self):
        if not self.device_key:
            return
        try:
            params = {"version": self.gallery_version} if self.gallery_version else {}
            resp = self._session.get(f"{self.api_url}/portaria/biometrics/", params=params, timeout=6)
            if not resp.ok:
                self.api_online = False
                return
            self.api_online = True
            data = resp.json()
            if data.get("unchanged"):
                return

            entries = data.get("entries", [])
            decoded = []
            for item in entries:
                vec_raw = base64.b64decode(item["vector_b64"])
                vec = np.frombuffer(vec_raw, dtype=np.float32).copy()
                if vec.shape[0] != 128:
                    continue
                norm = float(np.linalg.norm(vec))
                if norm > 1e-8:
                    vec /= norm
                decoded.append({
                    "uid": item["uid"],
                    "id": item["id"],
                    "tipo": item["tipo"],
                    "nome": item["nome"],
                    "grupo": item.get("grupo", ""),
                    "turno": item.get("turno", ""),
                    "vector": vec,
                })

            self.gallery_version = data.get("version", "")
            self.enrolled_count = len(decoded)
            if self.on_gallery_updated:
                self.on_gallery_updated(decoded)
            print(f"[SYNC] Galeria biométrica em RAM atualizada: {self.enrolled_count} pessoa(s) ativa(s).")
        except Exception:
            self.api_online = False

    def _flush_events(self):
        if not self.device_key:
            return
        while self._running:
            with self._db_lock:
                rows = self._conn.execute(
                    "SELECT id, payload_json FROM pending_events ORDER BY id ASC LIMIT 25"
                ).fetchall()
            if not rows:
                self.pending_count = 0
                return

            row_ids = [r[0] for r in rows]
            events = [json.loads(r[1]) for r in rows]
            try:
                resp = self._session.post(
                    f"{self.api_url}/portaria/events/",
                    json={"events": events},
                    timeout=5,
                )
                if resp.ok:
                    self.api_online = True
                    data = resp.json()
                    for res in data.get("results", []):
                        if res.get("notice") and not res.get("deduplicated"):
                            self.push_notice(res["notice"], res.get("noticeLevel", "ok"))
                    with self._db_lock:
                        placeholders = ",".join("?" for _ in row_ids)
                        self._conn.execute(f"DELETE FROM pending_events WHERE id IN ({placeholders})", row_ids)
                        self._conn.commit()
                    self.pending_count = self._count_pending()
                else:
                    self.api_online = False
                    break
            except Exception:
                self.api_online = False
                break

    def _send_heartbeat(self):
        if not self.device_key:
            return
        telemetry = self._telemetry_provider() if self._telemetry_provider else {}
        telemetry["enrolledCount"] = self.enrolled_count
        telemetry["pendingQueue"] = self.pending_count
        try:
            resp = self._session.post(f"{self.api_url}/portaria/heartbeat/", json=telemetry, timeout=3)
            self.api_online = resp.ok
        except Exception:
            self.api_online = False

    def _loop(self):
        last_gallery = time.monotonic()
        last_heartbeat = 0.0

        while self._running:
            self._flush_events()
            now = time.monotonic()

            if self._force_gallery.is_set() or (now - last_gallery) >= 30.0:
                self._force_gallery.clear()
                self._sync_gallery()
                last_gallery = now

            if (now - last_heartbeat) >= 20.0:
                self._send_heartbeat()
                last_heartbeat = now

            self._wake_event.wait(timeout=1.5)
            self._wake_event.clear()
