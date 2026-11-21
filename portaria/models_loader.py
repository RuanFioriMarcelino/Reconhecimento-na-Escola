from pathlib import Path

import cv2
import requests

YUNET_NAME = "face_detection_yunet_2023mar.onnx"
SFACE_NAME = "face_recognition_sface_2021dec.onnx"

MODEL_URLS = {
    YUNET_NAME: f"https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/{YUNET_NAME}",
    SFACE_NAME: f"https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/{SFACE_NAME}",
}


def ensure_models(models_dir: Path) -> tuple[Path, Path]:
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, url in MODEL_URLS.items():
        target = models_dir / name
        if not target.exists() or target.stat().st_size < 10_000:
            print(f"[*] Baixando modelo {name}...")
            resp = requests.get(url, allow_redirects=True, timeout=60)
            resp.raise_for_status()
            target.write_bytes(resp.content)
            print(f"[OK] {name} salvo ({len(resp.content)} bytes).")
    return models_dir / YUNET_NAME, models_dir / SFACE_NAME


def create_face_models(models_dir: Path, score_threshold: float = 0.78):
    yunet_path, sface_path = ensure_models(models_dir)
    detector = cv2.FaceDetectorYN.create(
        str(yunet_path), "", (320, 320), score_threshold=score_threshold, nms_threshold=0.3
    )
    recognizer = cv2.FaceRecognizerSF.create(str(sface_path), "")
    return detector, recognizer
