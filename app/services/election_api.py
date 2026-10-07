import json
from decouple import config
from app.services.http_client import HttpClient
from app.services.api_routes import API_ROUTES

class ElectionApiService:
    def __init__(self):
        self.http_client = HttpClient()

    def enviar_eleicao(self, payload):
        """
        Envia o payload da eleição para o backend em /api/election/create/.
        O HttpClient automaticamente encapsula a requisição no envelope
        criptográfico híbrido AES-GCM + RSA do TPM.
        """
        endpoint = API_ROUTES["election"]["create"]
        return self.http_client.post(endpoint, payload, include_public_key=True)

