import sys
import threading
import time

import cv2


class CameraStream:
    """Captura dedicada em thread separada para zero acúmulo de buffer e máximo FPS."""

    def __init__(self, source: int | str = 0, width: int = 960, height: int = 540, mirror: bool = True):
        self.source = source
        self.width = width
        self.height = height
        self.mirror = mirror and isinstance(source, int)
        self.is_file = isinstance(source, str) and not source.lower().startswith(("rtsp://", "http://", "https://"))

        self._cap = None
        self._lock = threading.Lock()
        self._frame = None
        self._frame_seq = 0
        self._running = False
        self._thread = None
        self.connected = False
        self.fps = 0.0
        self.eof = False

    def _open_capture(self):
        if isinstance(self.source, int) and sys.platform.startswith("win"):
            cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(self.source)
        else:
            cap = cv2.VideoCapture(self.source)

        if cap.isOpened():
            if not self.is_file:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 30)
            return cap
        cap.release()
        return None

    def start(self) -> bool:
        self._cap = self._open_capture()
        if self._cap is None:
            return False

        ret, frame = self._cap.read()
        if not ret or frame is None:
            self._cap.release()
            self._cap = None
            return False

        if self.mirror:
            frame = cv2.flip(frame, 1)

        with self._lock:
            self._frame = frame
            self._frame_seq = 1
        self.connected = True
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, name="CameraStream", daemon=True)
        self._thread.start()
        return True

    def _reader_loop(self):
        backoff = 1.0
        frames_in_sec = 0
        last_fps_ts = time.monotonic()

        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self.connected = False
                if self.is_file:
                    self.eof = True
                    break
                time.sleep(backoff)
                backoff = min(10.0, backoff * 1.8)
                self._cap = self._open_capture()
                continue

            ret, frame = self._cap.read()
            if not ret or frame is None:
                if self.is_file:
                    self.eof = True
                    self.connected = False
                    break
                self.connected = False
                self._cap.release()
                self._cap = None
                continue

            backoff = 1.0
            self.connected = True
            if self.mirror:
                frame = cv2.flip(frame, 1)

            with self._lock:
                self._frame = frame
                self._frame_seq += 1

            frames_in_sec += 1
            now = time.monotonic()
            if now - last_fps_ts >= 1.0:
                self.fps = frames_in_sec / (now - last_fps_ts)
                frames_in_sec = 0
                last_fps_ts = now

            if self.is_file:
                time.sleep(0.03)

    def read(self):
        with self._lock:
            if self._frame is None:
                return None, 0
            return self._frame.copy(), self._frame_seq

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self.connected = False
