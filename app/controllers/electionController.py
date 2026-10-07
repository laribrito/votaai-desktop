import json
import threading
from PySide6.QtCore import QObject, Slot, Signal, Property

from app.controllers.cryptoController import CryptoController
from app.services.election_api import ElectionApiService

class ElectionController(QObject):
    createElectionFinished = Signal(str)
    isLoadingChanged = Signal()

    def __init__(self, csv_controller=None, parent=None):
        super().__init__(parent)
        self.csv_controller = csv_controller
        self.crypto_controller = CryptoController()
        self.api_service = ElectionApiService()
        self._is_loading = False

    @Property(bool, notify=isLoadingChanged)
    def isLoading(self):
        return self._is_loading

    def _set_loading(self, loading: bool):
        if self._is_loading != loading:
            self._is_loading = loading
            self.isLoadingChanged.emit()

    def _execute_create_election(self, title, ballot_json):
        # 1. Gera a chave pública e o handle da eleição no hardware seguro correspondente ao SO atual
        public_key, key_handle = self.crypto_controller.generate_hardware_keys()
        
        # 2. Resgata o colégio eleitoral que já foi validado pelo CSV (campos em inglês)
        electoral_college = []
        if self.csv_controller and hasattr(self.csv_controller, '_csv_model'):
            for row in self.csv_controller._csv_model._data:
                full_name = row[0].strip() if len(row) > 0 else ""
                email = row[1].strip() if len(row) > 1 else ""
                electoral_college.append({
                    "name": full_name,
                    "email": email
                })
        else:
            return json.dumps({"status": "erro", "mensagem": "Controlador de CSV não disponível ou sem dados."})

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
                        options.append({"label": opt_str, "title": opt_str, "position": idx + 1})
                elif isinstance(opt, dict):
                    title_opt = (opt.get("label") or opt.get("title") or opt.get("opcao") or opt.get("text") or "").strip()
                    if title_opt:
                        options.append({"label": title_opt, "title": title_opt, "position": opt.get("position", idx + 1)})

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
