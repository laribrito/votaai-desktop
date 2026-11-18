import os
import json
import base64
import zipfile
import hashlib
import threading
from PySide6.QtCore import QObject, Slot, Signal, Property
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.controllers.cryptoController import CryptoController
from app.controllers.encryptionController import EncryptionController
from app.services.http_client import HttpClient
from app.services.api_routes import API_ROUTES


def decrypt_vote_with_pem(private_key_pem: str, encrypted_data):
    """
    Descriptografa o conteúdo de uma cédula cifrada utilizando a chave privada em formato PEM.
    Suporta os 3 formatos adotados pelo sistema:
    1. Modelo em camadas ({pacote_cifrado})
    2. Envelope híbrido AES-GCM + RSA ({encrypted_payload, encrypted_aes_key, iv, tag})
    3. Cifra RSA direta (PKCS#1 v1.5 ou OAEP)
    """
    priv_bytes = private_key_pem.encode('utf-8') if isinstance(private_key_pem, str) else private_key_pem
    private_key = serialization.load_pem_private_key(priv_bytes, password=None)

    parsed_dict = None
    if isinstance(encrypted_data, dict):
        parsed_dict = encrypted_data
    elif isinstance(encrypted_data, str):
        try:
            val = json.loads(encrypted_data)
            if isinstance(val, dict):
                parsed_dict = val
        except Exception:
            parsed_dict = None

    if parsed_dict and "pacote_cifrado" in parsed_dict:
        return decrypt_vote_with_pem(private_key_pem, parsed_dict["pacote_cifrado"])

    if parsed_dict and all(k in parsed_dict for k in ("encrypted_payload", "encrypted_aes_key", "iv", "tag")):
        enc_aes_key = base64.b64decode(parsed_dict["encrypted_aes_key"])
        aes_key = private_key.decrypt(enc_aes_key, padding.PKCS1v15())
        aesgcm = AESGCM(aes_key[:32])
        iv_bytes = base64.b64decode(parsed_dict["iv"])
        tag_bytes = base64.b64decode(parsed_dict["tag"])
        payload_bytes = base64.b64decode(parsed_dict["encrypted_payload"])
        return aesgcm.decrypt(iv_bytes, payload_bytes + tag_bytes, None)

    if isinstance(encrypted_data, str):
        cipher_bytes = base64.b64decode(encrypted_data)
    else:
        cipher_bytes = encrypted_data

    try:
        return private_key.decrypt(cipher_bytes, padding.PKCS1v15())
    except Exception:
        return private_key.decrypt(
            cipher_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )


class TallyElectionController(QObject):
    fetchAvailableFinished = Signal(str)
    tallyElectionFinished = Signal(str)
    auditFinished = Signal(str)
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

    @staticmethod
    def _count_vote_static(vote_data, question_map: dict, option_map: dict, results: dict):
        """Helper para tabular respostas de cédulas decifradas usando nomes legíveis de questões e opções."""
        # Formato padrão VotaAí Mobile: {"election_id": 1, "choices": {"1": 10}, "timestamp": "..."}
        if isinstance(vote_data, dict) and "choices" in vote_data and isinstance(vote_data["choices"], dict):
            for q_key, opt_val in vote_data["choices"].items():
                q = question_map.get(str(q_key), question_map.get(q_key, f"Pergunta {q_key}"))
                opt = option_map.get(str(opt_val), option_map.get(opt_val, str(opt_val)))
                results.setdefault(q, {})
                results[q][opt] = results[q].get(opt, 0) + 1
            return

        if isinstance(vote_data, dict):
            # Formato 1: {"question": "...", "option": "..."}
            if "question" in vote_data and "option" in vote_data:
                q = question_map.get(str(vote_data["question"]), str(vote_data["question"])).strip()
                opt = option_map.get(str(vote_data["option"]), str(vote_data["option"])).strip()
                results.setdefault(q, {})
                results[q][opt] = results[q].get(opt, 0) + 1
            # Formato 2: {"escolha": "..."}
            elif "escolha" in vote_data:
                q = "Voto"
                opt = option_map.get(str(vote_data["escolha"]), str(vote_data["escolha"])).strip()
                results.setdefault(q, {})
                results[q][opt] = results[q].get(opt, 0) + 1
            # Formato 3: {"answers": [...]}
            elif "answers" in vote_data and isinstance(vote_data["answers"], list):
                for ans in vote_data["answers"]:
                    TallyElectionController._count_vote_static(ans, question_map, option_map, results)
            # Formato 4: { "Pergunta 1": "Opção A", ... }
            else:
                for k, v in vote_data.items():
                    if k in ("id_voto", "nonce", "receipt", "signature", "election_id", "timestamp"):
                        continue
                    q = question_map.get(str(k), str(k)).strip()
                    opt = option_map.get(str(v), str(v)).strip()
                    results.setdefault(q, {})
                    results[q][opt] = results[q].get(opt, 0) + 1
        elif isinstance(vote_data, list):
            for item in vote_data:
                TallyElectionController._count_vote_static(item, question_map, option_map, results)
        elif isinstance(vote_data, str):
            q = "Voto"
            opt = option_map.get(str(vote_data), vote_data).strip()
            results.setdefault(q, {})
            results[q][opt] = results[q].get(opt, 0) + 1

    def _count_vote(self, vote_data, question_map: dict, option_map: dict, results: dict):
        return self._count_vote_static(vote_data, question_map, option_map, results)

    @classmethod
    def tally_votes_core(
        cls,
        raw_votes: list,
        questions_meta: list,
        total_voters: int,
        key_handle: str,
        decrypt_fn
    ) -> dict:
        """
        Função central e unificada de apuração de votos.
        Reutilizada tanto pela apuração oficial do administrador (Apurar) quanto
        pela auditoria pública independente (Auditoria).
        Decifra cédulas, tabula contagens por pergunta/opção e gera o hash canônico SHA-256.
        """
        question_map = {}
        option_map = {}
        structured_questions = []

        for q_info in questions_meta:
            q_id = q_info.get("id")
            q_text = q_info.get("question") or f"Pergunta {q_id}"
            question_map[str(q_id)] = q_text
            question_map[q_id] = q_text
            opts_list = []
            for opt_info in q_info.get("options", []):
                opt_id = opt_info.get("id")
                opt_label = opt_info.get("label") or f"Opção {opt_id}"
                option_map[str(opt_id)] = opt_label
                option_map[opt_id] = opt_label
                opts_list.append({
                    "id": opt_id,
                    "label": opt_label,
                    "votes": 0,
                    "percentage": 0.0
                })
            structured_questions.append({
                "id": q_id,
                "question": q_text,
                "total_votes": 0,
                "options": opts_list
            })

        decrypted_ballots = []
        results = {}

        for vote_item in raw_votes:
            receipt = vote_item.get("id_generated", "")
            encrypted_content = vote_item.get("content", "")

            try:
                decrypted_bytes = decrypt_fn(encrypted_content)
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

            cls._count_vote_static(ballot_obj, question_map, option_map, results)
            decrypted_ballots.append({
                "receipt": receipt,
                "ballot": ballot_obj
            })

        # Atualiza structured_questions com contagens e percentuais
        for q_entry in structured_questions:
            q_name = q_entry["question"]
            q_counts = results.get(q_name, {})
            q_total = sum(q_counts.values())
            q_entry["total_votes"] = q_total
            for opt_entry in q_entry["options"]:
                lbl = opt_entry["label"]
                c = q_counts.get(lbl, 0)
                opt_entry["votes"] = c
                opt_entry["percentage"] = round((c / q_total) * 100, 2) if q_total > 0 else 0.0

        abstention_count = max(0, total_voters - len(raw_votes))
        abstention_percentage = round((abstention_count / total_voters) * 100, 2) if total_voters > 0 else 0.0

        final_results = dict(results)
        final_results.update({
            "summary": results,
            "questions": structured_questions,
            "total_votos": len(raw_votes),
            "total_voters": total_voters,
            "abstention_count": abstention_count,
            "abstention_percentage": abstention_percentage
        })

        canonical_audit = {
            "keyHandle": key_handle,
            "total_votos": len(raw_votes),
            "results": final_results,
            "decrypted_ballots": decrypted_ballots
        }
        canonical_json = json.dumps(canonical_audit, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        tally_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

        return {
            "results": final_results,
            "tally_hash": tally_hash,
            "total_votos": len(raw_votes),
            "total_voters": total_voters,
            "abstention_count": abstention_count,
            "abstention_percentage": abstention_percentage,
            "decrypted_ballots": decrypted_ballots
        }

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
            questions_meta = dados_votes.get("questions", [])
            total_voters = dados_votes.get("total_voters", len(raw_votes))
            abstention_count = dados_votes.get("abstention_count", max(0, total_voters - len(raw_votes)))
            abstention_percentage = dados_votes.get("abstention_percentage", round((abstention_count / total_voters) * 100, 2) if total_voters > 0 else 0.0)
            print(f"[TallyElectionController] Total de votos cifrados recebidos: {len(raw_votes)}, Total eleitores: {total_voters}, Abstenção: {abstention_percentage}%")

            # --- Etapas 2 e 3: Apuração unificada (decifração, contagem e hash canônico) ---
            tally_core_output = self.tally_votes_core(
                raw_votes=raw_votes,
                questions_meta=questions_meta,
                total_voters=total_voters,
                key_handle=key_handle,
                decrypt_fn=lambda enc: self.crypto_controller.decrypt_vote(key_handle, enc)
            )

            final_results = tally_core_output["results"]
            tally_hash = tally_core_output["tally_hash"]
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
                "results": final_results,
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
                "results": final_results,
                "tally_hash": tally_hash,
                "total_votos": len(raw_votes),
                "total_voters": total_voters,
                "abstention_count": abstention_count,
                "abstention_percentage": abstention_percentage
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

    def _execute_audit_zip(self, zip_path: str) -> str:
        try:
            print(f"\n[TallyElectionController] >>> _execute_audit_zip para arquivo: {zip_path}")
            if not os.path.exists(zip_path):
                return json.dumps({
                    "status": "erro",
                    "mensagem": f"Arquivo não encontrado: {zip_path}"
                })

            with zipfile.ZipFile(zip_path, 'r') as zf:
                filenames = zf.namelist()

                # 1. Localiza a chave privada
                priv_name = next((f for f in filenames if f in ('chave_privada.pem', 'private_key.pem')), None)
                if not priv_name:
                    return json.dumps({
                        "status": "erro",
                        "mensagem": "O arquivo ZIP não contém a chave privada (chave_privada.pem)."
                    })
                private_key_pem = zf.read(priv_name).decode('utf-8')

                # 2. Localiza os votos criptografados
                votes_name = next((f for f in filenames if f in ('votos_criptografados.json', 'encrypted_votes.json')), None)
                if not votes_name:
                    return json.dumps({
                        "status": "erro",
                        "mensagem": "O arquivo ZIP não contém os votos criptografados (votos_criptografados.json)."
                    })
                raw_votes = json.loads(zf.read(votes_name).decode('utf-8'))

                # 3. Localiza os dados/metadados da eleição
                meta_name = next((f for f in filenames if f in ('dados_eleicao.json', 'election.json', 'detalhes_eleicao.json')), None)
                if not meta_name:
                    return json.dumps({
                        "status": "erro",
                        "mensagem": "O arquivo ZIP não contém os dados da eleição (dados_eleicao.json)."
                    })
                election_meta = json.loads(zf.read(meta_name).decode('utf-8'))

            key_handle = str(election_meta.get("key_handle") or election_meta.get("id") or "1")
            questions_meta = election_meta.get("questions", [])
            total_voters = election_meta.get("total_voters", len(raw_votes))
            expected_hash = election_meta.get("tally_hash", "")
            election_title = election_meta.get("title", "Eleição")

            # Reutiliza exatamente o mesmo núcleo de apuração
            tally_output = self.tally_votes_core(
                raw_votes=raw_votes,
                questions_meta=questions_meta,
                total_voters=total_voters,
                key_handle=key_handle,
                decrypt_fn=lambda enc: decrypt_vote_with_pem(private_key_pem, enc)
            )

            calculated_hash = tally_output["tally_hash"]
            is_valid = bool(expected_hash and calculated_hash.strip().lower() == expected_hash.strip().lower())

            return json.dumps({
                "status": "sucesso",
                "titulo": election_title,
                "keyHandle": key_handle,
                "is_valid": is_valid,
                "calculated_hash": calculated_hash,
                "expected_hash": expected_hash,
                "results": tally_output["results"],
                "total_votos": tally_output["total_votos"],
                "total_voters": tally_output["total_voters"],
                "abstention_count": tally_output["abstention_count"],
                "abstention_percentage": tally_output["abstention_percentage"],
                "mensagem": "Auditoria concluída com sucesso!"
            })
        except Exception as e:
            print(f"[TallyElectionController] Exceção em _execute_audit_zip: {e}")
            return json.dumps({"status": "erro", "mensagem": str(e)})

    @Slot(str)
    def auditZip(self, zip_path: str):
        self._set_loading(True)
        def _worker():
            clean_path = zip_path.replace("file://", "").strip()
            res = self._execute_audit_zip(clean_path)
            self._set_loading(False)
            self.auditFinished.emit(res)
        threading.Thread(target=_worker, daemon=True).start()
