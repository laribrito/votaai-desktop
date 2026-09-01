import os
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

class EncryptionService:
    def __init__(self):
        self.public_key = self._load_public_key()

    def _load_public_key(self):
        """Carrega a chave pública a partir do arquivo initial_key.json"""
        key_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'initial_key.json')
        try:
            with open(key_path, 'r') as f:
                crypto_config = json.load(f)
            
            pub_key_b64 = crypto_config.get("PublicKeyBase64")
            if not pub_key_b64:
                raise ValueError("PublicKeyBase64 não encontrada no initial_key.json")
            
            pub_key_blob = base64.b64decode(pub_key_b64)
            
            # Se for formato DER padrão (começa diferente de RSA1)
            if not pub_key_blob.startswith(b'RSA1'):
                public_key = serialization.load_der_public_key(pub_key_blob)
                return public_key
                
            # Formato BCRYPT_RSAKEY_BLOB (Microsoft CNG)
            import struct
            from cryptography.hazmat.primitives.asymmetric import rsa
            
            magic, bitlen, cbpubexp, cbmodulus, cbprime1, cbprime2 = struct.unpack('<IIIIII', pub_key_blob[:24])
            offset = 24
            exp_bytes = pub_key_blob[offset:offset+cbpubexp]
            offset += cbpubexp
            mod_bytes = pub_key_blob[offset:offset+cbmodulus]
            
            # CNG armazena Big-Endian
            e = int.from_bytes(exp_bytes, byteorder='big')
            n = int.from_bytes(mod_bytes, byteorder='big')
            
            public_numbers = rsa.RSAPublicNumbers(e, n)
            public_key = public_numbers.public_key()
            return public_key
            
        except Exception as e:
            print(f"Erro ao carregar chave pública: {e}")
            return None

    def encrypt_payload(self, payload_dict):
        """
        Criptografa o payload usando AES-GCM (Chave simétrica)
        e depois criptografa a chave simétrica com a Chave Pública RSA.
        Retorna o dicionário no formato esperado pelo middleware.
        """
        if not self.public_key:
            raise RuntimeError("Chave pública não foi carregada corretamente.")

        # Converte payload para JSON string -> bytes
        json_payload_bytes = json.dumps(payload_dict).encode('utf-8')

        # 1. Gera chave AES (32 bytes) e IV (12 bytes)
        aes_key = os.urandom(32)
        iv = os.urandom(12)

        # 2. Criptografa o payload usando AES-GCM
        aesgcm = AESGCM(aes_key)
        
        # O AESGCM no Python concatena a tag no final do ciphertext.
        # Precisamos separar os 16 bytes finais que correspondem à tag GCM.
        encrypted_data = aesgcm.encrypt(iv, json_payload_bytes, None)
        
        tag_length = 16
        ciphertext = encrypted_data[:-tag_length]
        tag = encrypted_data[-tag_length:]

        # 3. Criptografa a chave AES usando RSA Pública
        # Assumindo PKCS1v15 conforme padrão comumente usado em TPMs antigos, 
        # mude para padding.OAEP se o backend utilizar OAEP.
        encrypted_aes_key = self.public_key.encrypt(
            aes_key,
            padding.PKCS1v15()
        )

        # 4. Converte tudo para Base64 para envio JSON
        return {
            "encrypted_payload": base64.b64encode(ciphertext).decode('utf-8'),
            "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8')
        }
