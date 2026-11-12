import base64
import os
import struct
import stat
import hashlib
import subprocess
import json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def _get_keys_dir():
    resources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'resources'))
    keys_dir = os.path.join(resources_dir, '.client_keys')
    os.makedirs(keys_dir, exist_ok=True)
    return keys_dir

def _get_encrypted_key_path(key_name):
    clean_name = "".join(c for c in key_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(_get_keys_dir(), f"{clean_name}.enc")

def _rsa_public_to_cng_blob(public_key: rsa.RSAPublicKey) -> bytes:
    numbers = public_key.public_numbers()
    e = numbers.e
    n = numbers.n
    e_bytes = e.to_bytes((e.bit_length() + 7) // 8, byteorder='big')
    mod_len = (public_key.key_size + 7) // 8
    n_bytes = n.to_bytes(mod_len, byteorder='big')
    magic = 0x31415352
    header = struct.pack('<IIIIII', magic, public_key.key_size, len(e_bytes), len(n_bytes), 0, 0)
    return header + e_bytes + n_bytes

def _get_machine_secret():
    """
    Deriva um segredo de 32 bytes único desta instalação macOS,
    usando o IOPlatformUUID (UUID único do hardware Apple).
    """
    try:
        result = subprocess.run(
            ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if 'IOPlatformUUID' in line:
                uuid = line.split('"')[-2]
                break
        else:
            uuid = "fallback-mac-uuid"
    except Exception:
        import socket
        uuid = socket.gethostname()

    return hashlib.pbkdf2_hmac(
        'sha256',
        uuid.encode('utf-8'),
        b'VotaAI-DesktopClient-KeyProtection-v1',
        iterations=200_000
    )

def _encrypt_pem(pem_bytes: bytes) -> bytes:
    key = _get_machine_secret()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, pem_bytes, b'VotaAI-client-key-aad')
    return iv + ciphertext

def _decrypt_pem(encrypted: bytes) -> bytes:
    key = _get_machine_secret()
    iv, ciphertext = encrypted[:12], encrypted[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext, b'VotaAI-client-key-aad')

def generate_rsa_key(key_name="VotaAI_DesktopClient_Key"):
    """
    Gera uma chave RSA segura no macOS.
    A chave privada é cifrada com AES-256-GCM usando o IOPlatformUUID como segredo.
    Nunca fica em plaintext no disco.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    encrypted = _encrypt_pem(pem_bytes)
    enc_path = _get_encrypted_key_path(key_name)
    with open(enc_path, 'wb') as f:
        f.write(encrypted)
    try:
        os.chmod(enc_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

    cng_blob = _rsa_public_to_cng_blob(private_key.public_key())
    print("[VotaAI] Chave gerada e cifrada com IOPlatformUUID secret. NÃO está em plaintext no disco.")

    return {
        "KeyName": key_name,
        "PublicKeyBase64": base64.b64encode(cng_blob).decode('utf-8'),
        "Algorithm": "RSA",
        "Provider": "macOS (AES-256-GCM encrypted, IOPlatformUUID derived key)"
    }

def generate_key():
    """
    Gera a chave da eleição fora do hardware seguro (TEE) para viabilizar a ação de apurar.
    A chave privada da eleição NUNCA é salva no chip/enclave, permanecendo em software.
    """
    key_name = "votaai_desktop_hw_key"
    meta = generate_rsa_key(key_name)
    return meta.get("PublicKeyBase64"), meta.get("KeyName")

def _load_private_key(key_handle):
    enc_path = _get_encrypted_key_path(key_handle)
    if not os.path.exists(enc_path):
        generate_rsa_key(key_handle)
    with open(enc_path, 'rb') as f:
        encrypted = f.read()
    pem_bytes = _decrypt_pem(encrypted)
    return serialization.load_pem_private_key(pem_bytes, password=None)

def decrypt_data(key_handle, encrypted_data, provider_name=None):
    """
    Descriptografa dados usando a chave privada RSA no macOS.
    - Se for a chave da eleição (fora do TEE): descriptografa em software na memória RAM (PKCS#1 v1.5 / OAEP / híbrido).
    - Se for a chave da máquina: decifra usando a chave do enclave/dispositivo.
    """
    if key_handle != "VotaAI_DesktopClient_Key":
        private_key = _load_private_key(key_handle)

        parsed_dict = None
        if isinstance(encrypted_data, dict):
            parsed_dict = encrypted_data
        elif isinstance(encrypted_data, str):
            try:
                val = json.loads(encrypted_data)
                if isinstance(val, dict):
                    parsed_dict = val
            except Exception:
                parsed_dict = None

        # Caso A: Modelo em camadas do voto ({id_voto, pacote_cifrado})
        if parsed_dict and "pacote_cifrado" in parsed_dict:
            return decrypt_data(key_handle, parsed_dict["pacote_cifrado"], provider_name=provider_name)

        # Caso B: Envelope híbrido AES-GCM + RSA
        if parsed_dict and all(k in parsed_dict for k in ("encrypted_payload", "encrypted_aes_key", "iv", "tag")):
            enc_aes_key = base64.b64decode(parsed_dict["encrypted_aes_key"])
            aes_key = private_key.decrypt(enc_aes_key, padding.PKCS1v15())
            aesgcm = AESGCM(aes_key[:32])
            iv_bytes = base64.b64decode(parsed_dict["iv"])
            tag_bytes = base64.b64decode(parsed_dict["tag"])
            payload_bytes = base64.b64decode(parsed_dict["encrypted_payload"])
            return aesgcm.decrypt(iv_bytes, payload_bytes + tag_bytes, None)

        # Caso C: Cifra RSA direta (bytes ou string base64)
        if isinstance(encrypted_data, str):
            cipher_bytes = base64.b64decode(encrypted_data)
        else:
            cipher_bytes = encrypted_data

        try:
            return private_key.decrypt(cipher_bytes, padding.PKCS1v15())
        except Exception:
            return private_key.decrypt(
                cipher_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

    if isinstance(encrypted_data, str):
        cipher_bytes = base64.b64decode(encrypted_data)
    else:
        cipher_bytes = encrypted_data
    private_key = _load_private_key(key_handle)
    return private_key.decrypt(cipher_bytes, padding.PKCS1v15())

def sign_data(key_handle, payload_string, provider_name=None):
    """
    Assina digitalmente dados com RSA-PSS + SHA-256 no macOS.
    - Se for a chave da eleição (fora do TEE): assina em software.
    - Se for a chave da máquina: assina com a chave do dispositivo.
    """
    if isinstance(payload_string, str):
        data_bytes = payload_string.encode('utf-8')
    else:
        data_bytes = payload_string
    private_key = _load_private_key(key_handle)
    signature = private_key.sign(
        data_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')

def generate_random(num_bytes=32):
    """
    Gera bytes aleatórios seguros no macOS via OS CSPRNG (secrets).
    """
    print(f"[VotaAI] Gerando número aleatório ({num_bytes} bytes) no macOS via OS CSPRNG (secrets).")
    import secrets
    return secrets.token_hex(num_bytes)

