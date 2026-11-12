import json
import hashlib
import threading
from PySide6.QtCore import QObject, Slot, Signal, Property

from app.controllers.cryptoController import CryptoController
from app.controllers.encryptionController import EncryptionController
from app.services.http_client import HttpClient
from app.services.api_routes import API_ROUTES


class TallyElectionController(QObject):
    fetchAvailableFinished = Signal(str)
    tallyElectionFinished = Signal(str)
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

    def _execute_fetch_closed(self):
        """Busca eleições que estão no status CLOSED prontas para apuração."""
        try:
            nonce = self.crypto_controller.generate_random(16)
            payload = {
                "msg": "FETCH_CLOSED_FOR_TALLY",
                "nonceClient1": nonce,
                "status": "CLOSED"
            }
            print(f"\n[TallyElectionController] >>> _execute_fetch_closed")
            print(f"[TallyElectionController] Nonce enviado (nonceClient1): {nonce}")
            
            response = self.http_client.post(API_ROUTES["ELECTION_AVAILABLE"], payload)
            print(f"[TallyElectionController] Resposta http_client: {response}")
            
            if response.get("status") == "erro":
                res_err = json.dumps(response)
                return res_err
                
            dados = response.get("dados", {})
            if isinstance(dados, str):
                try:
                    dados = json.loads(dados)
                except Exception:
                    pass
            
            received_nonce = dados.get("nonceClient1") if isinstance(dados, dict) else None
            if received_nonce != nonce:
                return json.dumps({
                    "status": "erro",
                    "mensagem": "Falha de segurança: Nonce incompatível na listagem de eleições fechadas.",
                    "detalhes": {"nonce_esperado": nonce, "nonce_recebido": received_nonce}
                })
                
            elections = dados.get("elections", [])
            self._available_elections = elections
            return json.dumps({"status": "sucesso", "elections": elections})
            
        except Exception as e:
            print(f"[TallyElectionController] Exceção em fetch_closed: {e}")
            return json.dumps({"status": "erro", "mensagem": str(e)})

    @Slot()
    def fetchClosedElections(self):
        self._set_loading(True)
        def _worker():
            res = self._execute_fetch_closed()
            self._set_loading(False)
            self.fetchAvailableFinished.emit(res)
        threading.Thread(target=_worker, daemon=True).start()

    def _count_vote(self, vote_data, results: dict):
        """Helper para tabular respostas de cédulas decifradas."""
        if isinstance(vote_data, dict):
            # Formato 1: {"question": "...", "option": "..."}
            if "question" in vote_data and "option" in vote_data:
                q = str(vote_data["question"]).strip()
                opt = str(vote_data["option"]).strip()
                results.setdefault(q, {})
                results[q][opt] = results[q].get(opt, 0) + 1
            # Formato 2: {"escolha": "..."}
            elif "escolha" in vote_data:
                q = "Voto"
                opt = str(vote_data["escolha"]).strip()
                results.setdefault(q, {})
                results[q][opt] = results[q].get(opt, 0) + 1
            # Formato 3: {"answers": [...]}
            elif "answers" in vote_data and isinstance(vote_data["answers"], list):
                for ans in vote_data["answers"]:
                    self._count_vote(ans, results)
            # Formato 4: { "Pergunta 1": "Opção A", ... }
            else:
                for k, v in vote_data.items():
                    if k in ("id_voto", "nonce", "receipt", "signature"):
                        continue
                    q = str(k).strip()
                    opt = str(v).strip()
                    results.setdefault(q, {})
                    results[q][opt] = results[q].get(opt, 0) + 1
        elif isinstance(vote_data, list):
            for item in vote_data:
                self._count_vote(item, results)
        elif isinstance(vote_data, str):
            q = "Voto"
            opt = vote_data.strip()
            results.setdefault(q, {})
            results[q][opt] = results[q].get(opt, 0) + 1

    def _execute_tally_election(self, key_handle):
        try:
            print(f"\n[TallyElectionController] >>> _execute_tally_election para keyHandle: {key_handle}")
            
            # --- Etapa 1: Obter votos cifrados da urna ---
            nonce_votes = self.crypto_controller.generate_random(16)
            payload_votes = {
                "msg": "FETCH_VOTES_FOR_TALLY",
                "keyHandle": key_handle,
                "nonceClient": nonce_votes
            }
            
            resp_votes = self.http_client.post(API_ROUTES["ELECTION_TALLY_VOTES"], payload_votes)
            if resp_votes.get("status") == "erro":
                return json.dumps(resp_votes)
                
            dados_votes = resp_votes.get("dados", {})
            if isinstance(dados_votes, str):
                try:
                    dados_votes = json.loads(dados_votes)
                except Exception:
                    pass
                    
            received_nonce_v = dados_votes.get("nonceClient") if isinstance(dados_votes, dict) else None
            if received_nonce_v != nonce_votes:
                return json.dumps({
                    "status": "erro",
                    "mensagem": "Falha de segurança: Nonce incompatível ao obter votos cifrados."
                })
                
            raw_votes = dados_votes.get("votes", [])
            print(f"[TallyElectionController] Total de votos cifrados recebidos: {len(raw_votes)}")
            
            # --- Etapa 2: Decifração em lote com a chave privada da eleição ---
            decrypted_ballots = []
            results = {}
            
            for vote_item in raw_votes:
                receipt = vote_item.get("id_generated", "")
                encrypted_content = vote_item.get("content", "")
                
                try:
                    decrypted_bytes = self.crypto_controller.decrypt_vote(key_handle, encrypted_content)
                    if isinstance(decrypted_bytes, (bytes, bytearray)):
                        decrypted_text = decrypted_bytes.decode('utf-8')
                    else:
                        decrypted_text = str(decrypted_bytes)
                except Exception as e:
                    print(f"[TallyElectionController] Erro ao decifrar voto {receipt}: {e}")
                    decrypted_text = json.dumps({"error": f"Decryption failed: {str(e)}"})
                    
                try:
                    ballot_obj = json.loads(decrypted_text)
                except Exception:
                    ballot_obj = {"raw": decrypted_text}
                    
                self._count_vote(ballot_obj, results)
                decrypted_ballots.append({
                    "receipt": receipt,
                    "ballot": ballot_obj
                })
                
            # --- Etapa 3: Cálculo do hash criptográfico canônico de auditoria (tally_hash) ---
            canonical_audit = {
                "keyHandle": key_handle,
                "total_votos": len(raw_votes),
                "results": results,
                "decrypted_ballots": decrypted_ballots
            }
            canonical_json = json.dumps(canonical_audit, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            tally_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
            print(f"[TallyElectionController] Hash da apuração gerado: {tally_hash}")
            
            # --- Etapa 4: Exportação da chave privada da eleição fora do TEE ---
            private_key_pem = self.crypto_controller.export_election_private_key(key_handle)
            if not private_key_pem or "BEGIN PRIVATE KEY" not in private_key_pem:
                return json.dumps({
                    "status": "erro",
                    "mensagem": "Não foi possível carregar a chave privada da eleição para envio da apuração."
                })
                
            # --- Etapa 5: Submissão da apuração oficial ao servidor ---
            nonce_tally = self.crypto_controller.generate_random(16)
            payload_tally = {
                "msg": "SUBMIT_TALLY",
                "keyHandle": key_handle,
                "tally_hash": tally_hash,
                "private_key": private_key_pem,
                "results": results,
                "nonceClient": nonce_tally
            }
            
            resp_tally = self.http_client.post(API_ROUTES["ELECTION_TALLY"], payload_tally)
            if resp_tally.get("status") == "erro":
                return json.dumps(resp_tally)
                
            dados_tally = resp_tally.get("dados", {})
            if isinstance(dados_tally, str):
                try:
                    dados_tally = json.loads(dados_tally)
                except Exception:
                    pass
                    
            received_nonce_t = dados_tally.get("nonceClient") if isinstance(dados_tally, dict) else None
            if received_nonce_t != nonce_tally:
                return json.dumps({
                    "status": "erro",
                    "mensagem": "Falha de segurança: Nonce incompatível ao confirmar apuração."
                })
                
            return json.dumps({
                "status": "sucesso",
                "dados": dados_tally,
                "results": results,
                "tally_hash": tally_hash,
                "total_votos": len(raw_votes)
            })
            
        except Exception as e:
            print(f"[TallyElectionController] Exceção em tally_election: {e}")
            return json.dumps({"status": "erro", "mensagem": str(e)})

    @Slot(str)
    def tallyElection(self, key_handle):
        self._set_loading(True)
        def _worker():
            res = self._execute_tally_election(key_handle)
            self._set_loading(False)
            self.tallyElectionFinished.emit(res)
        threading.Thread(target=_worker, daemon=True).start()
