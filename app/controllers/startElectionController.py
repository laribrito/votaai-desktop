import json
import threading
from PySide6.QtCore import QObject, Slot, Signal, Property

from app.controllers.cryptoController import CryptoController
from app.controllers.encryptionController import EncryptionController
from app.services.http_client import HttpClient
from app.services.api_routes import API_ROUTES

class StartElectionController(QObject):
    fetchAvailableFinished = Signal(str)
    startElectionFinished = Signal(str)
    isLoadingChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.crypto_controller = CryptoController()
        self.encryption_controller = EncryptionController()
        self.http_client = HttpClient()
        self._is_loading = False
        self._available_elections = []

    @Property(bool, notify=isLoadingChanged)
    def isLoading(self):
        return self._is_loading

    def _set_loading(self, loading: bool):
        if self._is_loading != loading:
            self._is_loading = loading
            self.isLoadingChanged.emit()

    def _execute_fetch_available(self):
        try:
            nonce = self.crypto_controller.generate_random(16)
            payload = {
                "msg": "FETCH_AVAILABLE",
                "nonceClient1": nonce
            }
            print(f"\n[StartElectionController] >>> _execute_fetch_available")
            print(f"[StartElectionController] Nonce enviado (nonceClient1): {nonce}")
            print(f"[StartElectionController] Payload enviado: {payload}")
            
            response = self.http_client.post(API_ROUTES["ELECTION_AVAILABLE"], payload)
            print(f"[StartElectionController] Resposta http_client: {response}")
            
            if response.get("status") == "erro":
                res_err = json.dumps(response)
                print(f"[StartElectionController] Retorno (erro http_client): {res_err}")
                return res_err
                
            dados = response.get("dados", {})
            if isinstance(dados, str):
                try:
                    dados = json.loads(dados)
                except Exception:
                    pass
            print(f"[StartElectionController] Dados extraídos da resposta: {dados}")
            
            # Validação do nonce retornado para evitar replay attack
            received_nonce = dados.get("nonceClient1") if isinstance(dados, dict) else None
            print(f"[StartElectionController] Nonce esperado: {nonce}")
            print(f"[StartElectionController] Nonce recebido: {received_nonce}")
            if received_nonce != nonce:
                res_nonce_err = json.dumps({
                    "status": "erro",
                    "mensagem": "Falha de segurança: Nonce incompatível. Possível ataque de repetição.",
                    "detalhes": {
                        "nonce_esperado": nonce,
                        "nonce_recebido": received_nonce,
                        "dados": dados
                    }
                })
                print(f"[StartElectionController] Retorno (erro de nonce): {res_nonce_err}")
                return res_nonce_err
                
            elections = dados.get("elections", [])
            self._available_elections = elections
            res_sucesso = json.dumps({"status": "sucesso", "elections": elections})
            print(f"[StartElectionController] Retorno (sucesso): {res_sucesso}")
            return res_sucesso
            
        except Exception as e:
            res_exc = json.dumps({"status": "erro", "mensagem": str(e)})
            print(f"[StartElectionController] Retorno (exceção): {res_exc}")
            return res_exc

    @Slot()
    def fetchAvailableElections(self):
        self._set_loading(True)
        def _worker():
            res = self._execute_fetch_available()
            self._set_loading(False)
            self.fetchAvailableFinished.emit(res)
        threading.Thread(target=_worker, daemon=True).start()

    def _execute_start_election(self, key_handle):
        try:
            nonce = self.crypto_controller.generate_random(16)
            payload = {
                "msg": "START_ELECTION",
                "keyHandle": key_handle,
                "nonceClient2": nonce
            }
            print(f"\n[StartElectionController] >>> _execute_start_election")
            print(f"[StartElectionController] Nonce enviado (nonceClient2): {nonce}")
            print(f"[StartElectionController] keyHandle: {key_handle}")
            
            # 1. Assina o payload interno com a chave privada da eleição
            payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            election_signature = self.crypto_controller.sign_data(key_handle, payload_str)
            
            if not election_signature:
                res_sig_err = json.dumps({"status": "erro", "mensagem": "Não foi possível assinar com a chave da eleição."})
                print(f"[StartElectionController] Retorno (erro assinatura): {res_sig_err}")
                return res_sig_err
                
            payload["election_signature"] = election_signature
            
            # 2. http_client.post assina com a chave da máquina e cifra para a API
            response = self.http_client.post(API_ROUTES["ELECTION_START"], payload)
            print(f"[StartElectionController] Resposta http_client: {response}")
            
            if response.get("status") == "erro":
                res_err = json.dumps(response)
                print(f"[StartElectionController] Retorno (erro http_client): {res_err}")
                return res_err
                
            dados = response.get("dados", {})
            if isinstance(dados, str):
                try:
                    dados = json.loads(dados)
                except Exception:
                    pass
            print(f"[StartElectionController] Dados extraídos da resposta: {dados}")
            
            received_nonce = dados.get("nonceClient2") if isinstance(dados, dict) else None
            print(f"[StartElectionController] Nonce esperado: {nonce}")
            print(f"[StartElectionController] Nonce recebido: {received_nonce}")
            if received_nonce != nonce:
                res_nonce_err = json.dumps({
                    "status": "erro",
                    "mensagem": "Falha de segurança: Nonce incompatível.",
                    "detalhes": {
                        "nonce_esperado": nonce,
                        "nonce_recebido": received_nonce,
                        "dados": dados
                    }
                })
                print(f"[StartElectionController] Retorno (erro de nonce): {res_nonce_err}")
                return res_nonce_err
                
            res_sucesso = json.dumps({
                "status": "sucesso", 
                "dados": dados
            })
            print(f"[StartElectionController] Retorno (sucesso): {res_sucesso}")
            return res_sucesso
            
        except Exception as e:
            res_exc = json.dumps({"status": "erro", "mensagem": str(e)})
            print(f"[StartElectionController] Retorno (exceção): {res_exc}")
            return res_exc

    @Slot(str)
    def startElection(self, key_handle):
        self._set_loading(True)
        def _worker():
            res = self._execute_start_election(key_handle)
            self._set_loading(False)
            self.startElectionFinished.emit(res)
        threading.Thread(target=_worker, daemon=True).start()
