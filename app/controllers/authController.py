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
from app.services.device_service import DeviceService
import qrcode

class AuthController(QObject):
    """
    Controlador para gerenciar o pré-cadastro do usuário administrador
    com provisionamento de chave RSA segura no hardware TPM e segundo fator TOTP.
    """
    registrationStatusChanged = Signal()
    authenticationStatusChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.http_client = HttpClient()
        self.api_base_url = config('API_BASE_URL', default='http://127.0.0.1:8000').rstrip('/')
        self.resources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources'))
        os.makedirs(self.resources_dir, exist_ok=True)
        self._is_authenticated = False
        self._auth_token = None

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

    @Property(bool, notify=authenticationStatusChanged)
    def isAuthenticated(self):
        return self._is_authenticated

    @Property(str, notify=authenticationStatusChanged)
    def authToken(self):
        return self._auth_token or ""

    @Property(str, notify=registrationStatusChanged)
    def registeredEmail(self):
        data = self._read_registration_data()
        return data.get("email", "")

    @Property(str, notify=registrationStatusChanged)
    def registeredUserName(self):
        data = self._read_registration_data()
        if data.get("nome"):
            return data["nome"]
        email = data.get("email", "")
        if not email:
            return ""
        try:
            for csv_name in ['valido.csv', 'invalido4.csv']:
                csv_path = os.path.join(os.path.dirname(__file__), '..', '..', csv_name)
                if os.path.exists(csv_path):
                    import csv
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if len(row) >= 2 and row[1].strip() == email:
                                return row[0].strip()
        except Exception:
            pass
        return email.split("@")[0]

    @Property(str, notify=registrationStatusChanged)
    def registeredDeviceId(self):
        data = self._read_registration_data()
        return data.get("usuario_maquina", "")

    @Property(str, notify=registrationStatusChanged)
    def registeredDate(self):
        data = self._read_registration_data()
        raw_date = data.get("confirmed_at", "")
        if raw_date:
            try:
                dt = datetime.fromisoformat(raw_date)
                return dt.strftime("%d/%m/%Y às %H:%M")
            except Exception:
                return raw_date
        return ""

    @Property(str, notify=registrationStatusChanged)
    def registeredUserInitials(self):
        data = self._read_registration_data()
        email = data.get("email", "")
        if not email:
            return "AD"
        name_part = email.split("@")[0]
        letters = [c.upper() for c in name_part if c.isalpha()]
        if len(letters) >= 2:
            return "".join(letters[:2])
        elif len(letters) == 1:
            return letters[0]
        return "AD"

    @Property(str, notify=registrationStatusChanged)
    def registeredRole(self):
        return "Administrador"

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

        if self.isRegistered:
            return json.dumps({
                "status": "erro",
                "mensagem": f"Esta máquina já possui um administrador cadastrado ({self.registeredEmail})."
            })

        try:
            # 1. Carrega chave existente no hardware TPM da máquina ou gera uma nova caso não exista
            client_key_path = os.path.join(self.resources_dir, 'client_key.json')
            key_info = None
            if os.path.exists(client_key_path):
                try:
                    with open(client_key_path, 'r', encoding='utf-8') as f:
                        key_info = json.load(f)
                except Exception:
                    key_info = None

            if not key_info or not key_info.get("PublicKeyBase64"):
                key_info = cng_windows.generate_rsa_key("VotaAI_DesktopClient_Key")
                with open(client_key_path, 'w', encoding='utf-8') as f:
                    json.dump(key_info, f, indent=4)

            # Recarrega a chave pública no serviço de criptografia do http_client
            _, client_pub_pem = self.http_client.encryption_service.reload_client_keys()

            # 2. Envia para o backend (o HttpClient automaticamente envia o envelope cifrado híbrido)
            url = f"{self.api_base_url}/api/admin/pre-cadastro/"
            device_id = DeviceService().get_device_id()
            payload = {
                "email": email,
                "senha": senha,
                "chave_publica_maquina": client_pub_pem,
                "usuario_maquina": device_id
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
                "usuario_maquina": DeviceService().get_device_id(),
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
        self._is_authenticated = False
        self._auth_token = None
        self.authenticationStatusChanged.emit()
        self.registrationStatusChanged.emit()
        return True

    @Slot(str, str, result=str)
    def login(self, senha: str, codigo_totp: str) -> str:
        """
        Autentica o administrador registrado com dois fatores (2FA):
        1. Valida senha de acesso
        2. Valida código TOTP de 6 dígitos
        3. Assina o desafio no chip de hardware TPM da máquina
        4. Envia para POST /api/auth/login/
        """
        senha = (senha or '').strip()
        codigo_totp = (codigo_totp or '').strip()

        if not senha:
            return json.dumps({"status": "erro", "mensagem": "A senha é obrigatória."})

        if not codigo_totp:
            return json.dumps({"status": "erro", "mensagem": "O código TOTP de 6 dígitos é obrigatório."})

        if len(codigo_totp) != 6 or not codigo_totp.isdigit():
            return json.dumps({"status": "erro", "mensagem": "O código TOTP deve conter exatamente 6 dígitos numéricos."})

        email = self.registeredEmail
        if not email:
            return json.dumps({"status": "erro", "mensagem": "Nenhum administrador registrado nesta máquina."})

        try:
            # 1. Gera assinatura digital RSA da máquina com o código TOTP
            payload_to_sign = f"{email}:{codigo_totp}"
            try:
                assinatura = cng_windows.sign_data("VotaAI_DesktopClient_Key", payload_to_sign)
            except Exception as se:
                assinatura = ""
                print(f"Aviso de assinatura TPM: {se}")

            url = f"{self.api_base_url}/api/auth/login/"
            payload = {
                "username": email,
                "password": senha,
                "codigo_totp": codigo_totp,
                "assinatura": assinatura,
                "usuario_maquina": self.registeredDeviceId
            }

            response = self.http_client.post(url, payload)

            if response.get("status") != "sucesso":
                msg = response.get("mensagem", "Falha na autenticação.")
                if isinstance(msg, str):
                    try:
                        msg = json.loads(msg)
                    except Exception:
                        pass

                if isinstance(msg, dict):
                    if "codigo_totp" in msg:
                        totp_err = msg["codigo_totp"]
                        msg = totp_err if isinstance(totp_err, str) else "; ".join(str(x) for x in totp_err)
                    elif "assinatura" in msg:
                        sig_err = msg["assinatura"]
                        msg = sig_err if isinstance(sig_err, str) else "; ".join(str(x) for x in sig_err)
                    elif "usuario_maquina" in msg:
                        dev_err = msg["usuario_maquina"]
                        msg = dev_err if isinstance(dev_err, str) else "; ".join(str(x) for x in dev_err)
                    elif "detail" in msg:
                        detail = str(msg["detail"])
                        if "Invalid username or password" in detail:
                            msg = "Senha incorreta. Por favor, tente novamente."
                        else:
                            msg = detail
                    elif "error" in msg:
                        msg = str(msg["error"])
                    elif "non_field_errors" in msg:
                        msg = " ".join(str(x) for x in msg["non_field_errors"])
                    else:
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
                    dados = {"token": dados}

            token = dados.get("token") or dados.get("access") or ""
            self._auth_token = token
            self._is_authenticated = True
            self.authenticationStatusChanged.emit()

            return json.dumps({
                "status": "sucesso",
                "mensagem": "Autenticação em dois fatores realizada com sucesso!",
                "token": token
            })
        except Exception as e:
            return json.dumps({"status": "erro", "mensagem": f"Erro de conexão ao autenticar: {str(e)}"})

    @Slot()
    def logout(self):
        self._is_authenticated = False
        self._auth_token = None
        self.authenticationStatusChanged.emit()
