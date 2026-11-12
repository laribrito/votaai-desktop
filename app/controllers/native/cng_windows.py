import os
import sys
import json
import base64
import hashlib
import struct
import stat
import ctypes
from ctypes import wintypes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# NCrypt API constants
NCRYPT_OVERWRITE_KEY_FLAG = 0x00000080
NCRYPT_PERSIST_FLAG = 0x80000000
NCRYPT_PAD_PKCS1_FLAG = 0x00000002
NCRYPT_PAD_PSS_FLAG   = 0x00000008
BCRYPT_RSAPUBLIC_BLOB = "RSAPUBLICBLOB"
NCRYPT_EXPORT_POLICY_PROPERTY = "Export Policy"
NCRYPT_ALLOW_EXPORT_NONE = 0

class BCRYPT_PKCS1_PADDING_INFO(ctypes.Structure):
    _fields_ = [("pszAlgId", wintypes.LPCWSTR)]

class BCRYPT_PSS_PADDING_INFO(ctypes.Structure):
    _fields_ = [
        ("pszAlgId", wintypes.LPCWSTR),
        ("cbSalt",   wintypes.ULONG)
    ]

ncrypt = None

if sys.platform == 'win32':
    try:
        ncrypt = ctypes.windll.ncrypt

        # NCryptOpenStorageProvider
        ncrypt.NCryptOpenStorageProvider.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.LPCWSTR,
            wintypes.DWORD
        ]
        ncrypt.NCryptOpenStorageProvider.restype = wintypes.LONG

        # NCryptCreatePersistedKey
        ncrypt.NCryptCreatePersistedKey.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD
        ]
        ncrypt.NCryptCreatePersistedKey.restype = wintypes.LONG

        # NCryptSetProperty
        ncrypt.NCryptSetProperty.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.DWORD,
            wintypes.DWORD
        ]
        ncrypt.NCryptSetProperty.restype = wintypes.LONG

        # NCryptFinalizeKey
        ncrypt.NCryptFinalizeKey.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD
        ]
        ncrypt.NCryptFinalizeKey.restype = wintypes.LONG

        # NCryptExportKey
        ncrypt.NCryptExportKey.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD
        ]
        ncrypt.NCryptExportKey.restype = wintypes.LONG

        # NCryptOpenKey
        ncrypt.NCryptOpenKey.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD
        ]
        ncrypt.NCryptOpenKey.restype = wintypes.LONG

        # NCryptDecrypt
        ncrypt.NCryptDecrypt.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD
        ]
        ncrypt.NCryptDecrypt.restype = wintypes.LONG

        # NCryptSignHash
        ncrypt.NCryptSignHash.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD
        ]
        ncrypt.NCryptSignHash.restype = wintypes.LONG

        # NCryptFreeObject
        ncrypt.NCryptFreeObject.argtypes = [ctypes.c_void_p]
        ncrypt.NCryptFreeObject.restype = wintypes.LONG

    except Exception as e:
        print(f"Erro ao inicializar ncrypt.dll: {e}")

def _open_provider(preferred_provider="Microsoft Platform Crypto Provider"):
    if ncrypt is None:
        raise RuntimeError("ncrypt.dll não está disponível no sistema.")
    
    hProv = ctypes.c_void_p()
    status = ncrypt.NCryptOpenStorageProvider(ctypes.byref(hProv), preferred_provider, 0)
    if status == 0:
        return hProv, preferred_provider
    
    # Fallback para software se o hardware TPM não estiver disponível
    software_provider = "Microsoft Software Key Storage Provider"
    status = ncrypt.NCryptOpenStorageProvider(ctypes.byref(hProv), software_provider, 0)
    if status == 0:
        return hProv, software_provider
    
    raise RuntimeError(f"Falha ao abrir provedor CNG: {hex(status & 0xFFFFFFFF)}")

def generate_rsa_key(key_name="VotaAI_DesktopClient_Key"):
    """
    Gera uma chave privada RSA no Secure Element (TPM) via APIs nativas em C do Windows (CNG).
    A chave privada NUNCA é exportável e reside exclusivamente no hardware.
    """
    hProv, provider_name = _open_provider("Microsoft Platform Crypto Provider")
    hKey = ctypes.c_void_p()
    
    try:
        # 1. Cria a chave persistida
        status = ncrypt.NCryptCreatePersistedKey(hProv, ctypes.byref(hKey), "RSA", key_name, 0, NCRYPT_OVERWRITE_KEY_FLAG)
        if status != 0:
            raise RuntimeError(f"NCryptCreatePersistedKey falhou: {hex(status & 0xFFFFFFFF)}")

        # 2. Define a política de exportação como NENHUMA (0)
        export_policy = wintypes.DWORD(NCRYPT_ALLOW_EXPORT_NONE)
        export_policy_bytes = (ctypes.c_ubyte * 4).from_buffer_copy(export_policy)
        ncrypt.NCryptSetProperty(hKey, NCRYPT_EXPORT_POLICY_PROPERTY, export_policy_bytes, 4, NCRYPT_PERSIST_FLAG)

        # 3. Finaliza a criação da chave no hardware
        status = ncrypt.NCryptFinalizeKey(hKey, 0)
        if status != 0:
            raise RuntimeError(f"NCryptFinalizeKey falhou: {hex(status & 0xFFFFFFFF)}")

        # 4. Exporta a chave pública em formato BCRYPT_RSAPUBLIC_BLOB
        cbResult = wintypes.DWORD(0)
        status = ncrypt.NCryptExportKey(hKey, None, BCRYPT_RSAPUBLIC_BLOB, None, None, 0, ctypes.byref(cbResult), 0)
        if status != 0:
            raise RuntimeError(f"NCryptExportKey size check falhou: {hex(status & 0xFFFFFFFF)}")

        pub_arr = (ctypes.c_ubyte * cbResult.value)()
        status = ncrypt.NCryptExportKey(hKey, None, BCRYPT_RSAPUBLIC_BLOB, None, pub_arr, cbResult.value, ctypes.byref(cbResult), 0)
        if status != 0:
            raise RuntimeError(f"NCryptExportKey falhou: {hex(status & 0xFFFFFFFF)}")

        pub_bytes = bytes(pub_arr[:cbResult.value])

        return {
            "KeyName": key_name,
            "PublicKeyBase64": base64.b64encode(pub_bytes).decode('utf-8'),
            "Algorithm": "RSA",
            "Provider": provider_name
        }
    finally:
        if hKey.value:
            ncrypt.NCryptFreeObject(hKey)
        if hProv.value:
            ncrypt.NCryptFreeObject(hProv)

def _get_resources_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'resources'))

def _get_keys_dir():
    keys_dir = os.path.join(_get_resources_dir(), '.client_keys')
    os.makedirs(keys_dir, exist_ok=True)
    return keys_dir

def _get_key_meta_path(key_name):
    clean_name = "".join(c for c in key_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(_get_keys_dir(), f"{clean_name}.meta.json")

def _get_encrypted_key_path(key_name):
    clean_name = "".join(c for c in key_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(_get_keys_dir(), f"{clean_name}.enc")

def _get_machine_secret():
    import socket
    machine_id = socket.gethostname() or "votaai-windows-node"
    return hashlib.pbkdf2_hmac(
        'sha256',
        machine_id.encode('utf-8'),
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

def _software_generate_key(key_name):
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

    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    return pub_pem

def _software_load_private_key(key_name):
    enc_path = _get_encrypted_key_path(key_name)
    if not os.path.exists(enc_path):
        _software_generate_key(key_name)
    with open(enc_path, 'rb') as f:
        encrypted = f.read()
    pem_bytes = _decrypt_pem(encrypted)
    return serialization.load_pem_private_key(pem_bytes, password=None)

def _software_sign(key_name, data_str):
    if isinstance(data_str, str):
        data_bytes = data_str.encode('utf-8')
    else:
        data_bytes = data_str
    private_key = _software_load_private_key(key_name)
    signature = private_key.sign(
        data_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')

def _rsa_public_to_cng_blob(public_key: rsa.RSAPublicKey) -> bytes:
    numbers = public_key.public_numbers()
    e, n = numbers.e, numbers.n
    e_bytes = e.to_bytes((e.bit_length() + 7) // 8, byteorder='big')
    mod_len = (public_key.key_size + 7) // 8
    n_bytes = n.to_bytes(mod_len, byteorder='big')
    magic = 0x31415352
    header = struct.pack('<IIIIII', magic, public_key.key_size, len(e_bytes), len(n_bytes), 0, 0)
    return header + e_bytes + n_bytes

def generate_key():
    """
    Gera a chave da eleição fora do hardware seguro (TEE) para viabilizar a ação de apurar.
    A chave privada da eleição NUNCA é salva no chip TPM, permanecendo em software.
    """
    key_name = "votaai_desktop_hw_key"
    pub_pem = _software_generate_key(key_name)
    pub_key = serialization.load_pem_public_key(pub_pem.encode('utf-8'))
    cng_blob = _rsa_public_to_cng_blob(pub_key)
    meta_path = _get_key_meta_path(key_name)

    meta = {
        "KeyName": key_name,
        "PublicKeyBase64": base64.b64encode(cng_blob).decode('utf-8'),
        "PublicKeyPEM": pub_pem,
        "Algorithm": "RSA",
        "Provider": "Windows Software (AES-256-GCM encrypted, outside TEE)",
        "Storage": "software-encrypted",
        "TPMHandle": None
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    return meta.get("PublicKeyBase64"), meta.get("KeyName")

def decrypt_data(key_handle, encrypted_data, provider_name="Microsoft Platform Crypto Provider"):
    """
    Descriptografa dados usando a chave privada RSA.
    - Se for a chave da máquina (VotaAI_DesktopClient_Key): descriptografa diretamente no hardware via NCryptDecrypt.
    - Se for a chave da eleição (fora do TEE): descriptografa em software na memória RAM.
    """
    # Se for a chave da eleição (armazenada fora do TEE em software)
    if key_handle != "VotaAI_DesktopClient_Key":
        private_key = _software_load_private_key(key_handle)

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

        if parsed_dict and "pacote_cifrado" in parsed_dict:
            return decrypt_data(key_handle, parsed_dict["pacote_cifrado"], provider_name=provider_name)

        if parsed_dict and all(k in parsed_dict for k in ("encrypted_payload", "encrypted_aes_key", "iv", "tag")):
            enc_aes_key = base64.b64decode(parsed_dict["encrypted_aes_key"])
            aes_key = private_key.decrypt(enc_aes_key, padding.PKCS1v15())
            aesgcm = AESGCM(aes_key[:32])
            iv_bytes = base64.b64decode(parsed_dict["iv"])
            tag_bytes = base64.b64decode(parsed_dict["tag"])
            payload_bytes = base64.b64decode(parsed_dict["encrypted_payload"])
            return aesgcm.decrypt(iv_bytes, payload_bytes + tag_bytes, None)

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

    # Chave do cliente (residente no hardware TPM via CNG)
    if isinstance(encrypted_data, str):
        cipher_bytes = base64.b64decode(encrypted_data)
    else:
        cipher_bytes = encrypted_data

    hProv, _ = _open_provider(provider_name)
    hKey = ctypes.c_void_p()

    try:
        status = ncrypt.NCryptOpenKey(hProv, ctypes.byref(hKey), str(key_handle), 0, 0)
        if status != 0:
            raise RuntimeError(f"NCryptOpenKey falhou para chave '{key_handle}': {hex(status & 0xFFFFFFFF)}")

        cipher_arr = (ctypes.c_ubyte * len(cipher_bytes)).from_buffer_copy(cipher_bytes)
        cbResult = wintypes.DWORD(0)

        # 1. Consulta o tamanho necessário para o buffer de saída
        status = ncrypt.NCryptDecrypt(hKey, cipher_arr, len(cipher_bytes), None, None, 0, ctypes.byref(cbResult), NCRYPT_PAD_PKCS1_FLAG)
        if status != 0:
            raise RuntimeError(f"NCryptDecrypt size check falhou: {hex(status & 0xFFFFFFFF)}")

        output_arr = (ctypes.c_ubyte * cbResult.value)()
        # 2. Executa a descriptografia dentro do chip de hardware
        status = ncrypt.NCryptDecrypt(hKey, cipher_arr, len(cipher_bytes), None, output_arr, cbResult.value, ctypes.byref(cbResult), NCRYPT_PAD_PKCS1_FLAG)
        if status != 0:
            raise RuntimeError(f"NCryptDecrypt falhou: {hex(status & 0xFFFFFFFF)}")

        return bytes(output_arr[:cbResult.value])
    finally:
        if hKey.value:
            ncrypt.NCryptFreeObject(hKey)
        if hProv.value:
            ncrypt.NCryptFreeObject(hProv)

def sign_data(key_handle, payload_string, provider_name="Microsoft Platform Crypto Provider"):
    """
    Assina digitalmente dados com a chave privada RSA.
    - Se for a chave da eleição (fora do TEE): assina em software via _software_sign.
    - Se for a chave da máquina (no TPM): assina no chip TPM via NCryptSignHash (RSA-PSS).
    Retorna a assinatura em Base64.
    """
    if key_handle != "VotaAI_DesktopClient_Key":
        return _software_sign(key_handle, payload_string)

    if isinstance(payload_string, str):
        data_bytes = payload_string.encode('utf-8')
    else:
        data_bytes = payload_string

    digest = hashlib.sha256(data_bytes).digest()
    digest_arr = (ctypes.c_ubyte * len(digest)).from_buffer_copy(digest)

    hProv, _ = _open_provider(provider_name)
    hKey = ctypes.c_void_p()

    try:
        status = ncrypt.NCryptOpenKey(hProv, ctypes.byref(hKey), str(key_handle), 0, 0)
        if status != 0:
            raise RuntimeError(f"NCryptOpenKey falhou para chave '{key_handle}': {hex(status & 0xFFFFFFFF)}")

        # RSA-PSS: salt length = digest size (32 bytes para SHA-256)
        pad_info = BCRYPT_PSS_PADDING_INFO(pszAlgId="SHA256", cbSalt=32)
        cbResult = wintypes.DWORD(0)

        # 1. Consulta tamanho da assinatura
        status = ncrypt.NCryptSignHash(hKey, ctypes.byref(pad_info), digest_arr, len(digest), None, 0, ctypes.byref(cbResult), NCRYPT_PAD_PSS_FLAG)
        if status != 0:
            raise RuntimeError(f"NCryptSignHash (PSS) size check falhou: {hex(status & 0xFFFFFFFF)}")

        sig_arr = (ctypes.c_ubyte * cbResult.value)()
        # 2. Executa a assinatura PSS com o hardware
        status = ncrypt.NCryptSignHash(hKey, ctypes.byref(pad_info), digest_arr, len(digest), sig_arr, cbResult.value, ctypes.byref(cbResult), NCRYPT_PAD_PSS_FLAG)
        if status != 0:
            raise RuntimeError(f"NCryptSignHash (PSS) falhou: {hex(status & 0xFFFFFFFF)}")

        return base64.b64encode(bytes(sig_arr[:cbResult.value])).decode('utf-8')
    finally:
        if hKey.value:
            ncrypt.NCryptFreeObject(hKey)
        if hProv.value:
            ncrypt.NCryptFreeObject(hProv)

def generate_random(num_bytes=32):
    """
    Gera bytes aleatórios seguros no Windows.
    """
    print(f"[VotaAI] Gerando número aleatório ({num_bytes} bytes) no Windows via CSPRNG (secrets).")
    import secrets
    return secrets.token_hex(num_bytes)


