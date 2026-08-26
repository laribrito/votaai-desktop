import csv
import json
from PySide6.QtCore import QObject, Slot, Signal, Property, QAbstractTableModel, Qt, QSortFilterProxyModel

from app.controllers.cryptoController import CryptoController
from app.services.election_api import ElectionApiService
from app.services.auth_service import AuthService
from app.services.device_service import DeviceService
from app.services.http_client import HttpClient

class CsvTableModel(QAbstractTableModel):
    def __init__(self, data=None, headers=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = headers or []

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section < len(self._headers):
                return self._headers[section]
        return None

    def roleNames(self):
        return {Qt.DisplayRole: b"display"}

    def update_data(self, headers, data):
        self.beginResetModel()
        self._headers = headers
        self._data = data
        self.endResetModel()

class CsvController(QObject):
    modelChanged = Signal()

    def __init__(self, institutional_domain="@uesc.br"):
        super().__init__()
        self.institutional_domain = institutional_domain
        self.crypto_controller = CryptoController()
        
        device_service = DeviceService()
        http_client = HttpClient()
        auth_service = AuthService(self.crypto_controller, device_service, http_client)
        
        self.api_service = ElectionApiService(auth_service)
        self._csv_model = CsvTableModel()
        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._csv_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(-1)

    @Property(QObject, notify=modelChanged)
    def csvModel(self):
        return self._proxy_model

    @Slot(str)
    def search(self, query):
        self._proxy_model.setFilterFixedString(query)

    @Slot(str, result=str)
    def validateCsv(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers or len(headers) < 2:
                    self._csv_model.update_data([], [])
                    return "O CSV deve ter as colunas nomeCompleto e email."
                if headers[0].strip() != 'nomeCompleto' or headers[1].strip() != 'email':
                    self._csv_model.update_data([], [])
                    return "As colunas devem ser nomeCompleto e email."
                
                rows = []
                seen_emails = set()
                for row in reader:
                    if len(row) >= 2:
                        email = row[1].strip()
                        if not email.endswith(self.institutional_domain):
                            self._csv_model.update_data([], [])
                            return f"Apenas serão aceitos eleitores com emails institucionais ({self.institutional_domain})."
                        
                        if email in seen_emails:
                            self._csv_model.update_data([], [])
                            return f"O email '{email}' está duplicado no CSV. Cada email deve aparecer apenas uma vez."
                        
                        seen_emails.add(email)
                        rows.append([row[0].strip(), email])
                
                if not rows:
                    self._csv_model.update_data([], [])
                    return "O arquivo CSV não contém nenhum eleitor válido."
                
                self._csv_model.update_data([h.strip() for h in headers[:2]], rows)
                self.modelChanged.emit()
                return ""
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
            self._csv_model.update_data([], [])
            return f"Erro ao ler o arquivo: {e}"

    @Slot(str)
    def saveTemplate(self, filepath):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"nomeCompleto,email\nJoão da Silva,joao{self.institutional_domain}\n")
        except Exception as e:
            print(f"Erro ao salvar template: {e}")

    @Slot(str, str, result=str)
    def createElection(self, titulo, cedula_json):
        # 1. Gera a chave pública e o handle no hardware seguro correspondente ao SO atual
        chave_publica, key_handle = self.crypto_controller.generate_hardware_keys()
        
        # 2. Resgata o colégio eleitoral que já foi validado pelo CSV
        colegio_eleitoral = []
        for row in self._csv_model._data:
            nome_completo = row[0]
            email = row[1]
            apelido = nome_completo.split()[0] if nome_completo else ""
            colegio_eleitoral.append({
                "nomeCompleto": nome_completo,
                "email": email,
                "apelido": apelido
            })

        # 3. Faz o parsing das perguntas da cédula vindas do front-end
        try:
            cedula = json.loads(cedula_json)
        except Exception as e:
            print(f"Erro ao converter cédula: {e}")
            cedula = []

        # 4. Monta o payload final conforme a especificação
        payload = {
            "titulo": titulo,
            "chavePublica": chave_publica,
            "keyHandle": key_handle,
            "cedula": cedula,
            "colegio_eleitoral": colegio_eleitoral
        }
        
        # 5. Envia para a API externa usando o serviço
        resultado = self.api_service.enviar_eleicao(payload)
        return json.dumps(resultado)
