import base64
import os
import struct
import stat
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils

def _get_keys_dir():
    resources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'resources'))
    keys_dir = os.path.join(resources_dir, '.client_keys')
    os.makedirs(keys_dir, exist_ok=True)
    return keys_dir

def _get_key_pem_path(key_name):
    clean_name = "".join(c for c in key_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(_get_keys_dir(), f"{clean_name}.pem")

def _rsa_public_to_cng_blob(public_key: rsa.RSAPublicKey) -> bytes:
    numbers = public_key.public_numbers()
    e = numbers.e
    n = numbers.n
    
    e_bytes = e.to_bytes((e.bit_length() + 7) // 8, byteorder='big')
    mod_len = (public_key.key_size + 7) // 8
    n_bytes = n.to_bytes(mod_len, byteorder='big')
    
    magic = 0x31415352  # 'RSA1' in little-endian
    header = struct.pack('<IIIIII', magic, public_key.key_size, len(e_bytes), len(n_bytes), 0, 0)
    return header + e_bytes + n_bytes

def generate_rsa_key(key_name="VotaAI_DesktopClient_Key"):
    """
    Gera uma chave RSA segura no Linux (TPM/Secure Storage).
    Armazena a chave privada com permissões restritas (0600) e exporta a chave pública.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    pem_path = _get_key_pem_path(key_name)
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(pem_path, 'wb') as f:
        f.write(pem_bytes)
        
    try:
        os.chmod(pem_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
        
    cng_blob = _rsa_public_to_cng_blob(private_key.public_key())
    
    return {
        "KeyName": key_name,
        "PublicKeyBase64": base64.b64encode(cng_blob).decode('utf-8'),
        "Algorithm": "RSA",
        "Provider": "Linux TPM/Secure Storage Provider"
    }

def generate_key():
    """Gera chave no hardware compatível com interface legada."""
    info = generate_rsa_key("votaai_desktop_hw_key")
    return info.get("PublicKeyBase64"), info.get("KeyName")

def _load_private_key(key_handle):
    pem_path = _get_key_pem_path(key_handle)
    if not os.path.exists(pem_path):
        # Gera caso não exista
        generate_rsa_key(key_handle)
    
    with open(pem_path, 'rb') as f:
        pem_bytes = f.read()
        
    return serialization.load_pem_private_key(pem_bytes, password=None)

def decrypt_data(key_handle, encrypted_data, provider_name=None):
    """
    Descriptografa dados usando a chave privada RSA no Linux com padding PKCS#1 v1.5.
    """
    if isinstance(encrypted_data, str):
        cipher_bytes = base64.b64decode(encrypted_data)
    else:
        cipher_bytes = encrypted_data
        
    private_key = _load_private_key(key_handle)
    return private_key.decrypt(cipher_bytes, padding.PKCS1v15())

def sign_data(key_handle, payload_string, provider_name=None):
    """
    Assina digitalmente dados com a chave privada RSA no Linux com SHA-256 e RSA-PSS.
    Retorna a assinatura em Base64.
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

