import json
import socket
import threading
import urllib.request
import urllib.error
from urllib.parse import urlparse
from decouple import config
from app.controllers.encryptionController import EncryptionController

class HttpClient:
    _auth_token_lock = threading.Lock()
    _auth_token: str | None = None
    UNAUTHENTICATED_ROUTE_PREFIXES = ("/api/auth/login", "/api/admin/pre-registration")

    @classmethod
    def set_auth_token(cls, token: str | None) -> None:
        with cls._auth_token_lock:
            clean = (token or "").strip()
            cls._auth_token = clean or None

    @classmethod
    def get_auth_token(cls) -> str | None:
        with cls._auth_token_lock:
            return cls._auth_token

    @classmethod
    def clear_auth_token(cls) -> None:
        with cls._auth_token_lock:
            cls._auth_token = None

    def __init__(self, timeout=30):
        self.encryption_controller = EncryptionController()
        self.timeout = timeout
        self.base_url = config('API_BASE_URL', default='http://127.0.0.1:8000').rstrip('/')
        self.language = config('API_LANGUAGE', default='pt-br')

    def post(self, endpoint, payload, custom_headers=None, timeout=None):
        url = endpoint if endpoint.startswith('http') else f"{self.base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
        path = urlparse(url).path
        headers = {
            'Content-Type': 'application/json',
            'Accept-Language': self.language,
        }
        has_custom_auth = bool(
            custom_headers and any(k.lower() == 'authorization' for k in custom_headers.keys())
        )
        if not has_custom_auth and not path.startswith(self.UNAUTHENTICATED_ROUTE_PREFIXES):
            auth_token = self.get_auth_token()
            if auth_token:
                headers['Authorization'] = f'Token {auth_token}'
        if custom_headers:
            headers.update(custom_headers)
            
        req_timeout = timeout if timeout is not None else self.timeout

        # Criptografa o payload (Sign-then-Encrypt). A machine_public_key é injetada em todas as requisições.
        try:
            encrypted_payload = self.encryption_controller.encrypt_payload(payload)
        except Exception as e:
            print(f"Erro ao criptografar o payload: {e}")
            return {"status": "erro", "mensagem": f"Erro interno de criptografia antes do envio: {str(e)}"}
            
        data = json.dumps(encrypted_payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        print(f"[HttpClient] Enviando POST para {url}...")
        
        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as response:
                result_str = response.read().decode('utf-8')
                print(f"[HttpClient] Resposta recebida de {url} (HTTP {response.status}): {result_str}")
                try:
                    decrypted_result = self.encryption_controller.decrypt_response(
                        result_str, require_encrypted=True
                    )
                    print(f"[HttpClient] Resposta descriptografada com sucesso: {decrypted_result}")
                    return {"status": "sucesso", "dados": decrypted_result}
                except Exception as de:
                    print(f"[HttpClient] Falha ao validar/descriptografar resposta: {de}")
                    return {
                        "status": "erro",
                        "mensagem": f"Falha de segurança: não foi possível validar ou descriptografar a resposta do servidor ({de}).",
                    }
        except TimeoutError:
            print(f"[HttpClient] Timeout ao aguardar resposta de {url}")
            return {"status": "erro", "mensagem": "O servidor demorou muito para responder (tempo limite esgotado)."}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"[HttpClient] HTTPError {e.code} de {url}: {error_body}")
            try:
                try:
                    decrypted = self.encryption_controller.decrypt_response(error_body)
                    print(f"[HttpClient] HTTPError descriptografado: {decrypted}")
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
                print(f"[HttpClient] URLError Timeout para {url}")
                return {"status": "erro", "mensagem": "O servidor demorou muito para responder (tempo limite esgotado)."}
            print(f"[HttpClient] Erro de conexão na requisição POST para {url}: {e}")
            return {"status": "erro", "mensagem": f"Erro de conexão: {str(e.reason if hasattr(e, 'reason') else e)}"}
        except Exception as e:
            print(f"[HttpClient] Erro inesperado na requisição POST para {url}: {e}")
            return {"status": "erro", "mensagem": str(e)}

