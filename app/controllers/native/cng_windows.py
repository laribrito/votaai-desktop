import os
import sys
import json
import base64
import hashlib
import ctypes
from ctypes import wintypes

# NCrypt API constants
NCRYPT_OVERWRITE_KEY_FLAG = 0x00000080
NCRYPT_PERSIST_FLAG = 0x80000000
NCRYPT_PAD_PKCS1_FLAG = 0x00000002
BCRYPT_RSAPUBLIC_BLOB = "RSAPUBLICBLOB"
NCRYPT_EXPORT_POLICY_PROPERTY = "Export Policy"
NCRYPT_ALLOW_EXPORT_NONE = 0

class BCRYPT_PKCS1_PADDING_INFO(ctypes.Structure):
    _fields_ = [("pszAlgId", wintypes.LPCWSTR)]

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

def generate_key():
    """Gera chave no hardware compatível com interface legada."""
    info = generate_rsa_key("votaai_desktop_hw_key")
    return info.get("PublicKeyBase64"), info.get("KeyName")

def decrypt_data(key_handle, encrypted_data, provider_name="Microsoft Platform Crypto Provider"):
    """
    Descriptografa dados usando a chave privada residente no Secure Element / TPM via NCryptDecrypt.
    """
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
    Assina digitalmente dados com a chave privada residente no TPM via NCryptSignHash.
    Retorna a assinatura em Base64.
    """
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

        pad_info = BCRYPT_PKCS1_PADDING_INFO(pszAlgId="SHA256")
        cbResult = wintypes.DWORD(0)

        # 1. Consulta tamanho da assinatura
        status = ncrypt.NCryptSignHash(hKey, ctypes.byref(pad_info), digest_arr, len(digest), None, 0, ctypes.byref(cbResult), NCRYPT_PAD_PKCS1_FLAG)
        if status != 0:
            raise RuntimeError(f"NCryptSignHash size check falhou: {hex(status & 0xFFFFFFFF)}")

        sig_arr = (ctypes.c_ubyte * cbResult.value)()
        # 2. Executa a assinatura com o hardware
        status = ncrypt.NCryptSignHash(hKey, ctypes.byref(pad_info), digest_arr, len(digest), sig_arr, cbResult.value, ctypes.byref(cbResult), NCRYPT_PAD_PKCS1_FLAG)
        if status != 0:
            raise RuntimeError(f"NCryptSignHash falhou: {hex(status & 0xFFFFFFFF)}")

        return base64.b64encode(bytes(sig_arr[:cbResult.value])).decode('utf-8')
    finally:
        if hKey.value:
            ncrypt.NCryptFreeObject(hKey)
        if hProv.value:
            ncrypt.NCryptFreeObject(hProv)


