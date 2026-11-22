import json
import unittest
from unittest.mock import MagicMock, patch

from app.controllers.authController import AuthController
from app.services.http_client import HttpClient


class TestAuthEmailVerification(unittest.TestCase):
    def setUp(self):
        HttpClient.clear_auth_token()
        self.controller = AuthController()
        self.controller.http_client = MagicMock()

    def tearDown(self):
        HttpClient.clear_auth_token()

    @patch('app.controllers.authController.DeviceController')
    @patch('app.controllers.authController.CryptoController')
    def test_start_pre_registration_returns_email_verification_step(self, mock_crypto, mock_device):
        mock_device.return_value.get_device_id.return_value = "dev-test-123"
        mock_crypto.return_value.get_public_key_pem.return_value = "PEM"
        self.controller.http_client.post.return_value = {
            "status": "sucesso",
            "dados": {
                "message": "Pre-registration started successfully. A verification code has been sent to your email.",
                "signature": "sig"
            }
        }

        res = json.loads(self.controller._execute_start_pre_registration("admin@votaai.org", "SenhaForte123!"))
        self.assertEqual(res["status"], "sucesso")
        self.assertTrue(res["requires_email_verification"])
        self.assertIn("verification code", res["mensagem"])

    @patch('app.controllers.authController.DeviceController')
    def test_verify_email_returns_qr_and_secret(self, mock_device):
        mock_device.return_value.get_device_id.return_value = "dev-test-123"
        self.controller.http_client.post.return_value = {
            "status": "sucesso",
            "dados": {
                "message": "Email verified successfully.",
                "provisioning_uri": "otpauth://totp/VotaAI:admin@votaai.org?secret=JBSWY3DPEHPK3PXP&issuer=VotaAI",
                "signature": "sig"
            }
        }

        res = json.loads(self.controller._execute_verificar_email("admin@votaai.org", "123456"))
        self.assertEqual(res["status"], "sucesso")
        self.assertFalse(res["requires_email_verification"])
        self.assertEqual(res["secret"], "JBSWY3DPEHPK3PXP")
        self.assertTrue(res["qr_base64"].startswith("data:image/png;base64,"))

    @patch('app.controllers.authController.DeviceController')
    def test_resend_email_returns_success(self, mock_device):
        mock_device.return_value.get_device_id.return_value = "dev-test-123"
        self.controller.http_client.post.return_value = {
            "status": "sucesso",
            "dados": {
                "message": "A new verification code has been sent to your email.",
                "signature": "sig"
            }
        }

        res = json.loads(self.controller._execute_reenviar_email("admin@votaai.org"))
        self.assertEqual(res["status"], "sucesso")
        self.assertIn("new verification code", res["mensagem"])

    @patch('app.services.http_client.urllib.request.urlopen')
    @patch('app.services.http_client.EncryptionController')
    def test_http_client_injects_auth_token_only_on_protected_routes(self, mock_enc_cls, mock_urlopen):
        mock_enc = mock_enc_cls.return_value
        mock_enc.encrypt_payload.return_value = {"encrypted_payload": "a", "encrypted_aes_key": "b", "iv": "c", "tag": "d"}
        mock_enc.decrypt_response.return_value = {"ok": True}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = HttpClient()
        HttpClient.set_auth_token("knox-secret-token-123")

        client.post("/api/election/create/", {"title": "Teste"})
        req_election = mock_urlopen.call_args_list[-1][0][0]
        self.assertEqual(req_election.get_header("Authorization"), "Token knox-secret-token-123")

        client.post("/api/auth/login/", {"username": "admin"})
        req_login = mock_urlopen.call_args_list[-1][0][0]
        self.assertIsNone(req_login.get_header("Authorization"))

        client.post("/api/admin/pre-registration/start/", {"email": "a@b.c"})
        req_prereg = mock_urlopen.call_args_list[-1][0][0]
        self.assertIsNone(req_prereg.get_header("Authorization"))

        HttpClient.clear_auth_token()
        client.post("/api/election/available/", {"msg": "FETCH_AVAILABLE"})
        req_after_clear = mock_urlopen.call_args_list[-1][0][0]
        self.assertIsNone(req_after_clear.get_header("Authorization"))

    @patch('app.services.http_client.urllib.request.urlopen')
    @patch('app.services.http_client.EncryptionController')
    def test_http_client_rejects_plaintext_200_response(self, mock_enc_cls, mock_urlopen):
        from app.controllers.encryptionController import EncryptionController

        real_enc = EncryptionController.__new__(EncryptionController)
        real_enc.encrypt_payload = MagicMock(
            return_value={"encrypted_payload": "a", "encrypted_aes_key": "b", "iv": "c", "tag": "d"}
        )
        mock_enc_cls.return_value = real_enc

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok", "token": "FORGED_PLAINTEXT"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = HttpClient()
        res = client.post("/api/auth/login/", {"username": "admin"})
        self.assertEqual(res["status"], "erro")
        self.assertIn("não está cifrada", res["mensagem"])

    @patch('app.services.http_client.urllib.request.urlopen')
    @patch('app.services.http_client.EncryptionController')
    def test_http_client_rejects_200_when_decryption_fails(self, mock_enc_cls, mock_urlopen):
        mock_enc = mock_enc_cls.return_value
        mock_enc.encrypt_payload.return_value = {"encrypted_payload": "a", "encrypted_aes_key": "b", "iv": "c", "tag": "d"}
        mock_enc.decrypt_response.side_effect = ValueError("InvalidTag")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"encrypted_payload": "x", "encrypted_aes_key": "y", "iv": "z", "tag": "w"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = HttpClient()
        res = client.post("/api/auth/login/", {"username": "admin"})
        self.assertEqual(res["status"], "erro")
        self.assertIn("InvalidTag", res["mensagem"])
        mock_enc.decrypt_response.assert_called_once_with(
            '{"encrypted_payload": "x", "encrypted_aes_key": "y", "iv": "z", "tag": "w"}',
            require_encrypted=True,
        )

    def test_auth_controller_logout_clears_http_client_token(self):
        HttpClient.set_auth_token("knox-active-token")
        self.controller._auth_token = "knox-active-token"
        self.controller._is_authenticated = True

        self.controller.logout()
        self.assertFalse(self.controller.isAuthenticated)
        self.assertEqual(self.controller.authToken, "")
        self.assertIsNone(HttpClient.get_auth_token())


if __name__ == '__main__':
    unittest.main()
