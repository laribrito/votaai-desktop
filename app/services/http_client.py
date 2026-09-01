import json
import urllib.request
import urllib.error
from app.services.encryption_service import EncryptionService

class HttpClient:
    def __init__(self):
        self.encryption_service = EncryptionService()

    def post(self, url, payload, custom_headers=None):
        headers = {'Content-Type': 'application/json'}
        if custom_headers:
            headers.update(custom_headers)
            
        # Criptografa o payload para todas as requisições
        try:
            encrypted_payload = self.encryption_service.encrypt_payload(payload)
        except Exception as e:
            print(f"Erro ao criptografar o payload: {e}")
            return {"status": "erro", "mensagem": f"Erro interno de criptografia antes do envio: {str(e)}"}
            
        data = json.dumps(encrypted_payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                result_str = response.read().decode('utf-8')
                try:
                    decrypted_result = self.encryption_service.decrypt_response(result_str)
                    return {"status": "sucesso", "dados": decrypted_result}
                except Exception as de:
                    print(f"Erro ao descriptografar resposta: {de}")
                    return {"status": "sucesso", "dados": result_str}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                try:
                    error_body = self.encryption_service.decrypt_response(error_body)
                except Exception:
                    pass
                if isinstance(error_body, str):
                    error_json = json.loads(error_body)
                else:
                    error_json = error_body
                mensagem = error_json.get('error', error_body) if isinstance(error_json, dict) else error_body
            except Exception:
                mensagem = error_body
            return {"status": "erro", "mensagem": mensagem}
        except urllib.error.URLError as e:
            print(f"Erro de conexão na requisição POST para {url}: {e}")
            return {"status": "erro", "mensagem": str(e.reason if hasattr(e, 'reason') else e)}
        except Exception as e:
            print(f"Erro inesperado na requisição POST para {url}: {e}")
            return {"status": "erro", "mensagem": str(e)}
