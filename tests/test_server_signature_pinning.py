import base64
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.controllers.encryptionController import EncryptionController, pad_iso7816_4
from app.services.http_client import HttpClient


def _build_signed_envelope(
    payload_bytes: bytes,
    server_priv_key: rsa.RSAPrivateKey | None,
    sig_padding=None,
    omit_signature: bool = False,
) -> dict:
    aes_key = os.urandom(32)
    iv = os.urandom(12)
    padded = pad_iso7816_4(payload_bytes)
    encrypted = AESGCM(aes_key).encrypt(iv, padded, None)
    ciphertext, tag = encrypted[:-16], encrypted[-16:]

    envelope = {
        "encrypted_payload": base64.b64encode(ciphertext).decode("utf-8"),
        "encrypted_aes_key": base64.b64encode(aes_key).decode("utf-8"),
        "iv": base64.b64encode(iv).decode("utf-8"),
        "tag": base64.b64encode(tag).decode("utf-8"),
    }

    if not omit_signature and server_priv_key is not None:
        if sig_padding is None:
            sig_padding = padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        sig = server_priv_key.sign(payload_bytes, sig_padding, hashes.SHA256())
        envelope["server_signature"] = base64.b64encode(sig).decode("utf-8")

    return envelope


class TestServerSignaturePinning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.server_pub = cls.server_priv.public_key()
        cls.rogue_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def _make_controller(self) -> EncryptionController:
        enc = EncryptionController.__new__(EncryptionController)
        enc.server_public_key = self.server_pub
        enc.client_key_info = {"KeyName": "TestClientKey", "Provider": "TestProvider"}
        enc.machine_public_key_pem = "TEST_PEM"
        return enc

    @patch("app.controllers.encryptionController.CryptoController.get_backend")
    def test_decrypt_response_accepts_valid_rsa_pss_signature(self, mock_get_backend):
        mock_get_backend.return_value.decrypt_data.side_effect = lambda _k, aes_bytes, provider_name=None: aes_bytes
        enc = self._make_controller()
        raw_bytes = b'{"status":"ok","items":[1,2,3]}'
        envelope = _build_signed_envelope(raw_bytes, self.server_priv)

        result = enc.decrypt_response(json.dumps(envelope), require_encrypted=True)
        self.assertEqual(result, {"status": "ok", "items": [1, 2, 3]})

    @patch("app.controllers.encryptionController.CryptoController.get_backend")
    def test_decrypt_response_accepts_valid_pkcs1v15_fallback(self, mock_get_backend):
        mock_get_backend.return_value.decrypt_data.side_effect = lambda _k, aes_bytes, provider_name=None: aes_bytes
        enc = self._make_controller()
        raw_bytes = b'{"status":"ok","platform":"windows"}'
        envelope = _build_signed_envelope(raw_bytes, self.server_priv, sig_padding=padding.PKCS1v15())

        result = enc.decrypt_response(json.dumps(envelope), require_encrypted=True)
        self.assertEqual(result, {"status": "ok", "platform": "windows"})

    @patch("app.controllers.encryptionController.CryptoController.get_backend")
    def test_decrypt_response_rejects_missing_server_signature(self, mock_get_backend):
        mock_get_backend.return_value.decrypt_data.side_effect = lambda _k, aes_bytes, provider_name=None: aes_bytes
        enc = self._make_controller()
        envelope = _build_signed_envelope(b'{"status":"ok"}', self.server_priv, omit_signature=True)

        for req_enc in (True, False):
            with self.assertRaises(ValueError) as ctx:
                enc.decrypt_response(json.dumps(envelope), require_encrypted=req_enc)
            self.assertIn("server_signature", str(ctx.exception))

    @patch("app.controllers.encryptionController.CryptoController.get_backend")
    def test_decrypt_response_rejects_rogue_server_signature(self, mock_get_backend):
        mock_get_backend.return_value.decrypt_data.side_effect = lambda _k, aes_bytes, provider_name=None: aes_bytes
        enc = self._make_controller()
        envelope = _build_signed_envelope(b'{"status":"ok"}', self.rogue_priv)

        with self.assertRaises(ValueError) as ctx:
            enc.decrypt_response(json.dumps(envelope), require_encrypted=True)
        self.assertIn("public key pinning", str(ctx.exception))

    @patch("app.services.http_client.urllib.request.urlopen")
    @patch("app.services.http_client.EncryptionController")
    @patch("app.controllers.encryptionController.CryptoController.get_backend")
    def test_http_client_rejects_encrypted_http_error_with_invalid_signature(
        self, mock_get_backend, mock_enc_cls, mock_urlopen
    ):
        mock_get_backend.return_value.decrypt_data.side_effect = lambda _k, aes_bytes, provider_name=None: aes_bytes
        real_enc = self._make_controller()
        real_enc.encrypt_payload = MagicMock(
            return_value={"encrypted_payload": "a", "encrypted_aes_key": "b", "iv": "c", "tag": "d"}
        )
        mock_enc_cls.return_value = real_enc

        rogue_err_env = json.dumps(_build_signed_envelope(b'{"detail":"Forbidden"}', self.rogue_priv)).encode("utf-8")
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/election/create/",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(rogue_err_env),
        )

        client = HttpClient()
        res = client.post("/api/election/create/", {"title": "Teste"})
        self.assertEqual(res["status"], "erro")
        self.assertIn("Falha de segurança", res["mensagem"])

    @patch("app.services.http_client.urllib.request.urlopen")
    @patch("app.services.http_client.EncryptionController")
    def test_http_client_preserves_plaintext_http_error(self, mock_enc_cls, mock_urlopen):
        real_enc = self._make_controller()
        real_enc.encrypt_payload = MagicMock(
            return_value={"encrypted_payload": "a", "encrypted_aes_key": "b", "iv": "c", "tag": "d"}
        )
        mock_enc_cls.return_value = real_enc

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/auth/login/",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"Credenciais invalidas"}'),
        )

        client = HttpClient()
        res = client.post("/api/auth/login/", {"username": "admin"})
        self.assertEqual(res["status"], "erro")
        self.assertEqual(res["mensagem"], {"error": "Credenciais invalidas"})


if __name__ == "__main__":
    unittest.main()
