import json
from app.services.http_client import HttpClient

class ElectionApiService:
    def __init__(self, auth_service, base_url="https://api.votaai.exemplo.com"):
        self.base_url = base_url
        self.http_client = HttpClient()
        self.auth_service = auth_service

    def enviar_eleicao(self, payload):
        """
        Envia o payload da eleição assinado e autenticado para a API externa.
        """
        # 1. Transformar payload em string (ordenado para manter consistência no hash/assinatura)
        payload_str = json.dumps(payload, sort_keys=True)
        
        signature = ""
        # 2. Assinar se o dispositivo já estiver registrado (possui key_handle)
        if self.auth_service.key_handle:
            signature = self.auth_service.crypto_controller.sign_data(
                self.auth_service.key_handle, 
                payload_str
            )
            
        # 3. Cabeçalhos de segurança
        headers = {
            "Authorization": f"Bearer {self.auth_service.jwt_token}",
            "X-Device-Signature": str(signature),
            "X-Device-ID": self.auth_service.device_service.get_device_id()
        }
        
        url = f"{self.base_url}/eleicoes"
        return self.http_client.post(url, payload, custom_headers=headers)
