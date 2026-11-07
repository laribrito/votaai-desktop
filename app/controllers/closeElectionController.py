import json
import threading
from PySide6.QtCore import QObject, Slot, Signal, Property

from app.controllers.cryptoController import CryptoController
from app.controllers.encryptionController import EncryptionController
from app.services.http_client import HttpClient
from app.services.api_routes import API_ROUTES

class CloseElectionController(QObject):
    fetchAvailableFinished = Signal(str)
    closeElectionFinished = Signal(str)
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
                "nonceClient1": nonce,
                "status": "STARTED"  # Busca eleições ativas (em andamento) para encerramento
            }
            print(f"\n[CloseElectionController] >>> _execute_fetch_available")
            print(f"[CloseElectionController] Nonce enviado (nonceClient1): {nonce}")
            print(f"[CloseElectionController] Payload enviado: {payload}")
            
            response = self.http_client.post(API_ROUTES["ELECTION_AVAILABLE"], payload)
            print(f"[CloseElectionController] Resposta http_client: {response}")
            
            if response.get("status") == "erro":
                res_err = json.dumps(response)
                print(f"[CloseElectionController] Retorno (erro http_client): {res_err}")
                return res_err
                
            dados = response.get("dados", {})
            if isinstance(dados, str):
                try:
                    dados = json.loads(dados)
                except Exception:
                    pass
            print(f"[CloseElectionController] Dados extraídos da resposta: {dados}")
            
            # Validação do nonce retornado para evitar replay attack
            received_nonce = dados.get("nonceClient1") if isinstance(dados, dict) else None
            print(f"[CloseElectionController] Nonce esperado: {nonce}")
            print(f"[CloseElectionController] Nonce recebido: {received_nonce}")
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
                print(f"[CloseElectionController] Retorno (erro de nonce): {res_nonce_err}")
                return res_nonce_err
                
            elections = dados.get("elections", [])
            self._available_elections = elections
            res_sucesso = json.dumps({"status": "sucesso", "elections": elections})
            print(f"[CloseElectionController] Retorno (sucesso): {res_sucesso}")
            return res_sucesso
            
        except Exception as e:
            res_exc = json.dumps({"status": "erro", "mensagem": str(e)})
            print(f"[CloseElectionController] Retorno (exceção): {res_exc}")
            return res_exc

    @Slot()
    def fetchAvailableElections(self):
        self._set_loading(True)
        def _worker():
            res = self._execute_fetch_available()
            self._set_loading(False)
            self.fetchAvailableFinished.emit(res)
        threading.Thread(target=_worker, daemon=True).start()

    def _execute_close_election(self, key_handle):
        try:
            nonce = self.crypto_controller.generate_random(16)
            payload = {
                "msg": "CLOSE_ELECTION",
                "keyHandle": key_handle,
                "nonceClient3": nonce
            }
            print(f"\n[CloseElectionController] >>> _execute_close_election")
            print(f"[CloseElectionController] Nonce enviado (nonceClient3): {nonce}")
            print(f"[CloseElectionController] keyHandle: {key_handle}")
            
            # 1. Assina o payload canônico com a chave privada da eleição no hardware TPM
            payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            election_signature = self.crypto_controller.sign_data(key_handle, payload_str)
            
            if not election_signature:
                res_sig_err = json.dumps({"status": "erro", "mensagem": "Não foi possível assinar com a chave da eleição."})
                print(f"[CloseElectionController] Retorno (erro assinatura): {res_sig_err}")
                return res_sig_err
                
            payload["election_signature"] = election_signature
            
            # 2. http_client.post assina com a chave da máquina e cifra no envelope TPM da API
            endpoint = API_ROUTES.get("ELECTION_CLOSE") or API_ROUTES.get("election", {}).get("close", "/api/election/close/")
            response = self.http_client.post(endpoint, payload)
            print(f"[CloseElectionController] Resposta http_client: {response}")
            
            if response.get("status") == "erro":
                res_err = json.dumps(response)
                print(f"[CloseElectionController] Retorno (erro http_client): {res_err}")
                return res_err
                
            dados = response.get("dados", {})
            if isinstance(dados, str):
                try:
                    dados = json.loads(dados)
                except Exception:
                    pass
            print(f"[CloseElectionController] Dados extraídos da resposta: {dados}")
            
            received_nonce = (
                dados.get("nonceClient3")
                or dados.get("nonceClient")
                or dados.get("nonceClient2")
                or dados.get("nonce")
            ) if isinstance(dados, dict) else None
            
            print(f"[CloseElectionController] Nonce esperado: {nonce}")
            print(f"[CloseElectionController] Nonce recebido: {received_nonce}")
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
                print(f"[CloseElectionController] Retorno (erro de nonce): {res_nonce_err}")
                return res_nonce_err
                
            res_sucesso = json.dumps({
                "status": "sucesso", 
                "dados": dados
            })
            print(f"[CloseElectionController] Retorno (sucesso): {res_sucesso}")
            return res_sucesso
            
        except Exception as e:
            res_exc = json.dumps({"status": "erro", "mensagem": str(e)})
            print(f"[CloseElectionController] Retorno (exceção): {res_exc}")
            return res_exc

    @Slot(str)
    def closeElection(self, key_handle):
        self._set_loading(True)
        def _worker():
            res = self._execute_close_election(key_handle)
            self._set_loading(False)
            self.closeElectionFinished.emit(res)
        threading.Thread(target=_worker, daemon=True).start()
