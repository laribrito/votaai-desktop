import os
import io
import json
import base64
import urllib.parse
import threading
from datetime import datetime
from PySide6.QtCore import QObject, Slot, Signal, Property
from PySide6.QtGui import QGuiApplication
from decouple import config

from app.controllers.cryptoController import CryptoController
from app.services.http_client import HttpClient
from app.services.api_routes import API_ROUTES
from app.controllers.deviceController import DeviceController
import qrcode

class AuthController(QObject):
    """
    Controlador para gerenciar o pré-cadastro do usuário administrador
    com provisionamento de chave RSA segura no hardware TPM e segundo fator TOTP.
    Todas as chamadas à API são executadas de forma assíncrona.
    """
    registrationStatusChanged = Signal()
    authenticationStatusChanged = Signal()
    preRegistrationFinished = Signal(str)
    confirmarPreCadastroFinished = Signal(str)
    loginFinished = Signal(str)
    isLoadingChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.http_client = HttpClient()
        self.resources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources'))
        os.makedirs(self.resources_dir, exist_ok=True)
        self._is_authenticated = False
        self._auth_token = None
        self._is_loading = False
        self._pending_password = ""

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

    @Property(bool, notify=isLoadingChanged)
    def isLoading(self):
        return self._is_loading

    def _set_loading(self, loading: bool):
        if self._is_loading != loading:
            self._is_loading = loading
            self.isLoadingChanged.emit()

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
    def registeredEmailMasked(self):
        """Retorna o e-mail com a parte local parcialmente mascarada para exibição na tela de login.
        Exemplo: lbsantos1.cic@uesc.br -> l*******1@uesc.br"""
        email = self.registeredEmail
        if not email or "@" not in email:
            return email
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked_local}@{domain}"

    @Property(str, notify=registrationStatusChanged)
    def registeredUserName(self):
        data = self._read_registration_data()
        if data.get("name"):
            return data["name"]
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
        return data.get("device_id") or data.get("usuario_maquina", "")

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

    def _execute_start_pre_registration(self, email: str, password: str) -> str:
        """Execução síncrona do passo 1 do fluxo."""
        email = (email or '').strip()
        password = (password or '').strip()

        if not email:
            return json.dumps({"status": "erro", "mensagem": "O e-mail é obrigatório."})
        if not password:
            return json.dumps({"status": "erro", "mensagem": "A senha é obrigatória."})
        if len(password) < 8:
            return json.dumps({"status": "erro", "mensagem": "A senha deve conter no mínimo 8 caracteres com letras, números e símbolos."})

        self._pending_password = password

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
                crypto_backend = CryptoController.get_backend()
                key_info = crypto_backend.generate_rsa_key("VotaAI_DesktopClient_Key")
                with open(client_key_path, 'w', encoding='utf-8') as f:
                    json.dump(key_info, f, indent=4)

            # Recarrega as chaves do cliente no controller de criptografia
            self.http_client.encryption_controller.reload_client_keys()

            # 2. Envia para o backend (o HttpClient automaticamente envia o envelope cifrado híbrido)
            endpoint = API_ROUTES["auth"]["pre_cadastro"]
            device_id = DeviceController().get_device_id()
            client_pub_pem = self.http_client.encryption_controller.client_public_key_pem
            payload = {
                "email": email,
                "password": password,
                "device_id": device_id,
                "machine_public_key": client_pub_pem,
                "client_public_key": client_pub_pem
            }

            # include_public_key=True pois o servidor ainda não possui a chave pública desta máquina
            response = self.http_client.post(endpoint, payload, include_public_key=True)

            if response.get("status") != "sucesso":
                msg = response.get("mensagem") or response.get("message") or "Erro ao iniciar pré-cadastro no servidor."
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

            payload_data = dados
            if isinstance(dados, dict):
                # Se o servidor retornou status de erro dentro do payload cifrado
                if dados.get("status") in ["error", "erro", "failed"]:
                    err = (
                        dados.get("message")
                        or dados.get("mensagem")
                        or dados.get("detail")
                        or dados.get("error")
                        or "Erro ao iniciar pré-cadastro no servidor."
                    )
                    if isinstance(err, dict):
                        err = "; ".join(f"{k}: {v}" for k, v in err.items())
                    return json.dumps({"status": "erro", "mensagem": str(err)})

                if isinstance(dados.get("data"), dict):
                    payload_data = {**dados, **dados["data"]}
                elif isinstance(dados.get("dados"), dict):
                    payload_data = {**dados, **dados["dados"]}

            # Procura a URI de provisionamento TOTP por chaves em inglês e português
            uri_provisionamento = (
                payload_data.get("provisioning_uri")
                or payload_data.get("uri_provisionamento")
                or payload_data.get("totp_uri")
                or payload_data.get("otpauth_url")
                or payload_data.get("otp_uri")
                or payload_data.get("uri")
                or payload_data.get("provisioning_url")
                or ""
            )

            if not uri_provisionamento:
                server_msg = (
                    payload_data.get("message")
                    or payload_data.get("mensagem")
                    or payload_data.get("detail")
                    or payload_data.get("error")
                )
                if server_msg:
                    return json.dumps({
                        "status": "erro",
                        "mensagem": f"Servidor: {server_msg}"
                    })
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
            secret = (
                payload_data.get("secret")
                or payload_data.get("totp_secret")
                or payload_data.get("secret_key")
                or payload_data.get("base32_secret")
                or payload_data.get("segredo")
                or ""
            )
            if not secret and uri_provisionamento:
                try:
                    parsed = urllib.parse.urlparse(uri_provisionamento)
                    query = urllib.parse.parse_qs(parsed.query)
                    secret = query.get("secret", [""])[0]
                except Exception:
                    pass

            success_msg = (
                payload_data.get("message")
                or payload_data.get("mensagem")
                or "Pré-cadastro iniciado com sucesso."
            )

            return json.dumps({
                "status": "sucesso",
                "mensagem": success_msg,
                "message": success_msg,
                "uri_provisionamento": uri_provisionamento,
                "provisioning_uri": uri_provisionamento,
                "secret": secret,
                "qr_path": os.path.abspath(qr_file_path).replace("\\", "/"),
                "qr_base64": qr_base64
            })

        except Exception as e:
            return json.dumps({"status": "erro", "mensagem": f"Falha na operação: {str(e)}"})

    @Slot(str, str)
    def iniciarPreCadastro(self, email: str, password: str):
        """
        Dispara o início do pré-cadastro em segundo plano (assíncrono).
        Emite o sinal preRegistrationFinished(resJson) ao terminar.
        """
        self._set_loading(True)
        def _worker():
            try:
                res = self._execute_start_pre_registration(email, password)
            except Exception as e:
                res = json.dumps({"status": "erro", "mensagem": f"Falha na operação: {str(e)}"})
            finally:
                self._set_loading(False)
            self.preRegistrationFinished.emit(res)

        threading.Thread(target=_worker, daemon=True).start()

    def _execute_confirmar_pre_cadastro(self, email: str, codigo_totp: str, password: str = "") -> str:
        """Execução síncrona do passo 2 do fluxo."""
        email = (email or '').strip()
        codigo_totp = (codigo_totp or '').strip()
        password = (password or '').strip() or self._pending_password

        if not email:
            return json.dumps({"status": "erro", "mensagem": "O e-mail é obrigatório."})
        if not password:
            return json.dumps({"status": "erro", "mensagem": "A senha é obrigatória."})
        if not codigo_totp:
            return json.dumps({"status": "erro", "mensagem": "O código TOTP é obrigatório."})
        if len(codigo_totp) != 6 or not codigo_totp.isdigit():
            return json.dumps({"status": "erro", "mensagem": "O código TOTP deve conter exatamente 6 dígitos numéricos."})

        try:
            # 2. Envia para o backend (o HttpClient/EncryptionController preserva a assinatura e criptografa)
            # O encryptionController cuidará da assinatura do envelope completo (Sign-then-Encrypt)
            endpoint = API_ROUTES["auth"]["confirmar_pre_cadastro"]
            device_id = DeviceController().get_device_id()
            client_pub_pem = self.http_client.encryption_controller.client_public_key_pem
            payload = {
                "email": email,
                "password": password,
                "totp_code": codigo_totp,
                "device_id": device_id,
                "machine_public_key": client_pub_pem,
                "client_public_key": client_pub_pem
            }

            response = self.http_client.post(endpoint, payload, include_public_key=True)

            if response.get("status") != "sucesso":
                msg = response.get("mensagem") or response.get("message") or "Código TOTP inválido ou falha de validação."
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

            payload_data = dados
            if isinstance(dados, dict):
                if dados.get("status") in ["error", "erro", "failed"]:
                    err = (
                        dados.get("message")
                        or dados.get("mensagem")
                        or dados.get("detail")
                        or dados.get("error")
                        or "Código TOTP inválido ou falha de validação."
                    )
                    if isinstance(err, dict):
                        err = "; ".join(f"{k}: {v}" for k, v in err.items())
                    return json.dumps({"status": "erro", "mensagem": str(err)})

                if isinstance(dados.get("data"), dict):
                    payload_data = {**dados, **dados["data"]}
                elif isinstance(dados.get("dados"), dict):
                    payload_data = {**dados, **dados["dados"]}

            # 3. Salva a informação de registro com sucesso localmente
            reg_info = {
                "is_registered": True,
                "email": email,
                "device_id": device_id,
                "usuario_maquina": device_id,
                "confirmed_at": datetime.now().isoformat()
            }
            with open(self._get_registration_path(), 'w', encoding='utf-8') as f:
                json.dump(reg_info, f, indent=4)

            self._pending_password = ""
            self.registrationStatusChanged.emit()

            success_msg = (
                payload_data.get("message")
                or payload_data.get("mensagem")
                or "Administrador ativado e máquina vinculada com sucesso!"
            )

            return json.dumps({
                "status": "sucesso",
                "mensagem": success_msg,
                "message": success_msg
            })

        except Exception as e:
            return json.dumps({"status": "erro", "mensagem": f"Erro na confirmação: {str(e)}"})

    @Slot(str, str)
    @Slot(str, str, str)
    def confirmarPreCadastro(self, email: str, codigo_totp: str, password: str = ""):
        """
        Dispara a confirmação de pré-cadastro em segundo plano (assíncrono).
        Emite o sinal confirmarPreCadastroFinished(resJson) ao terminar.
        """
        self._set_loading(True)
        def _worker():
            try:
                res = self._execute_confirmar_pre_cadastro(email, codigo_totp, password)
            except Exception as e:
                res = json.dumps({"status": "erro", "mensagem": f"Erro na confirmação: {str(e)}"})
            finally:
                self._set_loading(False)
            self.confirmarPreCadastroFinished.emit(res)

        threading.Thread(target=_worker, daemon=True).start()

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

    def _execute_login(self, senha: str, codigo_totp: str) -> str:
        """Execução síncrona do login de dois fatores."""
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
            endpoint = API_ROUTES["auth"]["login"]
            payload = {
                "username": email,
                "email": email,
                "password": senha,
                "totp_code": codigo_totp,
                "device_id": self.registeredDeviceId
            }

            response = self.http_client.post(endpoint, payload)

            if response.get("status") != "sucesso":
                msg = response.get("mensagem") or response.get("message") or "Falha na autenticação."
                if isinstance(msg, str):
                    try:
                        msg = json.loads(msg)
                    except Exception:
                        pass

                if isinstance(msg, dict):
                    if "totp_code" in msg:
                        totp_err = msg["totp_code"]
                        msg = totp_err if isinstance(totp_err, str) else "; ".join(str(x) for x in totp_err)
                    elif "codigo_totp" in msg:
                        totp_err = msg["codigo_totp"]
                        msg = totp_err if isinstance(totp_err, str) else "; ".join(str(x) for x in totp_err)
                    elif "signature" in msg:
                        sig_err = msg["signature"]
                        msg = sig_err if isinstance(sig_err, str) else "; ".join(str(x) for x in sig_err)
                    elif "assinatura" in msg:
                        sig_err = msg["assinatura"]
                        msg = sig_err if isinstance(sig_err, str) else "; ".join(str(x) for x in sig_err)
                    elif "device_id" in msg:
                        dev_err = msg["device_id"]
                        msg = dev_err if isinstance(dev_err, str) else "; ".join(str(x) for x in dev_err)
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
                    elif "message" in msg:
                        msg = str(msg["message"])
                    elif "mensagem" in msg:
                        msg = str(msg["mensagem"])
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

            payload_data = dados
            if isinstance(dados, dict):
                if dados.get("status") in ["error", "erro", "failed"]:
                    err = (
                        dados.get("message")
                        or dados.get("mensagem")
                        or dados.get("detail")
                        or dados.get("error")
                        or "Falha na autenticação."
                    )
                    if isinstance(err, dict):
                        err = "; ".join(f"{k}: {v}" for k, v in err.items())
                    return json.dumps({"status": "erro", "mensagem": str(err)})

                if isinstance(dados.get("data"), dict):
                    payload_data = {**dados, **dados["data"]}
                elif isinstance(dados.get("dados"), dict):
                    payload_data = {**dados, **dados["dados"]}

            token = (
                payload_data.get("token")
                or payload_data.get("access")
                or payload_data.get("access_token")
                or ""
            )
            self._auth_token = token
            self._is_authenticated = True
            self.authenticationStatusChanged.emit()

            success_msg = (
                payload_data.get("message")
                or payload_data.get("mensagem")
                or "Autenticação em dois fatores realizada com sucesso!"
            )

            return json.dumps({
                "status": "sucesso",
                "mensagem": success_msg,
                "message": success_msg,
                "token": token
            })
        except Exception as e:
            return json.dumps({"status": "erro", "mensagem": f"Erro de conexão ao autenticar: {str(e)}"})

    @Slot(str, str)
    def login(self, senha: str, codigo_totp: str):
        """
        Dispara o login em segundo plano (assíncrono).
        Emite o sinal loginFinished(resJson) ao terminar.
        """
        self._set_loading(True)
        def _worker():
            try:
                res = self._execute_login(senha, codigo_totp)
            except Exception as e:
                res = json.dumps({"status": "erro", "mensagem": f"Erro de conexão ao autenticar: {str(e)}"})
            finally:
                self._set_loading(False)
            self.loginFinished.emit(res)

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def logout(self):
        self._is_authenticated = False
        self._auth_token = None
        self.authenticationStatusChanged.emit()

