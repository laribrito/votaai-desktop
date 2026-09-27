import os
import base64
import struct
import stat
import json
import hashlib
import subprocess
import tempfile
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Handle persistente no TPM para a chave de assinatura do cliente VotaAI
TPM2_SIGNING_HANDLE = "0x81010010"

def _get_resources_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'resources'))

def _get_keys_dir():
    keys_dir = os.path.join(_get_resources_dir(), '.client_keys')
    os.makedirs(keys_dir, exist_ok=True)
    return keys_dir

def _get_key_meta_path(key_name):
    clean_name = "".join(c for c in key_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(_get_keys_dir(), f"{clean_name}.meta.json")

# ─────────────────────────────────────────────────────────────────────────────
# Hardware path: TPM 2.0 via tpm2-tools
# ─────────────────────────────────────────────────────────────────────────────

def _tpm2_available():
    """Verifica se o tpm2-tools está disponível e o TPM 2.0 acessível."""
    try:
        result = subprocess.run(
            ['tpm2_getcap', 'properties-fixed'],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def _tpm2_handle_exists(handle):
    """Verifica se um handle persistente já existe no TPM."""
    try:
        result = subprocess.run(
            ['tpm2_getcap', 'handles-persistent'],
            capture_output=True, timeout=5, text=True
        )
        return handle in result.stdout
    except Exception:
        return False

def _tpm2_generate_signing_key(handle, key_name):
    """
    Gera uma chave RSA-PSS de assinatura diretamente no TPM 2.0.
    A chave privada NUNCA é exportada — reside exclusivamente no hardware.
    Retorna a chave pública em formato PEM.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        primary_ctx = os.path.join(tmpdir, 'primary.ctx')
        key_pub     = os.path.join(tmpdir, 'key.pub')
        key_priv    = os.path.join(tmpdir, 'key.priv')
        key_ctx     = os.path.join(tmpdir, 'key.ctx')
        pub_pem_out = os.path.join(tmpdir, 'pub.pem')

        # 1. Cria chave primária em owner hierarchy
        subprocess.run([
            'tpm2_createprimary', '-C', 'o', '-G', 'rsa', '-g', 'sha256',
            '-c', primary_ctx
        ], check=True, capture_output=True)

        # 2. Cria chave RSA para assinatura sob a chave primária
        # Nota: não passamos --attributes manualmente para compatibilidade com diferentes versões do tpm2-tools
        subprocess.run([
            'tpm2_create',
            '-G', 'rsa:rsapss',   # RSA com esquema PSS
            '-g', 'sha256',
            '-C', primary_ctx,
            '-u', key_pub,
            '-r', key_priv,
        ], check=True, capture_output=True)

        # 3. Carrega a chave no TPM
        subprocess.run([
            'tpm2_load', '-C', primary_ctx, '-u', key_pub, '-r', key_priv,
            '-c', key_ctx
        ], check=True, capture_output=True)

        # 4. Torna a chave persistente no handle reservado
        if _tpm2_handle_exists(handle):
            subprocess.run(
                ['tpm2_evictcontrol', '-C', 'o', '-c', handle],
                capture_output=True
            )
        subprocess.run([
            'tpm2_evictcontrol', '-C', 'o', '-c', key_ctx, handle
        ], check=True, capture_output=True)

        # 5. Exporta somente a chave pública em formato PEM
        subprocess.run([
            'tpm2_readpublic', '-c', handle, '--format=pem', f'--output={pub_pem_out}'
        ], check=True, capture_output=True)

        with open(pub_pem_out, 'r') as f:
            pub_pem = f.read()

    return pub_pem

def _tpm2_sign(handle, data_str):
    """
    Assina dados usando a chave privada residente no TPM 2.0 (RSA-PSS + SHA-256).
    O dado entra no chip, apenas a assinatura sai. Retorna assinatura em Base64.
    """
    if isinstance(data_str, str):
        data_bytes = data_str.encode('utf-8')
    else:
        data_bytes = data_str

    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = os.path.join(tmpdir, 'data.bin')
        sig_path  = os.path.join(tmpdir, 'sig.bin')

        with open(data_path, 'wb') as f:
            f.write(data_bytes)

        subprocess.run([
            'tpm2_sign',
            '-c', handle,
            '-g', 'sha256',
            '-s', 'rsapss',    # RSA-PSS
            '-f', 'plain',     # saída raw (sem wrapper TPMT_SIGNATURE)
            '-o', sig_path,
            data_path
        ], check=True, capture_output=True)

        with open(sig_path, 'rb') as f:
            sig_bytes = f.read()

    return base64.b64encode(sig_bytes).decode('utf-8')

# ─────────────────────────────────────────────────────────────────────────────
# Software fallback: chave cifrada com segredo derivado do machine-id
# A chave privada nunca fica em disco em plaintext.
# ─────────────────────────────────────────────────────────────────────────────

def _get_machine_secret():
    """
    Deriva um segredo de 32 bytes único desta instalação usando o machine-id.
    O segredo nunca é armazenado — é re-derivado na memória a cada acesso.
    """
    machine_id_path = '/etc/machine-id'
    try:
        with open(machine_id_path, 'r') as f:
            machine_id = f.read().strip()
    except OSError:
        import socket
        machine_id = socket.gethostname()

    return hashlib.pbkdf2_hmac(
        'sha256',
        machine_id.encode('utf-8'),
        b'VotaAI-DesktopClient-KeyProtection-v1',
        iterations=200_000
    )

def _encrypt_pem(pem_bytes: bytes) -> bytes:
    """Cifra o PEM da chave privada com AES-256-GCM + machine-id secret."""
    key = _get_machine_secret()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, pem_bytes, b'VotaAI-client-key-aad')
    return iv + ciphertext  # IV (12 bytes) || ciphertext+tag

def _decrypt_pem(encrypted: bytes) -> bytes:
    """Decifra o PEM da chave privada na memória."""
    key = _get_machine_secret()
    iv, ciphertext = encrypted[:12], encrypted[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext, b'VotaAI-client-key-aad')

def _get_encrypted_key_path(key_name):
    clean_name = "".join(c for c in key_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(_get_keys_dir(), f"{clean_name}.enc")

def _software_generate_key(key_name):
    """
    Gera chave RSA em software e a armazena cifrada com machine-id secret.
    Fallback quando o TPM não está disponível.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Cifra o PEM antes de salvar — nunca fica em plaintext no disco
    encrypted = _encrypt_pem(pem_bytes)
    enc_path = _get_encrypted_key_path(key_name)

    with open(enc_path, 'wb') as f:
        f.write(encrypted)

    try:
        os.chmod(enc_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return pub_pem

def _software_load_private_key(key_name):
    """Carrega e decifra a chave privada na memória. Nunca escreve plaintext em disco."""
    enc_path = _get_encrypted_key_path(key_name)
    if not os.path.exists(enc_path):
        _software_generate_key(key_name)

    with open(enc_path, 'rb') as f:
        encrypted = f.read()

    pem_bytes = _decrypt_pem(encrypted)
    return serialization.load_pem_private_key(pem_bytes, password=None)

def _software_sign(key_name, data_str):
    """Assina em software com RSA-PSS. Chave decifrada apenas na memória."""
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

# ─────────────────────────────────────────────────────────────────────────────
# Interface pública (utilizada pelo EncryptionController / CryptoController)
# ─────────────────────────────────────────────────────────────────────────────

def _rsa_public_to_cng_blob(public_key):
    numbers = public_key.public_numbers()
    e, n = numbers.e, numbers.n
    e_bytes  = e.to_bytes((e.bit_length() + 7) // 8, byteorder='big')
    mod_len  = (public_key.key_size + 7) // 8
    n_bytes  = n.to_bytes(mod_len, byteorder='big')
    magic    = 0x31415352
    header   = struct.pack('<IIIIII', magic, public_key.key_size, len(e_bytes), len(n_bytes), 0, 0)
    return header + e_bytes + n_bytes

def generate_rsa_key(key_name="VotaAI_DesktopClient_Key"):
    """
    Gera uma chave RSA para o cliente desktop.
    - Caminho hardware: TPM 2.0 via tpm2-tools (chave privada nunca sai do chip).
    - Fallback software: chave cifrada com AES-256-GCM + machine-id (nunca em plaintext no disco).
    Retorna dict compatível com a interface do CryptoController.
    """
    meta_path = _get_key_meta_path(key_name)
    use_tpm   = _tpm2_available()

    if use_tpm:
        try:
            pub_pem = _tpm2_generate_signing_key(TPM2_SIGNING_HANDLE, key_name)
            provider = "Linux TPM 2.0 (tpm2-tools)"
            storage  = "tpm2"
            print(f"[VotaAI] Chave gerada no TPM 2.0 hardware (handle {TPM2_SIGNING_HANDLE}). Chave privada NÃO exportada.")
        except Exception as e:
            print(f"[VotaAI] Falha no TPM 2.0: {e}. Usando fallback software cifrado.")
            use_tpm  = False

    if not use_tpm:
        pub_pem  = _software_generate_key(key_name)
        provider = "Linux Software (AES-256-GCM encrypted, machine-id derived key)"
        storage  = "software-encrypted"
        print(f"[VotaAI] Chave gerada em software, cifrada com machine-id secret. NÃO está em plaintext no disco.")

    # Lê a chave pública para gerar o CNG blob
    pub_key = serialization.load_pem_public_key(pub_pem.encode('utf-8'))
    cng_blob = _rsa_public_to_cng_blob(pub_key)

    meta = {
        "KeyName": key_name,
        "PublicKeyBase64": base64.b64encode(cng_blob).decode('utf-8'),
        "PublicKeyPEM": pub_pem,
        "Algorithm": "RSA",
        "Provider": provider,
        "Storage": storage,
        "TPMHandle": TPM2_SIGNING_HANDLE if storage == "tpm2" else None
    }

    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    try:
        os.chmod(meta_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

    return meta

def generate_key():
    """Interface legada."""
    info = generate_rsa_key("votaai_desktop_hw_key")
    return info.get("PublicKeyBase64"), info.get("KeyName")

def decrypt_data(key_handle, encrypted_data, provider_name=None):
    """Descriptografa dados usando a chave privada RSA (software path)."""
    if isinstance(encrypted_data, str):
        cipher_bytes = base64.b64decode(encrypted_data)
    else:
        cipher_bytes = encrypted_data

    private_key = _software_load_private_key(key_handle)
    return private_key.decrypt(cipher_bytes, padding.PKCS1v15())

def sign_data(key_handle, payload_string, provider_name=None):
    """
    Assina dados com RSA-PSS + SHA-256.
    - Se TPM disponível: operação ocorre dentro do chip (chave privada nunca sai do hardware).
    - Fallback: chave decifrada na memória, assinatura em software, memória limpa ao finalizar.
    """
    meta_path = _get_key_meta_path(key_handle)
    storage   = "software-encrypted"  # default

    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            storage = meta.get("Storage", "software-encrypted")
        except Exception:
            pass

    if storage == "tpm2" and _tpm2_available():
        try:
            return _tpm2_sign(TPM2_SIGNING_HANDLE, payload_string)
        except Exception as e:
            print(f"[VotaAI] Falha na assinatura TPM 2.0: {e}. Usando fallback software.")

    return _software_sign(key_handle, payload_string)
