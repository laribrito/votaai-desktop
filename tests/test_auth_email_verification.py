import json
import unittest
from unittest.mock import MagicMock, patch

from app.controllers.authController import AuthController


class TestAuthEmailVerification(unittest.TestCase):
    def setUp(self):
        self.controller = AuthController()
        self.controller.http_client = MagicMock()

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


if __name__ == '__main__':
    unittest.main()
