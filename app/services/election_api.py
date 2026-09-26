import json
from decouple import config
from app.services.http_client import HttpClient

class ElectionApiService:
    def __init__(self):
        self.http_client = HttpClient()

    def enviar_eleicao(self, payload):
        """
        Envia o payload da eleição para o backend em /api/election/create/.
        O HttpClient automaticamente encapsula a requisição no envelope
        criptográfico híbrido AES-GCM + RSA do TPM.
        """
        endpoint = "/api/election/create/"
        return self.http_client.post(endpoint, payload)

