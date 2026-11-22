import os
import sys
import json
import base64
import hashlib
import unittest
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.controllers.cryptoController import CryptoController
from app.controllers.tallyElectionController import TallyElectionController


class TestTallyElection(unittest.TestCase):
    def setUp(self):
        self.crypto = CryptoController()
        self.pub_b64, self.key_handle = self.crypto.generate_hardware_keys()

    def tearDown(self):
        backend = self.crypto.backend
        for getter in ('_get_key_meta_path', '_get_encrypted_key_path'):
            if hasattr(backend, getter):
                path = getattr(backend, getter)(self.key_handle)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def test_export_election_private_key_pem(self):
        """Exporta a chave privada da eleição em formato PEM e valida correspondência matemática."""
        priv_pem = self.crypto.export_election_private_key(self.key_handle)
        self.assertIn("BEGIN PRIVATE KEY", priv_pem)

        loaded_priv = serialization.load_pem_private_key(priv_pem.encode('utf-8'), password=None)
        derived_pub_pem = loaded_priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        # Carrega chave pública salva nos metadados
        backend = self.crypto.backend
        meta_path = backend._get_key_meta_path(self.key_handle)
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        self.assertEqual(derived_pub_pem.strip(), meta["PublicKeyPEM"].strip())

    @patch('app.controllers.tallyElectionController.HttpClient')
    def test_fetch_closed_elections_success(self, MockHttpClient):
        mock_http = MockHttpClient.return_value
        ctrl = TallyElectionController()
        ctrl.http_client = mock_http

        # Configura resposta simulada do backend para listagem de eleições fechadas
        def mock_post(url, payload):
            nonce = payload.get("nonceClient1")
            return {
                "status": "sucesso",
                "dados": {
                    "nonceClient1": nonce,
                    "elections": [
                        {"keyHandle": "handle_closed_1", "titulo": "Eleição Reitor 2026"}
                    ]
                }
            }

        mock_http.post.side_effect = mock_post

        res_str = ctrl._execute_fetch_closed()
        res = json.loads(res_str)

        self.assertEqual(res["status"], "sucesso")
        self.assertEqual(len(res["elections"]), 1)
        self.assertEqual(res["elections"][0]["keyHandle"], "handle_closed_1")

    @patch('app.controllers.tallyElectionController.HttpClient')
    def test_fetch_closed_elections_nonce_mismatch_fails(self, MockHttpClient):
        mock_http = MockHttpClient.return_value
        ctrl = TallyElectionController()
        ctrl.http_client = mock_http

        mock_http.post.return_value = {
            "status": "sucesso",
            "dados": {
                "nonceClient1": "tampered_nonce",
                "elections": []
            }
        }

        res_str = ctrl._execute_fetch_closed()
        res = json.loads(res_str)

        self.assertEqual(res["status"], "erro")
        self.assertIn("Nonce incompatível", res["mensagem"])

    @patch('app.controllers.tallyElectionController.HttpClient')
    def test_execute_tally_election_full_flow(self, MockHttpClient):
        """Testa o fluxo soberano completo: baixar votos, decifrar, calcular hash, exportar private_key e submeter."""
        mock_http = MockHttpClient.return_value
        ctrl = TallyElectionController()
        ctrl.http_client = mock_http
        ctrl.crypto_controller = self.crypto

        # Prepara votos cifrados reais com a chave pública da eleição
        priv_pem = self.crypto.export_election_private_key(self.key_handle)
        priv_key = serialization.load_pem_private_key(priv_pem.encode('utf-8'), password=None)
        pub_key = priv_key.public_key()

        voto1 = pub_key.encrypt(b'{"question": "Reitor 2026", "option": "Chapa 1"}', padding.PKCS1v15())
        voto2 = pub_key.encrypt(b'{"question": "Reitor 2026", "option": "Chapa 2"}', padding.PKCS1v15())
        voto3 = pub_key.encrypt(b'{"question": "Reitor 2026", "option": "Chapa 1"}', padding.PKCS1v15())

        def mock_post(url, payload):
            if "votes" in url:
                # Retorna votos cifrados com o nonce esperado
                return {
                    "status": "sucesso",
                    "dados": {
                        "nonceClient": payload.get("nonceClient"),
                        "votes": [
                            {"id_generated": "V-1", "content": base64.b64encode(voto1).decode('utf-8')},
                            {"id_generated": "V-2", "content": base64.b64encode(voto2).decode('utf-8')},
                            {"id_generated": "V-3", "content": base64.b64encode(voto3).decode('utf-8')},
                        ]
                    }
                }
            elif "tally" in url:
                # Valida que o payload enviado contém tally_hash, private_key e results
                self.assertIn("tally_hash", payload)
                self.assertIn("BEGIN PRIVATE KEY", payload["private_key"])
                self.assertEqual(payload["results"]["Reitor 2026"]["Chapa 1"], 2)
                self.assertEqual(payload["results"]["Reitor 2026"]["Chapa 2"], 1)

                return {
                    "status": "sucesso",
                    "dados": {
                        "nonceClient": payload.get("nonceClient"),
                        "tally_id": 42,
                        "tally_hash": payload["tally_hash"],
                        "status": "TALLIED"
                    }
                }
            raise ValueError(f"URL inesperada: {url}")

        mock_http.post.side_effect = mock_post

        res_str = ctrl._execute_tally_election(self.key_handle)
        res = json.loads(res_str)

        self.assertEqual(res["status"], "sucesso")
        self.assertEqual(res["total_votos"], 3)
        self.assertEqual(res["results"]["Reitor 2026"]["Chapa 1"], 2)
        self.assertEqual(res["results"]["Reitor 2026"]["Chapa 2"], 1)
        self.assertTrue(len(res["tally_hash"]) == 64)

    @patch('app.controllers.tallyElectionController.HttpClient')
    def test_execute_tally_with_mobile_choices_and_abstention(self, MockHttpClient):
        """Testa decifração com formato mobile {choices: {q_id: opt_id}} e metadados de abstenção."""
        mock_http = MockHttpClient.return_value
        ctrl = TallyElectionController()
        ctrl.http_client = mock_http
        ctrl.crypto_controller = self.crypto

        priv_pem = self.crypto.export_election_private_key(self.key_handle)
        priv_key = serialization.load_pem_private_key(priv_pem.encode('utf-8'), password=None)
        pub_key = priv_key.public_key()

        voto_payload = json.dumps({
            "election_id": 1,
            "choices": {"101": 201},
            "timestamp": "2026-11-12T20:00:00Z"
        }).encode('utf-8')
        voto_enc = pub_key.encrypt(voto_payload, padding.PKCS1v15())

        def mock_post(url, payload):
            if "votes" in url:
                return {
                    "status": "sucesso",
                    "dados": {
                        "nonceClient": payload.get("nonceClient"),
                        "total_voters": 5,
                        "abstention_count": 4,
                        "abstention_percentage": 80.0,
                        "questions": [
                            {
                                "id": 101,
                                "question": "Presidente",
                                "options": [
                                    {"id": 201, "label": "Chapa A"},
                                    {"id": 202, "label": "Chapa B"}
                                ]
                            }
                        ],
                        "votes": [
                            {"id_generated": "V-10", "content": base64.b64encode(voto_enc).decode('utf-8')}
                        ]
                    }
                }
            elif "tally" in url:
                return {
                    "status": "sucesso",
                    "dados": {
                        "nonceClient": payload.get("nonceClient"),
                        "tally_hash": payload["tally_hash"],
                        "status": "TALLIED"
                    }
                }
            raise ValueError(f"URL: {url}")

        mock_http.post.side_effect = mock_post
        res = json.loads(ctrl._execute_tally_election(self.key_handle))

        self.assertEqual(res["status"], "sucesso")
        self.assertEqual(res["total_votos"], 1)
        self.assertEqual(res["total_voters"], 5)
        self.assertEqual(res["abstention_count"], 4)
        self.assertEqual(res["abstention_percentage"], 80.0)
        self.assertEqual(res["results"]["Presidente"]["Chapa A"], 1)
        self.assertEqual(res["results"]["questions"][0]["options"][0]["votes"], 1)
        self.assertEqual(res["results"]["questions"][0]["options"][0]["percentage"], 100.0)

    @patch('app.controllers.tallyElectionController.HttpClient')
    def test_tally_hybrid_iso7816_4_padded_ballots(self, MockHttpClient):
        """Valida apuração de cédulas híbridas preenchidas com ISO/IEC 7816-4 para 1024 B (incluindo >245 B)."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from app.controllers.tallyElectionController import decrypt_vote_with_pem

        mock_http = MockHttpClient.return_value
        ctrl = TallyElectionController()
        ctrl.http_client = mock_http
        ctrl.crypto_controller = self.crypto

        priv_pem = self.crypto.export_election_private_key(self.key_handle)
        priv_key = serialization.load_pem_private_key(priv_pem.encode('utf-8'), password=None)
        pub_key = priv_key.public_key()

        def make_hybrid_ballot(choices: dict) -> str:
            raw = json.dumps({"election_id": 1, "choices": choices, "timestamp": "2026-11-22T18:00:00.000Z"}, separators=(",", ":")).encode("utf-8")
            target = ((len(raw) // 1024) + 1) * 1024
            padded = raw + b"\x80" + b"\x00" * (target - len(raw) - 1)
            aes_key, iv = os.urandom(32), os.urandom(12)
            ct_tag = AESGCM(aes_key).encrypt(iv, padded, None)
            enc_key = pub_key.encrypt(aes_key, padding.PKCS1v15())
            return json.dumps({
                "encrypted_payload": base64.b64encode(ct_tag[:-16]).decode("utf-8"),
                "encrypted_aes_key": base64.b64encode(enc_key).decode("utf-8"),
                "iv": base64.b64encode(iv).decode("utf-8"),
                "tag": base64.b64encode(ct_tag[-16:]).decode("utf-8"),
            }, separators=(",", ":"))

        ballot_short = make_hybrid_ballot({"1": 1})
        ballot_large = make_hybrid_ballot({str(q): 1000 + q for q in range(1, 15)})
        self.assertEqual(len(ballot_short), len(ballot_large))
        self.assertEqual(len(ballot_short), 1816)

        questions_meta = [
            {
                "id": q,
                "question": f"Pergunta {q}",
                "options": [
                    {"id": 1, "label": "Ana"},
                    {"id": 1000 + q, "label": f"Chapa {q}"},
                ],
            }
            for q in range(1, 15)
        ]

        out = TallyElectionController.tally_votes_core(
            raw_votes=[
                {"id_generated": "V-SHORT", "content": ballot_short},
                {"id_generated": "V-LARGE", "content": ballot_large},
            ],
            questions_meta=questions_meta,
            total_voters=2,
            key_handle=self.key_handle,
            decrypt_fn=lambda enc: decrypt_vote_with_pem(priv_pem, enc),
        )
        self.assertEqual(out["total_votos"], 2)
        self.assertEqual(out["results"]["Pergunta 1"]["Ana"], 1)
        self.assertEqual(out["results"]["Pergunta 1"]["Chapa 1"], 1)
        self.assertEqual(out["results"]["Pergunta 14"]["Chapa 14"], 1)
