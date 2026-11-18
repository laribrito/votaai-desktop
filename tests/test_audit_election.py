import os
import json
import base64
import zipfile
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.controllers.tallyElectionController import TallyElectionController, decrypt_vote_with_pem


class TestAuditElection(unittest.TestCase):
    def setUp(self):
        self.controller = TallyElectionController()
        # Gera par de chaves RSA para teste de decifração da auditoria
        self.priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.priv_pem = self.priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        self.pub_key = self.priv_key.public_key()

    def test_decrypt_vote_with_pem_pkcs1v15(self):
        """Valida que decrypt_vote_with_pem decifra corretamente com a chave privada."""
        payload_bytes = b'{"question": "Diretoria", "option": "Chapa 1"}'
        encrypted = self.pub_key.encrypt(payload_bytes, padding.PKCS1v15())
        b64_enc = base64.b64encode(encrypted).decode('utf-8')

        decrypted = decrypt_vote_with_pem(self.priv_pem, b64_enc)
        self.assertEqual(decrypted, payload_bytes)

    def test_tally_votes_core_reused_logic(self):
        """Valida a execução de tally_votes_core tabulando contagens e calculando o hash canônico."""
        voto1 = self.pub_key.encrypt(b'{"question": "Pergunta 1", "option": "Opcao A"}', padding.PKCS1v15())
        voto2 = self.pub_key.encrypt(b'{"question": "Pergunta 1", "option": "Opcao B"}', padding.PKCS1v15())
        voto3 = self.pub_key.encrypt(b'{"question": "Pergunta 1", "option": "Opcao A"}', padding.PKCS1v15())

        raw_votes = [
            {"id_generated": "rcpt-1", "content": base64.b64encode(voto1).decode('utf-8')},
            {"id_generated": "rcpt-2", "content": base64.b64encode(voto2).decode('utf-8')},
            {"id_generated": "rcpt-3", "content": base64.b64encode(voto3).decode('utf-8')},
        ]

        questions_meta = [
            {
                "id": 1,
                "question": "Pergunta 1",
                "options": [
                    {"id": 10, "label": "Opcao A"},
                    {"id": 11, "label": "Opcao B"},
                ]
            }
        ]

        out = TallyElectionController.tally_votes_core(
            raw_votes=raw_votes,
            questions_meta=questions_meta,
            total_voters=5,
            key_handle="handle_test_01",
            decrypt_fn=lambda enc: decrypt_vote_with_pem(self.priv_pem, enc)
        )

        self.assertEqual(out["total_votos"], 3)
        self.assertEqual(out["total_voters"], 5)
        self.assertEqual(out["abstention_count"], 2)
        self.assertEqual(out["abstention_percentage"], 40.0)
        self.assertEqual(out["results"]["Pergunta 1"]["Opcao A"], 2)
        self.assertEqual(out["results"]["Pergunta 1"]["Opcao B"], 1)
        self.assertTrue(len(out["tally_hash"]) == 64)

    def test_audit_zip_package_success(self):
        """Valida auditoria completa a partir de um pacote ZIP oficial em português."""
        voto1 = self.pub_key.encrypt(b'{"question": "Reitor 2026", "option": "Chapa 1"}', padding.PKCS1v15())
        voto2 = self.pub_key.encrypt(b'{"question": "Reitor 2026", "option": "Chapa 2"}', padding.PKCS1v15())

        raw_votes = [
            {"id_generated": "V-001", "content": base64.b64encode(voto1).decode('utf-8')},
            {"id_generated": "V-002", "content": base64.b64encode(voto2).decode('utf-8')},
        ]

        questions_meta = [
            {
                "id": 1,
                "question": "Reitor 2026",
                "options": [
                    {"id": 101, "label": "Chapa 1"},
                    {"id": 102, "label": "Chapa 2"},
                ]
            }
        ]

        # Calcula o hash oficial canônico
        expected_output = TallyElectionController.tally_votes_core(
            raw_votes=raw_votes,
            questions_meta=questions_meta,
            total_voters=2,
            key_handle="eleicao_audit_10",
            decrypt_fn=lambda enc: decrypt_vote_with_pem(self.priv_pem, enc)
        )
        expected_hash = expected_output["tally_hash"]

        dados_eleicao = {
            "id": 10,
            "key_handle": "eleicao_audit_10",
            "title": "Eleição Reitoria Auditável",
            "tally_hash": expected_hash,
            "total_voters": 2,
            "questions": questions_meta
        }

        # Cria arquivo ZIP temporário
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            zip_path = tmp_file.name

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('chave_privada.pem', self.priv_pem)
                zf.writestr('votos_criptografados.json', json.dumps(raw_votes))
                zf.writestr('dados_eleicao.json', json.dumps(dados_eleicao))
                zf.writestr('LEIAME.txt', "Instruções de auditoria")

            res_str = self.controller._execute_audit_zip(zip_path)
            res = json.loads(res_str)

            self.assertEqual(res["status"], "sucesso")
            self.assertEqual(res["titulo"], "Eleição Reitoria Auditável")
            self.assertTrue(res["is_valid"])
            self.assertEqual(res["calculated_hash"], expected_hash)
            self.assertEqual(res["expected_hash"], expected_hash)
            self.assertEqual(res["total_votos"], 2)
            self.assertEqual(res["results"]["Reitor 2026"]["Chapa 1"], 1)
            self.assertEqual(res["results"]["Reitor 2026"]["Chapa 2"], 1)

        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_audit_zip_detects_hash_tampering(self):
        """Valida que adulteração no hash ou nos votos é detectada pela auditoria."""
        voto1 = self.pub_key.encrypt(b'{"question": "Conselho", "option": "Sim"}', padding.PKCS1v15())
        raw_votes = [{"id_generated": "V-001", "content": base64.b64encode(voto1).decode('utf-8')}]

        dados_eleicao = {
            "id": 11,
            "key_handle": "eleicao_11",
            "title": "Eleição com Hash Adulterado",
            "tally_hash": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "total_voters": 1,
            "questions": []
        }

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            zip_path = tmp_file.name

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('chave_privada.pem', self.priv_pem)
                zf.writestr('votos_criptografados.json', json.dumps(raw_votes))
                zf.writestr('dados_eleicao.json', json.dumps(dados_eleicao))

            res_str = self.controller._execute_audit_zip(zip_path)
            res = json.loads(res_str)

            self.assertEqual(res["status"], "sucesso")
            self.assertFalse(res["is_valid"])  # Divergência detectada!
            self.assertNotEqual(res["calculated_hash"], res["expected_hash"])

        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_audit_zip_missing_files_error(self):
        """Retorna erro caso o ZIP não possua os arquivos essenciais."""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            zip_path = tmp_file.name

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('LEIAME.txt', "Apenas leiame")

            res_str = self.controller._execute_audit_zip(zip_path)
            res = json.loads(res_str)
            self.assertEqual(res["status"], "erro")
            self.assertIn("chave privada", res["mensagem"])
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_qml_navigation_from_cadastro_and_login_to_auditoria(self):
        """Valida que o botão de auditoria na tela de Cadastro e de Login abre a tela de Auditoria e retorna via stackView."""
        from pathlib import Path
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import QObject
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtQml import QQmlApplicationEngine
        from app.controllers.authController import AuthController
        from app.controllers.csvController import CsvController

        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        app = QGuiApplication.instance() or QGuiApplication([])
        engine = QQmlApplicationEngine()
        qml_dir = Path(__file__).resolve().parent.parent / "Design"
        engine.addImportPath(str(qml_dir))

        auth = AuthController()
        auth._is_registered = False  # Inicia na tela de cadastro

        engine.rootContext().setContextProperty('institutionalDomain', '@uesc.br')
        engine.rootContext().setContextProperty('backend', CsvController('@uesc.br'))
        engine.rootContext().setContextProperty('authController', auth)
        engine.rootContext().setContextProperty('tallyElectionController', self.controller)

        qml_app = qml_dir / "DesignContent" / "App.qml"
        engine.load(str(qml_app))

        self.assertTrue(len(engine.rootObjects()) > 0)
        root_obj = engine.rootObjects()[0]
        stack_view = root_obj.findChild(QObject, 'stackView')
        self.assertIsNotNone(stack_view)

        # 1. Navegação a partir da tela de Cadastro
        current_cadastro = stack_view.property('currentItem')
        self.assertIsNotNone(current_cadastro)
        self.assertEqual(stack_view.property('depth'), 1)

        # Clica em Auditar na tela de Cadastro
        current_cadastro.auditarClicked.emit()
        app.processEvents()

        self.assertEqual(stack_view.property('depth'), 2)
        auditoria_screen = stack_view.property('currentItem')
        self.assertIsNotNone(auditoria_screen)

        # Clica em Voltar na tela de Auditoria
        auditoria_screen.backClicked.emit()
        app.processEvents()

        self.assertEqual(stack_view.property('depth'), 1)


if __name__ == '__main__':
    unittest.main()
