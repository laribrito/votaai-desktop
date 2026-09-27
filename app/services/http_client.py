import json
import socket
import urllib.request
import urllib.error
from decouple import config
from app.controllers.encryptionController import EncryptionController

class HttpClient:
    def __init__(self, timeout=30):
        self.encryption_controller = EncryptionController()
        self.timeout = timeout
        self.base_url = config('API_BASE_URL', default='http://127.0.0.1:8000').rstrip('/')

    def post(self, endpoint, payload, custom_headers=None, timeout=None, include_public_key=False):
        url = endpoint if endpoint.startswith('http') else f"{self.base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
        headers = {'Content-Type': 'application/json'}
        if custom_headers:
            headers.update(custom_headers)
            
        req_timeout = timeout if timeout is not None else self.timeout

        # Criptografa o payload (Sign-then-Encrypt).
        # include_public_key=True apenas nas rotas de registro, onde o servidor ainda não possui a chave do cliente.
        try:
            encrypted_payload = self.encryption_controller.encrypt_payload(payload, include_public_key=include_public_key)
        except Exception as e:
            print(f"Erro ao criptografar o payload: {e}")
            return {"status": "erro", "mensagem": f"Erro interno de criptografia antes do envio: {str(e)}"}
            
        data = json.dumps(encrypted_payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as response:
                result_str = response.read().decode('utf-8')
                try:
                    decrypted_result = self.encryption_controller.decrypt_response(result_str)
                    return {"status": "sucesso", "dados": decrypted_result}
                except Exception as de:
                    print(f"Erro ao descriptografar resposta: {de}")
                    return {"status": "sucesso", "dados": result_str}
        except TimeoutError:
            return {"status": "erro", "mensagem": "O servidor demorou muito para responder (tempo limite esgotado)."}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                try:
                    decrypted = self.encryption_controller.decrypt_response(error_body)
                    error_body = decrypted
                except Exception:
                    pass

                if isinstance(error_body, str):
                    try:
                        error_json = json.loads(error_body)
                    except Exception:
                        error_json = error_body
                else:
                    error_json = error_body

                if isinstance(error_json, dict):
                    mensagem = error_json
                else:
                    mensagem = str(error_body)
            except Exception:
                mensagem = error_body
            return {"status": "erro", "mensagem": mensagem}
        except urllib.error.URLError as e:
            if isinstance(getattr(e, 'reason', None), (socket.timeout, TimeoutError)):
                return {"status": "erro", "mensagem": "O servidor demorou muito para responder (tempo limite esgotado)."}
            print(f"Erro de conexão na requisição POST para {url}: {e}")
            return {"status": "erro", "mensagem": f"Erro de conexão: {str(e.reason if hasattr(e, 'reason') else e)}"}
        except Exception as e:
            print(f"Erro inesperado na requisição POST para {url}: {e}")
            return {"status": "erro", "mensagem": str(e)}

