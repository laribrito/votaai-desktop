import sys

class CryptoController:
    def __init__(self):
        self.backend = self._load_backend()

    def _load_backend(self):
        platform = sys.platform
        if platform.startswith('linux'):
            from .native import tpm_linux as backend
        elif platform == 'win32':
            from .native import cng_windows as backend
        elif platform == 'darwin':
            from .native import enclave_mac as backend
        else:
            raise RuntimeError(f"Plataforma não suportada: {platform}")
        return backend

    def generate_hardware_keys(self):
        """Gera chaves ECC (P-256) no hardware seguro da máquina e retorna (chave_publica, key_handle)."""
        return self.backend.generate_key()

    def decrypt_with_hardware(self, key_handle, encrypted_data):
        """Usa a chave privada armazenada no hardware (referenciada pelo key_handle) para descriptografar os dados."""
        return self.backend.decrypt_data(key_handle, encrypted_data)
