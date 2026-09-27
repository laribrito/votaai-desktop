import os
import sys
import json
import base64
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization, hashes
from app.controllers.cryptoController import CryptoController

class EncryptionController:
    def __init__(self):
        self.server_public_key = self._load_server_public_key()
        self.client_key_info, self.client_public_key_pem = self._load_or_generate_client_hardware_keys()

    def _get_resources_dir(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources'))

    def _load_server_public_key(self):
        """Carrega a chave pública do servidor a partir do arquivo obrigatório initial_key.json"""
        key_path = os.path.join(self._get_resources_dir(), 'initial_key.json')
        if not os.path.exists(key_path):
            raise FileNotFoundError(
                f"O arquivo obrigatório 'initial_key.json' não foi encontrado em '{key_path}'. "
                "Certifique-se de configurar a chave pública do servidor em app/resources/initial_key.json."
            )

        try:
            with open(key_path, 'r', encoding='utf-8') as f:
                crypto_config = json.load(f)
            
            if isinstance(crypto_config, list):
                crypto_config = next((k for k in crypto_config if k.get("KeyName") == "VotaAI_SecureKey_1"), crypto_config[0] if crypto_config else {})

            pub_key_b64 = crypto_config.get("PublicKeyBase64")
            if not pub_key_b64:
                raise ValueError("PublicKeyBase64 não encontrada no initial_key.json")
            
            return self._parse_public_key_blob(pub_key_b64)
        except Exception as e:
            print(f"Erro ao carregar chave pública do servidor: {e}")
            raise


    def _parse_public_key_blob(self, pub_key_b64):
        """Converte uma chave pública Base64 (DER, PEM ou BCRYPT_RSAKEY_BLOB) em um objeto RSA public key."""
        if isinstance(pub_key_b64, str) and "-----BEGIN" in pub_key_b64:
            return serialization.load_pem_public_key(pub_key_b64.encode('utf-8'))

        pub_key_blob = base64.b64decode(pub_key_b64)
        
        # Se for formato DER padrão (começa diferente de RSA1)
        if not pub_key_blob.startswith(b'RSA1'):
            try:
                return serialization.load_der_public_key(pub_key_blob)
            except Exception:
                pass
            
        # Formato BCRYPT_RSAKEY_BLOB (Microsoft CNG)
        magic, bitlen, cbpubexp, cbmodulus, cbprime1, cbprime2 = struct.unpack('<IIIIII', pub_key_blob[:24])
        offset = 24
        exp_bytes = pub_key_blob[offset:offset+cbpubexp]
        offset += cbpubexp
        mod_bytes = pub_key_blob[offset:offset+cbmodulus]
        
        # CNG armazena Big-Endian
        e = int.from_bytes(exp_bytes, byteorder='big')
        n = int.from_bytes(mod_bytes, byteorder='big')
        
        public_numbers = rsa.RSAPublicNumbers(e, n)
        return public_numbers.public_key()

    def _load_or_generate_client_hardware_keys(self):
        """
        Carrega os metadados da chave de hardware do cliente a partir de client_key.json.
        Se não existir, gera uma nova chave no Secure Element (TPM) / Provedor Seguro do hardware e salva o JSON.
        A chave privada NUNCA sai do hardware/armazenamento seguro.
        """
        key_path = os.path.join(self._get_resources_dir(), 'client_key.json')
        client_info = None

        if os.path.exists(key_path):
            try:
                with open(key_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get("PublicKeyBase64") and data.get("KeyName"):
                    client_info = data
            except Exception as e:
                print(f"Erro ao ler client_key.json existente: {e}")

        if not client_info:
            print("Gerando chave no hardware (Secure Element / TPM)...")
            crypto_backend = CryptoController.get_backend()
            client_info = crypto_backend.generate_rsa_key("VotaAI_DesktopClient_Key")
            try:
                os.makedirs(os.path.dirname(key_path), exist_ok=True)
                with open(key_path, 'w', encoding='utf-8') as f:
                    json.dump(client_info, f, indent=4)
            except Exception as e:
                print(f"Erro ao salvar client_key.json: {e}")

        # Extrai a chave pública do cliente em formato PEM para envio
        client_pub_rsa = self._parse_public_key_blob(client_info["PublicKeyBase64"])
        client_pub_pem = client_pub_rsa.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        return client_info, client_pub_pem

    def reload_client_keys(self):
        """Recarrega os metadados e chave pública do cliente."""
        self.client_key_info, self.client_public_key_pem = self._load_or_generate_client_hardware_keys()
        return self.client_key_info, self.client_public_key_pem

    def encrypt_payload(self, payload_dict):
        """
        Implementa Sign-then-Encrypt:
          1. Serializa o payload canonicamente (chaves ordenadas, sem espaços).
          2. Assina com RSA-PSS + SHA-256 via chave privada residente no hardware.
          3. Injeta 'signature' e 'client_public_key' no payload.
          4. Cifra o payload enriquecido com AES-256-GCM.
          5. Protege a chave AES com a chave pública RSA do servidor (PKCS1v15).
        """
        if not self.server_public_key:
            self.server_public_key = self._load_server_public_key()
            if not self.server_public_key:
                raise RuntimeError("Chave pública do servidor não foi carregada corretamente.")

        # 1. Serialização canônica — determinística, independente de plataforma
        canonical_json = json.dumps(payload_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

        # 2. Assina o JSON canônico com RSA-PSS via hardware (chave privada nunca sai do dispositivo)
        crypto_backend = CryptoController.get_backend()
        key_name = (
            self.client_key_info.get("KeyName", "VotaAI_DesktopClient_Key")
            if self.client_key_info else "VotaAI_DesktopClient_Key"
        )
        try:
            signature_b64 = crypto_backend.sign_data(key_name, canonical_json)
        except Exception as e:
            raise RuntimeError(f"Falha ao assinar o payload com a chave de hardware: {e}") from e

        # 3. Enriquece o payload com a assinatura e a chave pública do cliente antes de cifrar
        signed_payload = dict(payload_dict)
        signed_payload["signature"] = signature_b64
        signed_payload["client_public_key"] = self.client_public_key_pem

        # 4. Cifra o payload enriquecido com AES-256-GCM
        json_payload_bytes = json.dumps(signed_payload).encode('utf-8')
        aes_key = os.urandom(32)
        iv = os.urandom(12)
        aesgcm = AESGCM(aes_key)
        encrypted_data = aesgcm.encrypt(iv, json_payload_bytes, None)
        tag_length = 16
        ciphertext = encrypted_data[:-tag_length]
        tag = encrypted_data[-tag_length:]

        # 5. Protege a chave AES com a chave pública RSA do servidor
        encrypted_aes_key = self.server_public_key.encrypt(
            aes_key,
            padding.PKCS1v15()
        )

        envelope = {
            "encrypted_payload": base64.b64encode(ciphertext).decode('utf-8'),
            "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8')
        }
        return envelope

    def decrypt_response(self, response_data):
        """
        Descriptografa uma resposta recebida do servidor no formato híbrido (AES-GCM + RSA).
        A chave AES é descriptografada diretamente no Secure Element / TPM de hardware.
        """
        if not response_data:
            return response_data

        if isinstance(response_data, (bytes, bytearray)):
            response_data = response_data.decode('utf-8')

        data_dict = None
        if isinstance(response_data, str):
            try:
                data_dict = json.loads(response_data)
            except Exception:
                return response_data
        elif isinstance(response_data, dict):
            data_dict = response_data

        if not isinstance(data_dict, dict):
            return response_data

        # Verifica se contém os campos de envelope criptografado
        encrypted_payload = data_dict.get('encrypted_payload')
        encrypted_aes_key = data_dict.get('encrypted_aes_key')
        iv = data_dict.get('iv')
        tag = data_dict.get('tag')

        if not encrypted_payload or not encrypted_aes_key or not iv or not tag:
            # Não é um envelope criptografado, retorna o próprio dict
            return data_dict

        if not self.client_key_info:
            raise RuntimeError("Informações da chave de hardware do cliente não disponíveis.")

        # 1. Descriptografa a chave AES usando o HARDWARE TPM / Backend
        enc_aes_key_bytes = base64.b64decode(encrypted_aes_key)
        key_name = self.client_key_info.get("KeyName", "VotaAI_DesktopClient_Key")
        provider = self.client_key_info.get("Provider", "Microsoft Platform Crypto Provider")
        
        crypto_backend = CryptoController.get_backend()
        aes_key_bytes = crypto_backend.decrypt_data(key_name, enc_aes_key_bytes, provider_name=provider)

        # 2. Descriptografa o payload com AES-GCM usando a chave revelada pelo hardware
        aesgcm = AESGCM(aes_key_bytes[:32])
        iv_bytes = base64.b64decode(iv)
        tag_bytes = base64.b64decode(tag)
        payload_bytes = base64.b64decode(encrypted_payload)

        ciphertext = payload_bytes + tag_bytes
        decrypted_json_bytes = aesgcm.decrypt(iv_bytes, ciphertext, None)
        decrypted_str = decrypted_json_bytes.decode('utf-8')

        try:
            return json.loads(decrypted_str)
        except Exception:
            return decrypted_str



