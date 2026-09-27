import sys

class CryptoController:
    def __init__(self):
        self.backend = self._load_backend()

    @staticmethod
    def get_backend():
        platform = sys.platform
        if platform.startswith('linux'):
            from .native import tpm_linux as backend
        elif platform == 'win32':
            from .native import cng_windows as backend
        elif platform == 'darwin':
            from .native import enclave_mac as backend
        else:
            from .native import tpm_linux as backend
        return backend

    def _load_backend(self):
        return self.get_backend()

    def generate_hardware_keys(self):
        """Gera chaves no hardware seguro da máquina e retorna (chave_publica, key_handle)."""
        return self.backend.generate_key()

    def generate_rsa_key(self, key_name="VotaAI_DesktopClient_Key"):
        """Gera uma chave RSA no Secure Element / TPM ou provedor seguro da plataforma."""
        return self.backend.generate_rsa_key(key_name)

    def decrypt_with_hardware(self, key_handle, encrypted_data, provider_name=None):
        """Usa a chave privada armazenada no hardware (referenciada pelo key_handle) para descriptografar os dados."""
        return self.backend.decrypt_data(key_handle, encrypted_data, provider_name=provider_name)

    def decrypt_data(self, key_handle, encrypted_data, provider_name=None):
        return self.backend.decrypt_data(key_handle, encrypted_data, provider_name=provider_name)

    def sign_data(self, key_handle, payload_string, provider_name=None):
        """
        Usa a chave privada armazenada no hardware (via key_handle) para 
        assinar digitalmente a string do payload.
        Retorna a assinatura em Base64.
        """
        return self.backend.sign_data(key_handle, payload_string, provider_name=provider_name)

    def generate_random(self, num_bytes=32):
        """
        Gera bytes aleatórios de alta entropia.
        Utiliza o RNG do TPM, se disponível, ou o OS random/secrets como fallback.
        Retorna string em hexadecimal.
        """
        if hasattr(self.backend, 'generate_random'):
            return self.backend.generate_random(num_bytes)
        import secrets
        return secrets.token_hex(num_bytes)
