from app.services.http_client import HttpClient

class ElectionApiService:
    def __init__(self, base_url="https://api.votaai.exemplo.com"):
        self.base_url = base_url
        self.http_client = HttpClient()

    def enviar_eleicao(self, payload):
        """
        Envia o payload da eleição (com chave pública) para a API externa.
        """
        url = f"{self.base_url}/eleicoes"
        return self.http_client.post(url, payload)
