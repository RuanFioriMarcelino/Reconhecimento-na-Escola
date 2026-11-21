import base64
import hashlib
import hmac
import os

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings


def _decode_master_key(raw_value: str) -> bytes:
    value = (raw_value or "").strip()
    if not value:
        if not settings.DEBUG:
            raise RuntimeError("BIOMETRIC_MASTER_KEY é obrigatória em produção.")
        return hashlib.sha256(f"dev-biometric:{settings.SECRET_KEY}".encode("utf-8")).digest()

    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if len(decoded) >= 32:
            return decoded[:32]
    except Exception:
        pass

    try:
        decoded = base64.b64decode(value)
        if len(decoded) >= 32:
            return decoded[:32]
    except Exception:
        pass

    if len(value.encode("utf-8")) >= 32:
        return hashlib.sha256(value.encode("utf-8")).digest()

    raise RuntimeError("BIOMETRIC_MASTER_KEY inválida: forneça uma chave base64 de 32 bytes.")


def _get_master_key_for_id(key_id: str) -> bytes:
    current_id = getattr(settings, "BIOMETRIC_KEY_ID", "k1")
    if key_id == current_id:
        return _decode_master_key(getattr(settings, "BIOMETRIC_MASTER_KEY", ""))

    previous = getattr(settings, "BIOMETRIC_PREVIOUS_KEYS", {}) or {}
    if key_id in previous:
        return _decode_master_key(previous[key_id])

    raise ValueError(f"Chave criptográfica '{key_id}' não configurada.")


def _derive_subkey(master_key: bytes, purpose: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"reconhece-escola-v2",
        info=purpose.encode("utf-8"),
    )
    return hkdf.derive(master_key)


def encrypt_bytes(plaintext: bytes, aad: bytes = b"", purpose: str = "biometrics") -> tuple[bytes, str]:
    """Criptografa bytes com AES-256-GCM e AAD, retornando (nonce+ciphertext_tag, key_id)."""
    key_id = getattr(settings, "BIOMETRIC_KEY_ID", "k1")
    master = _get_master_key_for_id(key_id)
    subkey = _derive_subkey(master, purpose)
    nonce = os.urandom(12)
    ciphertext = AESGCM(subkey).encrypt(nonce, plaintext, aad)
    return nonce + ciphertext, key_id


def decrypt_bytes(blob: bytes, key_id: str, aad: bytes = b"", purpose: str = "biometrics") -> bytes:
    """Descriptografa blob AES-256-GCM validando AAD e key_id."""
    if not blob or len(blob) <= 12:
        raise ValueError("Dados criptografados inválidos.")
    master = _get_master_key_for_id(key_id)
    subkey = _derive_subkey(master, purpose)
    nonce, ciphertext = blob[:12], blob[12:]
    return AESGCM(subkey).decrypt(nonce, ciphertext, aad)


def encrypt_vector(vec: np.ndarray, owner_type: str, owner_id: int) -> tuple[bytes, str]:
    """Normaliza vetor biométrico 128-d float32 e criptografa com AAD vinculada ao dono."""
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    if arr.shape[0] != 128 or not np.all(np.isfinite(arr)):
        raise ValueError("Vetor biométrico deve possuir exatamente 128 dimensões numéricas válidas.")
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-8:
        raise ValueError("Vetor biométrico degenerado (norma zero).")
    arr = (arr / norm).astype(np.float32)
    aad = f"{owner_type}:{owner_id}".encode("utf-8")
    return encrypt_bytes(arr.tobytes(), aad=aad, purpose="biometrics")


def decrypt_vector(blob: bytes, key_id: str, owner_type: str, owner_id: int) -> np.ndarray:
    """Descriptografa vetor biométrico 128-d garantindo vínculo com o mesmo owner_type/owner_id."""
    aad = f"{owner_type}:{owner_id}".encode("utf-8")
    raw = decrypt_bytes(bytes(blob), key_id=key_id, aad=aad, purpose="biometrics")
    arr = np.frombuffer(raw, dtype=np.float32).copy()
    if arr.shape[0] != 128:
        raise ValueError("Dimensão de vetor biométrico inválida após descriptografia.")
    return arr


def encrypt_text(text: str, aad: bytes = b"") -> tuple[bytes, str]:
    return encrypt_bytes((text or "").encode("utf-8"), aad=aad, purpose="pii")


def decrypt_text(blob: bytes, key_id: str, aad: bytes = b"") -> str:
    return decrypt_bytes(bytes(blob), key_id=key_id, aad=aad, purpose="pii").decode("utf-8")


def blind_index(value: str, purpose: str = "cpf") -> bytes:
    """Gera índice cego determinístico via HMAC-SHA256 para busca/unicidade sem texto claro."""
    key_id = getattr(settings, "BIOMETRIC_KEY_ID", "k1")
    master = _get_master_key_for_id(key_id)
    subkey = _derive_subkey(master, f"blind_index:{purpose}")
    normalized = (value or "").strip().lower().encode("utf-8")
    return hmac.new(subkey, normalized, hashlib.sha256).digest()
