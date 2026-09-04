import os
import io
import json
import base64
import urllib.parse
from datetime import datetime
from PySide6.QtCore import QObject, Slot, Signal, Property
from PySide6.QtGui import QGuiApplication
from decouple import config

from app.controllers.native import cng_windows
from app.services.http_client import HttpClient
import qrcode

class AuthController(QObject):
    """
    Controlador para gerenciar o pré-cadastro do usuário administrador
    com provisionamento de chave RSA segura no hardware TPM e segundo fator TOTP.
    """
    registrationStatusChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.http_client = HttpClient()
        self.api_base_url = config('API_BASE_URL', default='http://127.0.0.1:8000').rstrip('/')
        self.resources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources'))
        os.makedirs(self.resources_dir, exist_ok=True)

    def _get_registration_path(self):
        return os.path.join(self.resources_dir, 'registration_info.json')

    def _read_registration_data(self):
        reg_path = self._get_registration_path()
        if os.path.exists(reg_path):
            try:
                with open(reg_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao ler registration_info.json: {e}")
        return {}

    @Property(bool, notify=registrationStatusChanged)
    def isRegistered(self):
        data = self._read_registration_data()
        return bool(data.get("is_registered", False))

    @Property(str, notify=registrationStatusChanged)
    def registeredEmail(self):
        data = self._read_registration_data()
        return data.get("email", "")

    @Slot(str)
    def copyToClipboard(self, text: str):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    @Slot(str, str, result=str)
    def iniciarPreCadastro(self, email: str, senha: str) -> str:
        """
        Passo 1 do fluxo:
        - Valida credenciais locais
        - Gera novo par de chaves RSA no Secure Element (TPM)
        - Envia requisição cifrada para POST /api/admin/pre-cadastro/
        - Recebe uri_provisionamento e gera QR Code para autenticador
        """
        email = (email or '').strip()
        senha = (senha or '').strip()

        if not email:
            return json.dumps({"status": "erro", "mensagem": "O e-mail é obrigatório."})
        if not senha:
            return json.dumps({"status": "erro", "mensagem": "A senha é obrigatória."})
        if len(senha) < 8:
            return json.dumps({"status": "erro", "mensagem": "A senha deve conter no mínimo 8 caracteres com letras, números e símbolos."})

        try:
            # 1. Gera ou atualiza chave no hardware TPM da máquina
            key_info = cng_windows.generate_rsa_key("VotaAI_DesktopClient_Key")
            client_key_path = os.path.join(self.resources_dir, 'client_key.json')
            with open(client_key_path, 'w', encoding='utf-8') as f:
                json.dump(key_info, f, indent=4)

            # Recarrega a chave pública no serviço de criptografia do http_client
            _, client_pub_pem = self.http_client.encryption_service.reload_client_keys()

            # 2. Envia para o backend (o HttpClient automaticamente envia o envelope cifrado híbrido)
            url = f"{self.api_base_url}/api/admin/pre-cadastro/"
            payload = {
                "email": email,
                "senha": senha,
                "chave_publica_maquina": client_pub_pem
            }

            response = self.http_client.post(url, payload)

            if response.get("status") != "sucesso":
                msg = response.get("mensagem", "Erro ao iniciar pré-cadastro no servidor.")
                if isinstance(msg, dict):
                    parts = []
                    for k, v in msg.items():
                        if isinstance(v, list):
                            parts.append(f"{k.capitalize()}: {'; '.join(str(x) for x in v)}")
                        else:
                            parts.append(f"{k.capitalize()}: {v}")
                    msg = " ".join(parts)
                return json.dumps({"status": "erro", "mensagem": str(msg)})

            dados = response.get("dados", {})
            if isinstance(dados, str):
                try:
                    dados = json.loads(dados)
                except Exception:
                    dados = {"mensagem": dados}

            uri_provisionamento = dados.get("uri_provisionamento", "")
            if not uri_provisionamento:
                return json.dumps({
                    "status": "erro",
                    "mensagem": "URI de provisionamento TOTP não recebida do servidor."
                })

            # 3. Gera a imagem do QR Code
            qr_file_path = os.path.join(self.resources_dir, 'totp_qr.png')
            img = qrcode.make(uri_provisionamento)
            img.save(qr_file_path)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qr_base64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

            # 4. Extrai o segredo para inserção manual caso necessário
            secret = ""
            try:
                parsed = urllib.parse.urlparse(uri_provisionamento)
                query = urllib.parse.parse_qs(parsed.query)
                secret = query.get("secret", [""])[0]
            except Exception:
                pass

            return json.dumps({
                "status": "sucesso",
                "mensagem": dados.get("mensagem", "Pré-cadastro iniciado com sucesso."),
                "uri_provisionamento": uri_provisionamento,
                "secret": secret,
                "qr_path": os.path.abspath(qr_file_path).replace("\\", "/"),
                "qr_base64": qr_base64
            })

        except Exception as e:
            return json.dumps({"status": "erro", "mensagem": f"Falha na operação: {str(e)}"})

    @Slot(str, str, result=str)
    def confirmarPreCadastro(self, email: str, codigo_totp: str) -> str:
        """
        Passo 2 do fluxo:
        - Valida o código TOTP digitado
        - Gera assinatura digital RSA no hardware TPM com a chave privada da máquina
        - Envia para POST /api/admin/pre-cadastro/confirmar/
        - Salva o status de confirmação localmente ao receber sucesso
        """
        email = (email or '').strip()
        codigo_totp = (codigo_totp or '').strip()

        if not email:
            return json.dumps({"status": "erro", "mensagem": "O e-mail é obrigatório."})
        if not codigo_totp:
            return json.dumps({"status": "erro", "mensagem": "O código TOTP é obrigatório."})
        if len(codigo_totp) != 6 or not codigo_totp.isdigit():
            return json.dumps({"status": "erro", "mensagem": "O código TOTP deve conter exatamente 6 dígitos numéricos."})

        try:
            # 1. Assina o payload com a chave privada residente no chip de hardware TPM
            payload_to_sign = f"{email}:{codigo_totp}"
            assinatura = cng_windows.sign_data("VotaAI_DesktopClient_Key", payload_to_sign)

            # 2. Envia para o backend
            url = f"{self.api_base_url}/api/admin/pre-cadastro/confirmar/"
            payload = {
                "email": email,
                "codigo_totp": codigo_totp,
                "assinatura": assinatura
            }

            response = self.http_client.post(url, payload)

            if response.get("status") != "sucesso":
                msg = response.get("mensagem", "Código TOTP inválido ou falha de validação.")
                if isinstance(msg, dict):
                    msg = "; ".join(f"{k}: {v}" for k, v in msg.items())
                return json.dumps({"status": "erro", "mensagem": str(msg)})

            dados = response.get("dados", {})
            if isinstance(dados, str):
                try:
                    dados = json.loads(dados)
                except Exception:
                    dados = {"mensagem": dados}

            # 3. Salva a informação de registro com sucesso localmente
            reg_info = {
                "is_registered": True,
                "email": email,
                "confirmed_at": datetime.now().isoformat()
            }
            with open(self._get_registration_path(), 'w', encoding='utf-8') as f:
                json.dump(reg_info, f, indent=4)

            self.registrationStatusChanged.emit()

            return json.dumps({
                "status": "sucesso",
                "mensagem": dados.get("mensagem", "Administrador ativado e máquina vinculada com sucesso!")
            })

        except Exception as e:
            return json.dumps({"status": "erro", "mensagem": f"Erro na confirmação: {str(e)}"})

    @Slot(result=bool)
    def resetRegistration(self) -> bool:
        """Remove o registro local para permitir novo pré-cadastro de teste."""
        reg_path = self._get_registration_path()
        if os.path.exists(reg_path):
            try:
                os.remove(reg_path)
            except Exception as e:
                print(f"Erro ao remover registration_info.json: {e}")
                return False
        self.registrationStatusChanged.emit()
        return True
