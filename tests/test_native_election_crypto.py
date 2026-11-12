import os
import sys
import json
import base64
import unittest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.controllers.cryptoController import CryptoController
from app.controllers.native import tpm_linux, cng_windows, enclave_mac


class TestNativeElectionCrypto(unittest.TestCase):
    def setUp(self):
        self.crypto = CryptoController()

    def test_election_key_generation_outside_tee(self):
        """Gera a chave de eleição e confirma que ela reside fora do hardware TEE/TPM."""
        pub_b64, key_handle = self.crypto.generate_hardware_keys()
        self.assertEqual(key_handle, "votaai_desktop_hw_key")
        self.assertTrue(len(pub_b64) > 100)

        meta_path = tpm_linux._get_key_meta_path(key_handle)
        enc_path = tpm_linux._get_encrypted_key_path(key_handle)

        self.assertTrue(os.path.exists(meta_path))
        self.assertTrue(os.path.exists(enc_path))

        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        self.assertEqual(meta["KeyName"], "votaai_desktop_hw_key")
        self.assertEqual(meta["Storage"], "software-encrypted")
        self.assertIsNone(meta.get("TPMHandle"))

    def test_election_sign_and_verify(self):
        """Assina dados com a chave da eleição e valida a assinatura RSA-PSS."""
        pub_b64, key_handle = self.crypto.generate_hardware_keys()
        payload = '{"msg":"START_ELECTION","keyHandle":"votaai_desktop_hw_key"}'

        signature_b64 = self.crypto.sign_data(key_handle, payload)
        self.assertTrue(len(signature_b64) > 0)

        meta_path = tpm_linux._get_key_meta_path(key_handle)
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        pub_pem = meta["PublicKeyPEM"]
        public_key = serialization.load_pem_public_key(pub_pem.encode('utf-8'))

        # Validação RSA-PSS (padrão de verificação do backend)
        public_key.verify(
            base64.b64decode(signature_b64),
            payload.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

    def test_election_decrypt_direct_rsa(self):
        """Descriptografa votos cifrados diretamente com a chave pública da eleição."""
        pub_b64, key_handle = self.crypto.generate_hardware_keys()
        meta_path = tpm_linux._get_key_meta_path(key_handle)
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        public_key = serialization.load_pem_public_key(meta["PublicKeyPEM"].encode('utf-8'))
        voto_texto = b'{"question": "Reitor 2026", "option": "Chapa 1"}'

        cipher_bytes = public_key.encrypt(voto_texto, padding.PKCS1v15())
        decrypted = self.crypto.decrypt_data(key_handle, cipher_bytes)
        self.assertEqual(decrypted, voto_texto)

    def test_election_decrypt_vote_layered_model(self):
        """Descriptografa cédula eleitoral enviada pelo app mobile ({id_voto, pacote_cifrado})."""
        pub_b64, key_handle = self.crypto.generate_hardware_keys()
        meta_path = tpm_linux._get_key_meta_path(key_handle)
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        public_key = serialization.load_pem_public_key(meta["PublicKeyPEM"].encode('utf-8'))
        conteudo_voto = b'{"escolha": "Candidato A", "motivo": "Apuracao soberana"}'
        cipher_bytes = public_key.encrypt(conteudo_voto, padding.PKCS1v15())

        vote_record = {
            "id_voto": "VOTE-AUDIT-9988",
            "pacote_cifrado": base64.b64encode(cipher_bytes).decode('utf-8')
        }

        decrypted = self.crypto.decrypt_data(key_handle, vote_record)
        self.assertEqual(decrypted, conteudo_voto)

    def test_election_decrypt_hybrid_envelope(self):
        """Descriptografa envelope híbrido AES-256-GCM + RSA com a chave da eleição."""
        pub_b64, key_handle = self.crypto.generate_hardware_keys()
        meta_path = tpm_linux._get_key_meta_path(key_handle)
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        public_key = serialization.load_pem_public_key(meta["PublicKeyPEM"].encode('utf-8'))
        ballot_payload = b'{"respostas": [1, 3, 5]}'

        aes_key = os.urandom(32)
        iv = os.urandom(12)
        aesgcm = AESGCM(aes_key)
        encrypted_data = aesgcm.encrypt(iv, ballot_payload, None)
        ciphertext = encrypted_data[:-16]
        tag = encrypted_data[-16:]

        enc_aes_key = public_key.encrypt(aes_key, padding.PKCS1v15())

        envelope = {
            "encrypted_payload": base64.b64encode(ciphertext).decode('utf-8'),
            "encrypted_aes_key": base64.b64encode(enc_aes_key).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8')
        }

        decrypted = self.crypto.decrypt_data(key_handle, envelope)
        self.assertEqual(decrypted, ballot_payload)

    def test_mac_native_decoupled_crypto(self):
        """Valida que o módulo macOS é independente e descriptografa em software fora do TEE."""
        pub_b64, key_handle = enclave_mac.generate_key()
        self.assertEqual(key_handle, "votaai_desktop_hw_key")
        self.assertTrue(len(pub_b64) > 50)

        # Assinatura
        payload = "macOS test payload"
        sig = enclave_mac.sign_data(key_handle, payload)
        self.assertTrue(len(sig) > 0)

        # Cifra direta e decifra
        priv_key = enclave_mac._load_private_key(key_handle)
        pub_key = priv_key.public_key()
        msg = b"macOS sovereign vote"
        cipher = pub_key.encrypt(msg, padding.PKCS1v15())
        dec = enclave_mac.decrypt_data(key_handle, cipher)
        self.assertEqual(dec, msg)

        # Envelope híbrido no macOS
        aes_key = os.urandom(32)
        iv = os.urandom(12)
        aesgcm = AESGCM(aes_key)
        enc_payload = aesgcm.encrypt(iv, msg, None)
        envelope = {
            "encrypted_payload": base64.b64encode(enc_payload[:-16]).decode('utf-8'),
            "encrypted_aes_key": base64.b64encode(pub_key.encrypt(aes_key, padding.PKCS1v15())).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "tag": base64.b64encode(enc_payload[-16:]).decode('utf-8')
        }
        dec_env = enclave_mac.decrypt_data(key_handle, envelope)
        self.assertEqual(dec_env, msg)

    def test_windows_native_decoupled_crypto(self):
        """Valida que o módulo Windows é independente e executa decifra em software fora do TEE."""
        pub_b64, key_handle = cng_windows.generate_key()
        self.assertEqual(key_handle, "votaai_desktop_hw_key")
        self.assertTrue(len(pub_b64) > 50)

        # Assinatura
        sig = cng_windows.sign_data(key_handle, "windows test payload")
        self.assertTrue(len(sig) > 0)

        # Decifra direta
        priv_key = cng_windows._software_load_private_key(key_handle)
        pub_key = priv_key.public_key()
        msg = b"windows sovereign vote"
        cipher = pub_key.encrypt(msg, padding.PKCS1v15())
        dec = cng_windows.decrypt_data(key_handle, cipher)
        self.assertEqual(dec, msg)

        # Envelope híbrido no Windows
        aes_key = os.urandom(32)
        iv = os.urandom(12)
        aesgcm = AESGCM(aes_key)
        enc_payload = aesgcm.encrypt(iv, msg, None)
        envelope = {
            "encrypted_payload": base64.b64encode(enc_payload[:-16]).decode('utf-8'),
            "encrypted_aes_key": base64.b64encode(pub_key.encrypt(aes_key, padding.PKCS1v15())).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "tag": base64.b64encode(enc_payload[-16:]).decode('utf-8')
        }
        dec_env = cng_windows.decrypt_data(key_handle, envelope)
        self.assertEqual(dec_env, msg)


if __name__ == '__main__':
    unittest.main()
