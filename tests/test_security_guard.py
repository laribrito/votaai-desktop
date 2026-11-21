import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

from app.services import security_guard
from app.services.security_guard import (
    SecurityGuard,
    SecurityViolationError,
    check_root_or_elevated_privileges,
    lock_process_privileges,
    harden_process_memory,
    check_qml_debug_flags,
    check_python_debugger,
    check_os_debugger,
    zero_sensitive_bytes,
    check_environment_injection,
    generate_integrity_manifest,
    verify_file_integrity,
    register_critical_functions,
    check_runtime_monkey_patching,
)


class TestSecurityGuard(unittest.TestCase):
    def setUp(self):
        # Limpa snapshots de monkey-patching antes de cada teste
        security_guard._FUNCTION_FINGERPRINTS.clear()

    def tearDown(self):
        security_guard._FUNCTION_FINGERPRINTS.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Testes Contra Root / Privilégio Elevado (Sem Secure Boot)
    # ─────────────────────────────────────────────────────────────────────────

    def test_anti_root_clean_environment_passes(self):
        with patch("platform.system", return_value="Linux"), \
             patch("os.geteuid", return_value=1000), \
             patch("os.getuid", return_value=1000), \
             patch.dict(os.environ, {}, clear=False):
            for var in security_guard.PRIVILEGE_ESCALATION_ENV_VARS:
                os.environ.pop(var, None)
            violated, reason = check_root_or_elevated_privileges()
            self.assertFalse(violated, reason)

    def test_anti_root_detects_euid_zero(self):
        with patch("platform.system", return_value="Linux"), \
             patch("os.geteuid", return_value=0):
            violated, reason = check_root_or_elevated_privileges()
            self.assertTrue(violated)
            self.assertIn("euid=0", reason)

    def test_anti_root_detects_sudo_env(self):
        with patch("platform.system", return_value="Linux"), \
             patch("os.geteuid", return_value=1000), \
             patch("os.getuid", return_value=1000), \
             patch.dict(os.environ, {"SUDO_UID": "1000"}):
            violated, reason = check_root_or_elevated_privileges()
            self.assertTrue(violated)
            self.assertIn("SUDO_UID", reason)

    def test_anti_root_lock_process_privileges(self):
        # Deve executar sem erro no Linux (PR_SET_NO_NEW_PRIVS)
        res = lock_process_privileges()
        self.assertIsInstance(res, bool)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Testes Contra Depuração (Anti-Debugging e Memória)
    # ─────────────────────────────────────────────────────────────────────────

    def test_anti_debug_detects_qmljsdebugger_flag(self):
        violated, reason = check_qml_debug_flags(["main.py", "-qmljsdebugger=port:3768,block"])
        self.assertTrue(violated)
        self.assertIn("qmljsdebugger", reason)

    def test_anti_debug_detects_sys_gettrace(self):
        with patch("sys.gettrace", return_value=lambda *args: None):
            violated, reason = check_python_debugger()
            self.assertTrue(violated)
            self.assertIn("sys.gettrace()", reason)

    def test_anti_debug_detects_forbidden_module_in_sys_modules(self):
        with patch("sys.gettrace", return_value=None), \
             patch.dict(sys.modules, {"pydevd": object()}):
            violated, reason = check_python_debugger()
            self.assertTrue(violated)
            self.assertIn("pydevd", reason)

    def test_anti_debug_detects_linux_tracer_pid(self):
        fake_proc_status = "Name:\tpython\nState:\tR (running)\nTracerPid:\t4242\nUid:\t1000\n"
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", mock_open(read_data=fake_proc_status)):
            violated, reason = check_os_debugger()
            self.assertTrue(violated)
            self.assertIn("TracerPid=4242", reason)

    def test_anti_debug_detects_suspicious_parent_process(self):
        def custom_open(path, *args, **kwargs):
            if path == "/proc/self/status":
                return mock_open(read_data="Name:\tpython\nTracerPid:\t0\n")()
            if path.endswith("/comm"):
                return mock_open(read_data="gdb\n")()
            raise FileNotFoundError(path)

        with patch("platform.system", return_value="Linux"), \
             patch("os.getppid", return_value=999), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=custom_open):
            violated, reason = check_os_debugger()
            self.assertTrue(violated)
            self.assertIn("gdb", reason)

    def test_zero_sensitive_bytes_wipes_memory(self):
        secret = bytearray(b"BEGIN PRIVATE KEY SECRET MATERIAL 123456")
        zero_sensitive_bytes(secret)
        self.assertEqual(secret, bytearray(len(secret)))
        self.assertTrue(all(b == 0 for b in secret))

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Testes Contra Adulteração (Anti-Tampering e Anti-Monkey-Patching)
    # ─────────────────────────────────────────────────────────────────────────

    def test_anti_tamper_detects_ld_preload_injection(self):
        with patch.dict(os.environ, {"LD_PRELOAD": "/tmp/evil_hook.so"}):
            violated, reason = check_environment_injection()
            self.assertTrue(violated)
            self.assertIn("LD_PRELOAD", reason)

    def test_anti_tamper_manifest_verification_on_real_project(self):
        violated, reason = verify_file_integrity()
        self.assertFalse(violated, f"O manifesto real do projeto deveria estar íntegro: {reason}")

    def test_anti_tamper_detects_modified_removed_and_injected_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app").mkdir()
            (root / "Design").mkdir()

            py_file = root / "app" / "logic.py"
            qml_file = root / "Design" / "View.qml"
            py_file.write_text("def vote():\n    return True\n", encoding="utf-8")
            qml_file.write_text("import QtQuick 2.15\nItem {}\n", encoding="utf-8")

            # Gera manifesto válido
            generate_integrity_manifest(project_root=root, save=True)
            violated, reason = verify_file_integrity(project_root=root)
            self.assertFalse(violated, reason)

            # Caso 1: Adulteração de arquivo QML
            qml_file.write_text("import QtQuick 2.15\nItem { /* tampered */ }\n", encoding="utf-8")
            violated, reason = verify_file_integrity(project_root=root)
            self.assertTrue(violated)
            self.assertIn("Design/View.qml", reason)

            # Restaura o QML original
            qml_file.write_text("import QtQuick 2.15\nItem {}\n", encoding="utf-8")
            violated, _ = verify_file_integrity(project_root=root)
            self.assertFalse(violated)

            # Caso 2: Injeção de arquivo .py extra não autorizado
            injected = root / "app" / "backdoor.py"
            injected.write_text("import os\n", encoding="utf-8")
            violated, reason = verify_file_integrity(project_root=root)
            self.assertTrue(violated)
            self.assertIn("app/backdoor.py", reason)
            injected.unlink()

            # Caso 3: Remoção de arquivo obrigatório
            py_file.unlink()
            violated, reason = verify_file_integrity(project_root=root)
            self.assertTrue(violated)
            self.assertIn("app/logic.py", reason)

    def test_anti_tamper_detects_runtime_monkey_patching(self):
        def original_fn(x):
            return x + 1

        def tampered_fn(x):
            return x + 999

        targets = {"critical_op": original_fn}
        register_critical_functions(targets)

        violated, reason = check_runtime_monkey_patching(targets)
        self.assertFalse(violated, reason)

        # Simula monkey-patching em memória
        targets["critical_op"] = tampered_fn
        violated, reason = check_runtime_monkey_patching(targets)
        self.assertTrue(violated)
        self.assertIn("critical_op", reason)

    def test_security_guard_enforce_raises_when_abort_disabled(self):
        with patch.dict(os.environ, {"LD_PRELOAD": "/tmp/hook.so"}):
            with self.assertRaises(SecurityViolationError):
                SecurityGuard.enforce(check_files=False, abort_on_violation=False)


if __name__ == "__main__":
    unittest.main()
