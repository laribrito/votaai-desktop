from PySide6.QtCore import QSettings

class AuthService:
    def __init__(self, crypto_controller, device_service, http_client):
        self.crypto_controller = crypto_controller
        self.device_service = device_service
        self.http_client = http_client
        self.jwt_token = None
        
        self.settings = QSettings("VotaAi", "DesktopApp")
        self.key_handle = self._load_key_handle()

    def _load_key_handle(self):
        return self.settings.value("device/key_handle", None)

    def _save_key_handle(self, key_handle):
        self.settings.setValue("device/key_handle", key_handle)
        self.key_handle = key_handle

    def login(self, username, password):
        """
        Faz o login na API e guarda o token (exemplo/mock)
        """
        # payload = {"username": username, "password": password}
        # result = self.http_client.post("API_URL/token/", payload)
        # self.jwt_token = result.get('access')
        self.jwt_token = "mock_jwt_token_12345"
        return True

    def register_device(self):
        """
        Gera as chaves de hardware, pega o device_id, e envia para a API Django.
        Salva o key_handle para uso futuro (assinaturas).
        """
        if not self.jwt_token:
            raise ValueError("Usuário precisa estar logado para registrar o dispositivo")
            
        public_key, key_handle = self.crypto_controller.generate_hardware_keys()
        device_id = self.device_service.get_device_id()
        
        payload = {
            "device_id": device_id,
            "public_key": public_key
        }
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        # MOCK da chamada real para a API:
        # response = self.http_client.post("API_URL/devices/register/", payload, custom_headers=headers)
        
        self._save_key_handle(key_handle)
        return True
