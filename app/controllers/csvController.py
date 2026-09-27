import csv
import json
import threading
from PySide6.QtCore import QObject, Slot, Signal, Property, QAbstractTableModel, Qt, QSortFilterProxyModel

from app.controllers.cryptoController import CryptoController
from app.services.election_api import ElectionApiService
from app.services.http_client import HttpClient
from app.services.api_routes import API_ROUTES

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
    createElectionFinished = Signal(str)
    testConnectionFinished = Signal(str)
    isLoadingChanged = Signal()

    def __init__(self, institutional_domain="@uesc.br"):
        super().__init__()
        self.institutional_domain = institutional_domain
        self.crypto_controller = CryptoController()
        self.api_service = ElectionApiService()
        self._csv_model = CsvTableModel()
        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._csv_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(-1)
        self._is_loading = False

    @Property(bool, notify=isLoadingChanged)
    def isLoading(self):
        return self._is_loading

    def _set_loading(self, loading: bool):
        if self._is_loading != loading:
            self._is_loading = loading
            self.isLoadingChanged.emit()

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

    def _execute_create_election(self, title, ballot_json):
        # 1. Gera a chave pública e o handle da eleição no hardware seguro correspondente ao SO atual
        public_key, key_handle = self.crypto_controller.generate_hardware_keys()
        
        # 2. Resgata o colégio eleitoral que já foi validado pelo CSV (campos em inglês)
        electoral_college = []
        for row in self._csv_model._data:
            full_name = row[0].strip() if len(row) > 0 else ""
            email = row[1].strip() if len(row) > 1 else ""
            electoral_college.append({
                "name": full_name,
                "email": email
            })

        # 3. Faz o parsing e normalização da cédula (campos em inglês)
        try:
            raw_ballot = json.loads(ballot_json)
        except Exception as e:
            print(f"Erro ao converter cédula: {e}")
            raw_ballot = []

        ballot = []
        for item in raw_ballot:
            question_text = (item.get("question") or item.get("enunciado") or item.get("titulo") or "").strip()
            raw_options = item.get("options") or item.get("opcoes") or []
            options = []
            for idx, opt in enumerate(raw_options):
                if isinstance(opt, str):
                    opt_str = opt.strip()
                    if opt_str:
                        options.append({"title": opt_str, "position": idx + 1})
                elif isinstance(opt, dict):
                    title_opt = (opt.get("title") or opt.get("opcao") or opt.get("text") or "").strip()
                    if title_opt:
                        options.append({"title": title_opt, "position": opt.get("position", idx + 1)})

            if question_text and options:
                ballot.append({
                    "question": question_text,
                    "maxOptions": item.get("maxOptions", 1),
                    "minOptions": item.get("minOptions", 1),
                    "options": options
                })

        # 5. Monta o payload final exclusivamente com campos em inglês (snake_case)
        payload = {
            "title": title,
            "public_key": public_key,
            "key_handle": key_handle,
            "ballot": ballot,
            "electoral_college": electoral_college
        }
        
        # 6. Envia para a API externa usando o serviço
        resultado = self.api_service.enviar_eleicao(payload)
        if isinstance(resultado, dict):
            dados = resultado.get("dados", {})
            if isinstance(dados, dict) and dados.get("status") in ["error", "erro", "failed"]:
                err = dados.get("message") or dados.get("mensagem") or dados.get("detail") or dados.get("error") or "Erro ao criar eleição."
                return json.dumps({"status": "erro", "mensagem": err})
        return json.dumps(resultado)

    @Slot(str, str)
    def createElection(self, titulo, cedula_json):
        """Dispara a criação de eleição em segundo plano (assíncrono)."""
        self._set_loading(True)
        def _worker():
            try:
                res = self._execute_create_election(titulo, cedula_json)
            except Exception as e:
                res = json.dumps({"status": "erro", "mensagem": str(e)})
            finally:
                self._set_loading(False)
            self.createElectionFinished.emit(res)

        threading.Thread(target=_worker, daemon=True).start()

    @Slot(result=str)
    def testConnection(self):
        """Teste síncrono para scripts/terminal."""
        try:
            http_client = HttpClient()
            payload = {"ping": "Hello from Desktop"}
            response = http_client.post(API_ROUTES["system"]["ping"], payload)
            return json.dumps(response, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Erro ao conectar: {str(e)}"

    @Slot()
    def testConnectionAsync(self):
        """Dispara o teste de conexão em segundo plano emitindo testConnectionFinished."""
        self._set_loading(True)
        def _worker():
            try:
                res = self.testConnection()
            except Exception as e:
                res = f"Erro ao conectar: {str(e)}"
            finally:
                self._set_loading(False)
            self.testConnectionFinished.emit(res)

        threading.Thread(target=_worker, daemon=True).start()


