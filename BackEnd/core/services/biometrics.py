import base64
import hashlib
import threading
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..crypto.cipher import decrypt_vector, encrypt_vector
from ..models import DadoBiometrico
from ..security import registrar_auditoria

_MODELS_LOCK = threading.Lock()
_INFERENCE_LOCK = threading.Lock()
_DETECTOR = None
_RECOGNIZER = None

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"


class BiometricValidationError(ValueError):
    """Erro de validação de qualidade ou enquadramento da captura facial."""


def _models_dir() -> Path:
    return Path(settings.BASE_DIR).parent / "portaria" / "models"


def _ensure_models() -> tuple[Path, Path]:
    models_dir = _models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    yunet = models_dir / "face_detection_yunet_2023mar.onnx"
    sface = models_dir / "face_recognition_sface_2021dec.onnx"

    for path, url in ((yunet, YUNET_URL), (sface, SFACE_URL)):
        if not path.exists() or path.stat().st_size < 10_000:
            resp = requests.get(url, allow_redirects=True, timeout=60)
            resp.raise_for_status()
            path.write_bytes(resp.content)
    return yunet, sface


def _get_models():
    global _DETECTOR, _RECOGNIZER
    if _DETECTOR is not None and _RECOGNIZER is not None:
        return _DETECTOR, _RECOGNIZER
    with _MODELS_LOCK:
        if _DETECTOR is None or _RECOGNIZER is None:
            yunet, sface = _ensure_models()
            _DETECTOR = cv2.FaceDetectorYN.create(
                str(yunet), "", (320, 320), score_threshold=0.75, nms_threshold=0.3
            )
            _RECOGNIZER = cv2.FaceRecognizerSF.create(str(sface), "")
    return _DETECTOR, _RECOGNIZER


def _decode_and_resize(raw_bytes: bytes) -> np.ndarray:
    buf = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise BiometricValidationError("Arquivo de imagem inválido ou corrompido.")
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim > 1280:
        scale = 1280.0 / max_dim
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return image


def extract_biometric_template(image_bytes_list: list[bytes]) -> tuple[np.ndarray, float, dict]:
    """Processa 1 a N quadros em RAM e extrai um template SFace 128-d L2-normalizado e validado."""
    if not image_bytes_list:
        raise BiometricValidationError("Nenhuma imagem recebida para extração biométrica.")

    detector, recognizer = _get_models()
    vectors: list[np.ndarray] = []
    det_scores: list[float] = []
    sharp_scores: list[float] = []

    for raw in image_bytes_list:
        image = _decode_and_resize(raw)
        h, w = image.shape[:2]
        with _INFERENCE_LOCK:
            detector.setInputSize((w, h))
            _, faces = detector.detect(image)

            if faces is None or len(faces) == 0:
                raise BiometricValidationError(
                    "Nenhum rosto detectado na imagem. Posicione o rosto de frente e em local iluminado."
                )
            if len(faces) > 1:
                raise BiometricValidationError(
                    "Mais de um rosto detectado. Enquadre apenas a pessoa que está sendo cadastrada."
                )

            face = faces[0]
            bx, by, bw, bh = [int(v) for v in face[:4]]
            det_score = float(face[-1])

            if det_score < 0.80:
                raise BiometricValidationError(
                    "Confiança de detecção facial baixa. Melhore a iluminação e olhe diretamente para a câmera."
                )
            if bw < 60 or bh < 60:
                raise BiometricValidationError(
                    "Rosto muito distante da câmera. Aproxime-se um pouco mais para garantir precisão."
                )

            x1, y1 = max(0, bx), max(0, by)
            x2, y2 = min(w, bx + bw), min(h, by + bh)
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                raise BiometricValidationError("Recorte facial inválido. Tente capturar novamente.")
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if sharpness < 25.0:
                raise BiometricValidationError(
                    "Imagem desfocada ou em movimento. Mantenha o rosto parado durante a captura."
                )

            aligned = recognizer.alignCrop(image, face)
            feat = recognizer.feature(aligned).reshape(-1).astype(np.float32)

        norm = float(np.linalg.norm(feat))
        if norm <= 1e-8 or not np.all(np.isfinite(feat)):
            raise BiometricValidationError("Não foi possível extrair assinatura facial válida.")
        feat = feat / norm

        vectors.append(feat)
        det_scores.append(det_score)
        sharp_scores.append(sharpness)

    consistency = 1.0
    if len(vectors) > 1:
        base = vectors[0]
        sims = [float(np.dot(base, other)) for other in vectors[1:]]
        min_sim = min(sims)
        if min_sim < 0.45:
            raise BiometricValidationError(
                "Os quadros capturados divergem entre si. Mantenha o mesmo rosto parado durante os 3 quadros."
            )
        consistency = min(1.0, max(0.5, sum(sims) / len(sims)))

    mean_vec = np.mean(np.stack(vectors, axis=0), axis=0).astype(np.float32)
    mean_vec /= float(np.linalg.norm(mean_vec))

    avg_det = sum(det_scores) / len(det_scores)
    avg_sharp = min(1.0, (sum(sharp_scores) / len(sharp_scores)) / 180.0)
    quality = round(min(1.0, max(0.0, 0.45 * avg_det + 0.30 * avg_sharp + 0.25 * consistency)), 2)

    meta = {
        "frames": len(vectors),
        "det_score": round(avg_det, 3),
        "sharpness": round(sum(sharp_scores) / len(sharp_scores), 1),
        "consistency": round(consistency, 3),
    }
    return mean_vec, quality, meta


def enroll_person_biometrics(
    person,
    tipo: str,
    image_bytes_list: list[bytes],
    usuario: str = "",
    ip: str | None = None,
) -> DadoBiometrico:
    """Extrai, criptografa com AES-256-GCM e persiste o vetor biométrico sem gravar fotos em disco."""
    vector, quality, meta = extract_biometric_template(image_bytes_list)
    blob, key_id = encrypt_vector(vector, owner_type=tipo, owner_id=person.pk)
    owner_filter = {"aluno": person} if tipo == "aluno" else {"funcionario": person}

    with transaction.atomic():
        DadoBiometrico.objects.filter(ativo=True, **owner_filter).update(ativo=False)
        bio = DadoBiometrico.objects.create(
            algoritmo=DadoBiometrico.Algoritmo.SFACE,
            versao="2021dec",
            dimensao=128,
            qualidade=Decimal(f"{quality:.2f}"),
            vetor_enc=blob,
            key_id=key_id,
            ativo=True,
            **owner_filter,
        )
        update_fields = []
        if not person.consentimento_biometrico:
            person.consentimento_biometrico = True
            update_fields.append("consentimento_biometrico")
        if not person.consentimento_em:
            person.consentimento_em = timezone.now()
            update_fields.append("consentimento_em")
        if update_fields:
            person.save(update_fields=update_fields)

    registrar_auditoria(
        tabela="dados_biometricos",
        operacao="INSERT",
        chave=f"{tipo}:{person.pk}",
        usuario=usuario,
        ip=ip,
        detalhes={"qualidade": quality, "key_id": key_id, **meta},
        sensivel=True,
    )
    return bio


def get_active_gallery() -> tuple[str, list[dict]]:
    """Retorna (versao_hash, lista_vetores_ativos) com vetores descriptografados apenas em RAM."""
    bios = (
        DadoBiometrico.objects.filter(ativo=True)
        .select_related("aluno", "funcionario")
        .order_by("id")
    )
    entries = []
    hasher = hashlib.sha256()

    for bio in bios:
        if bio.aluno_id and bio.aluno and bio.aluno.status == "ativo":
            owner_type = "aluno"
            owner = bio.aluno
            uid = f"aluno-{owner.pk}"
        elif bio.funcionario_id and bio.funcionario and bio.funcionario.status == "ativo":
            owner_type = "funcionario"
            owner = bio.funcionario
            uid = f"funcionario-{owner.pk}"
        else:
            continue

        try:
            vec = decrypt_vector(bio.vetor_enc, bio.key_id, owner_type=owner_type, owner_id=owner.pk)
        except Exception:
            continue

        grupo = owner.turma if owner_type == "aluno" else owner.cargo
        vec_b64 = base64.b64encode(vec.astype(np.float32).tobytes()).decode("ascii")
        hasher.update(f"{bio.pk}:{uid}:{bio.criado_em.timestamp():.3f}:".encode("utf-8"))
        entries.append({
            "uid": uid,
            "id": owner.pk,
            "tipo": owner_type,
            "nome": owner.nome,
            "grupo": grupo,
            "turno": owner.turno,
            "qualidade": float(bio.qualidade),
            "vector_b64": vec_b64,
        })

    return hasher.hexdigest()[:16], entries
