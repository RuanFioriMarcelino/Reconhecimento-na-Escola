import base64
import os
from datetime import timedelta

import numpy as np
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from ..crypto.cipher import (
    blind_index,
    decrypt_bytes,
    decrypt_text,
    decrypt_vector,
    encrypt_bytes,
    encrypt_text,
    encrypt_vector,
)
from ..crypto.fields import clean_str, mask_cpf, mask_phone, normalize_digits
from ..models import AuthToken, PerfilUsuario
from ..security import (
    check_login_rate_limit,
    clear_login_failures,
    generate_secret,
    hash_secret,
    issue_auth_token,
    record_login_failure,
)


class CryptoUnitTests(SimpleTestCase):
    def test_encrypt_decrypt_vector_roundtrip_and_normalization(self):
        vec = np.linspace(0.5, 2.5, 128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=42)
        recovered = decrypt_vector(blob, key_id=key_id, owner_type="aluno", owner_id=42)

        self.assertEqual(recovered.shape, (128,))
        self.assertAlmostEqual(float(np.linalg.norm(recovered)), 1.0, places=5)
        expected = vec / np.linalg.norm(vec)
        self.assertGreater(float(np.dot(recovered, expected)), 0.99999)

    def test_vector_validation_rejects_bad_dimension_zero_and_nan(self):
        with self.assertRaises(ValueError):
            encrypt_vector(np.ones(64, dtype=np.float32), "aluno", 1)
        with self.assertRaises(ValueError):
            encrypt_vector(np.zeros(128, dtype=np.float32), "aluno", 1)
        bad = np.ones(128, dtype=np.float32)
        bad[0] = np.nan
        with self.assertRaises(ValueError):
            encrypt_vector(bad, "aluno", 1)

    def test_aad_tampering_and_corrupted_ciphertext_fail(self):
        vec = np.ones(128, dtype=np.float32)
        blob, key_id = encrypt_vector(vec, owner_type="aluno", owner_id=10)

        with self.assertRaises(Exception):
            decrypt_vector(blob, key_id=key_id, owner_type="aluno", owner_id=11)
        with self.assertRaises(Exception):
            decrypt_vector(blob, key_id=key_id, owner_type="funcionario", owner_id=10)

        tampered = bytearray(blob)
        tampered[-1] ^= 0xFF
        with self.assertRaises(Exception):
            decrypt_vector(bytes(tampered), key_id=key_id, owner_type="aluno", owner_id=10)

        with self.assertRaises(ValueError):
            decrypt_bytes(b"short", key_id=key_id)

    def test_text_encryption_and_key_rotation(self):
        old_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        new_key = base64.urlsafe_b64encode(os.urandom(32)).decode()

        with override_settings(BIOMETRIC_MASTER_KEY=old_key, BIOMETRIC_KEY_ID="k0"):
            blob, kid = encrypt_text("12345678900", aad=b"resp:1")
            self.assertEqual(kid, "k0")

        with override_settings(
            BIOMETRIC_MASTER_KEY=new_key,
            BIOMETRIC_KEY_ID="k1",
            BIOMETRIC_PREVIOUS_KEYS={"k0": old_key},
        ):
            self.assertEqual(decrypt_text(blob, kid, aad=b"resp:1"), "12345678900")
            new_blob, new_kid = encrypt_text("novo-valor")
            self.assertEqual(new_kid, "k1")
            self.assertEqual(decrypt_text(new_blob, new_kid), "novo-valor")

        with override_settings(
            BIOMETRIC_MASTER_KEY=new_key,
            BIOMETRIC_KEY_ID="k1",
            BIOMETRIC_PREVIOUS_KEYS={},
        ):
            with self.assertRaises(ValueError):
                decrypt_text(blob, "k0", aad=b"resp:1")

    def test_blind_index_is_deterministic_and_purpose_scoped(self):
        h1 = blind_index(" 12345678900 ", purpose="cpf")
        h2 = blind_index("12345678900", purpose="cpf")
        h3 = blind_index("12345678900", purpose="phone")
        h4 = blind_index("00000000000", purpose="cpf")
        self.assertEqual(len(h1), 32)
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertNotEqual(h1, h4)

    def test_encrypt_bytes_uses_unique_nonces(self):
        b1, _ = encrypt_bytes(b"same-plaintext")
        b2, _ = encrypt_bytes(b"same-plaintext")
        self.assertNotEqual(b1[:12], b2[:12])
        self.assertNotEqual(b1, b2)


class FieldsHelperTests(SimpleTestCase):
    def test_normalize_digits(self):
        self.assertEqual(normalize_digits("123.456.789-00"), "12345678900")
        self.assertEqual(normalize_digits("(48) 99988-7766"), "48999887766")
        self.assertEqual(normalize_digits(""), "")
        self.assertEqual(normalize_digits(None), "")

    def test_mask_cpf_and_phone(self):
        self.assertEqual(mask_cpf("123.456.789-00"), "***.456.789-**")
        self.assertEqual(mask_cpf("123"), "***")
        self.assertEqual(mask_phone("(48) 99988-7766"), "***-7766")
        self.assertEqual(mask_phone("12"), "****")

    def test_clean_str(self):
        self.assertEqual(clean_str(None), "")
        self.assertEqual(clean_str("  Maria  ", 4), "Mari")
        self.assertEqual(clean_str(12345, 3), "123")


@override_settings(ALLOWED_HOSTS=["testserver"])
class SecurityTokenAndRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="sec_unit@escola.edu.br", password="StrongPassword!1")
        PerfilUsuario.objects.create(user=self.user, nome_exibicao="Sec Unit", papel="admin")

    def test_generate_secret_and_hash_consistency(self):
        raw, prefix, digest = generate_secret("usr")
        self.assertTrue(raw.startswith("usr_"))
        self.assertEqual(prefix, raw[:12])
        self.assertEqual(digest, hash_secret(raw))
        self.assertEqual(len(digest), 64)

    def test_expired_and_revoked_tokens_rejected(self):
        raw_token, token_obj = issue_auth_token(self.user, ip_address="127.0.0.1")
        headers = {"HTTP_AUTHORIZATION": f"Bearer {raw_token}"}
        self.assertEqual(self.client.get("/api/me/", **headers).status_code, 200)

        # Expirado -> 401
        token_obj.expira_em = timezone.now() - timedelta(minutes=1)
        token_obj.save(update_fields=["expira_em"])
        self.assertEqual(self.client.get("/api/me/", **headers).status_code, 401)

        # Novo token revogado -> 401
        raw2, tok2 = issue_auth_token(self.user, ip_address="127.0.0.1")
        tok2.revogado = True
        tok2.save(update_fields=["revogado"])
        self.assertEqual(self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {raw2}").status_code, 401)

    def test_inactive_user_token_rejected(self):
        raw_token, _ = issue_auth_token(self.user, ip_address="127.0.0.1")
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        res = self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        self.assertEqual(res.status_code, 401)

    def test_login_rate_limit_helpers(self):
        self.assertTrue(check_login_rate_limit("10.0.0.1", "a@b.com"))
        for _ in range(5):
            record_login_failure("10.0.0.1", "a@b.com")
        self.assertFalse(check_login_rate_limit("10.0.0.1", "a@b.com"))
        clear_login_failures("10.0.0.1", "a@b.com")
        self.assertTrue(check_login_rate_limit("10.0.0.1", "a@b.com"))
