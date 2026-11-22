import os
import sys
import json
import time
import ctypes
import hashlib
import platform
import threading
import subprocess
from pathlib import Path


class SecurityViolationError(RuntimeError):
    """Exceção lançada quando uma violação de segurança (Root, Debug ou Tamper) é detectada."""
    pass


# Módulos Python de depuração, instrumentação dinâmica e injeção proibidos em execução
FORBIDDEN_DEBUG_MODULES = {
    "pdb",
    "ipdb",
    "pudb",
    "pydevd",
    "debugpy",
    "frida",
    "pyinjector",
}

# Processos pais nativos associados a depuração e engenharia reversa
FORBIDDEN_PARENT_PROCESSES = {
    "gdb",
    "lldb",
    "strace",
    "ltrace",
    "radare2",
    "r2",
    "ida",
    "ida64",
    "ghidra",
    "frida",
    "frida-server",
    "valgrind",
    "x64dbg",
    "x32dbg",
    "ollydbg",
    "windbg",
}

# Variáveis de ambiente usadas para injeção de bibliotecas (hooking) e inspeção de runtime
FORBIDDEN_INJECTION_ENV_VARS = (
    "LD_PRELOAD",
    "LD_AUDIT",
    "DYLD_INSERT_LIBRARIES",
    "PYTHONINSPECT",
    "QML_IMPORT_TRACE",
    "QMLSCENE_DEVICE",
)

# Variáveis de ambiente que indicam execução via escalonamento de privilégios (sudo/pkexec)
PRIVILEGE_ESCALATION_ENV_VARS = (
    "SUDO_UID",
    "SUDO_USER",
    "SUDO_COMMAND",
    "PKEXEC_UID",
)


def get_project_root() -> Path:
    """Retorna o diretório raiz do projeto votaai-desktop (ou _MEIPASS quando empacotado em executável)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent.parent.parent


def get_manifest_path() -> Path:
    """Retorna o caminho do arquivo de manifesto de integridade SHA-256."""
    return get_project_root() / "app" / "resources" / "integrity_manifest.json"


# ─────────────────────────────────────────────────────────────────────────────
# 1. MECANISMOS CONTRA ROOT / PRIVILÉGIO ELEVADO (SEM SECURE BOOT)
# ─────────────────────────────────────────────────────────────────────────────

def check_root_or_elevated_privileges() -> tuple[bool, str]:
    """
    Verifica se o aplicativo está sendo executado como root, sudo ou Administrador.
    Retorna (violado: bool, motivo: str).
    """
    system = platform.system()

    if system in ("Linux", "Darwin"):
        # 1. Verifica UID / EUID igual a 0 (root)
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return True, "Execução direta como superusuário (euid=0) não é permitida."
        if hasattr(os, "getuid") and os.getuid() == 0:
            return True, "Execução direta como superusuário (uid=0) não é permitida."

        # 2. Verifica variáveis de escalonamento via sudo / pkexec
        for env_var in PRIVILEGE_ESCALATION_ENV_VARS:
            if os.environ.get(env_var):
                return True, f"Escalonamento de privilégio detectado via variável '{env_var}'."

    elif system == "Windows":
        try:
            if ctypes.windll.shell32.IsUserAnAdmin() != 0:
                return True, "Execução com privilégios de Administrador no Windows não é permitida."
        except Exception:
            pass

    return False, ""


def lock_process_privileges() -> bool:
    """
    Trava o processo atual no kernel Linux com PR_SET_NO_NEW_PRIVS = 1.
    Impede que o processo ou qualquer subprocesso adquira privilégios de root (ex: setuid/sudo).
    """
    if platform.system() == "Linux":
        try:
            libc = ctypes.CDLL("libc.so.6")
            PR_SET_NO_NEW_PRIVS = 38
            res = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
            return res == 0
        except Exception:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 2. MECANISMOS CONTRA DEPURAÇÃO (ANTI-DEBUGGING) E PROTEÇÃO DE MEMÓRIA
# ─────────────────────────────────────────────────────────────────────────────

def harden_process_memory() -> bool:
    """
    Aplica proteções de memória e bloqueia ganchos de depuração na inicialização:
    - Desativa breakpoint() nativo do Python (PYTHONBREAKPOINT=0) e limpa PYTHONSTARTUP.
    - Bloqueia flags de depuração do motor Qt/QML (-qmljsdebugger).
    - No Linux: configura prctl(PR_SET_DUMPABLE, 0) impedindo core dumps da RAM e ptrace.
    """
    os.environ["PYTHONBREAKPOINT"] = "0"
    os.environ.pop("PYTHONSTARTUP", None)

    for arg in list(sys.argv):
        if "qmljsdebugger" in arg.lower():
            os._exit(1)

    if platform.system() == "Linux":
        try:
            libc = ctypes.CDLL("libc.so.6")
            PR_SET_DUMPABLE = 4
            res = libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
            return res == 0
        except Exception:
            return False
    return True


def check_qml_debug_flags(argv=None) -> tuple[bool, str]:
    """Verifica se argumentos de depuração do motor QML foram passados na linha de comando."""
    args_to_check = argv if argv is not None else sys.argv
    for arg in args_to_check:
        if "qmljsdebugger" in str(arg).lower():
            return True, f"Flag de depuração QML detectada nos argumentos: '{arg}'."
    return False, ""


def check_python_debugger() -> tuple[bool, str]:
    """
    Detecta depuradores, tracers e ferramentas de instrumentação no runtime do Python:
    - sys.gettrace()
    - sys.monitoring (Python 3.12+)
    - Módulos de debug carregados em sys.modules (pdb, pydevd, debugpy, frida, etc.)
    """
    if sys.gettrace() is not None:
        return True, "Tracer Python ativo detectado via sys.gettrace()."

    if hasattr(sys, "monitoring"):
        try:
            for tool_id in range(6):
                tool_name = sys.monitoring.get_tool(tool_id)
                if tool_name is not None:
                    return True, f"Ferramenta de instrumentação ativa em sys.monitoring (id={tool_id}, tool='{tool_name}')."
        except Exception:
            pass

    loaded_modules = set(sys.modules.keys())
    found_forbidden = loaded_modules.intersection(FORBIDDEN_DEBUG_MODULES)
    if found_forbidden:
        return True, f"Módulo(s) de depuração carregado(s) na memória: {sorted(found_forbidden)}."

    return False, ""


def check_os_debugger() -> tuple[bool, str]:
    """
    Detecta depuradores nativos no nível do Sistema Operacional:
    - Linux: TracerPid em /proc/self/status e inspeção de processo pai (/proc/<ppid>/comm).
    - Windows: IsDebuggerPresent() e CheckRemoteDebuggerPresent() via kernel32.
    - macOS: Inspeção de processo pai (lldb, dtrace, frida).
    """
    system = platform.system()

    if system == "Linux":
        # 1. Verifica TracerPid em /proc/self/status
        try:
            with open("/proc/self/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("TracerPid:"):
                        tracer_pid = int(line.split(":", 1)[1].strip())
                        if tracer_pid != 0:
                            return True, f"Depurador nativo anexado detectado (TracerPid={tracer_pid})."
                        break
        except Exception:
            pass

        # 2. Verifica nome do processo pai (/proc/<ppid>/comm)
        try:
            ppid = os.getppid()
            if ppid > 1:
                comm_path = f"/proc/{ppid}/comm"
                if os.path.exists(comm_path):
                    with open(comm_path, "r", encoding="utf-8") as f:
                        parent_name = f.read().strip().lower()
                    if parent_name in FORBIDDEN_PARENT_PROCESSES:
                        return True, f"Processo pai suspeito de depuração detectado: '{parent_name}' (PID={ppid})."
        except Exception:
            pass

    elif system == "Windows":
        try:
            kernel32 = ctypes.windll.kernel32
            if kernel32.IsDebuggerPresent() != 0:
                return True, "Depurador nativo Windows detectado via IsDebuggerPresent()."

            is_remote_debugged = ctypes.c_bool(False)
            kernel32.CheckRemoteDebuggerPresent(
                kernel32.GetCurrentProcess(),
                ctypes.byref(is_remote_debugged),
            )
            if is_remote_debugged.value:
                return True, "Depurador remoto Windows detectado via CheckRemoteDebuggerPresent()."
        except Exception:
            pass

    elif system == "Darwin":
        try:
            ppid = os.getppid()
            if ppid > 1:
                res = subprocess.run(
                    ["ps", "-p", str(ppid), "-o", "comm="],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                parent_name = os.path.basename(res.stdout.strip()).lower()
                if parent_name in FORBIDDEN_PARENT_PROCESSES:
                    return True, f"Processo pai suspeito no macOS detectado: '{parent_name}'."
        except Exception:
            pass

    return False, ""


def zero_sensitive_bytes(buffer) -> None:
    """
    Sobrescreve explicitamente com zeros um buffer mutável (bytearray ou memoryview)
    na memória RAM para reduzir a janela de exposição de chaves privadas e votos decifrados.
    """
    if isinstance(buffer, bytearray):
        for i in range(len(buffer)):
            buffer[i] = 0
    elif isinstance(buffer, memoryview) and not buffer.readonly:
        buffer[:] = b"\x00" * len(buffer)


# ─────────────────────────────────────────────────────────────────────────────
# 3. MECANISMOS CONTRA ADULTERAÇÃO (ANTI-TAMPERING E INTEGRIDADE)
# ─────────────────────────────────────────────────────────────────────────────

def check_environment_injection() -> tuple[bool, str]:
    """
    Verifica variáveis de ambiente usadas para injetar bibliotecas compartilhadas
    ou interceptar chamadas de sistema (LD_PRELOAD, DYLD_INSERT_LIBRARIES, etc.).
    """
    for env_var in FORBIDDEN_INJECTION_ENV_VARS:
        val = os.environ.get(env_var)
        if val:
            return True, f"Variável de injeção/hooking detectada no ambiente: '{env_var}={val}'."
    return False, ""


def _compute_file_sha256(file_path: Path) -> str:
    """Calcula o hash SHA-256 do conteúdo normalizado (LF) de um arquivo."""
    h = hashlib.sha256()
    raw = file_path.read_bytes()
    # Normaliza quebras de linha CRLF -> LF para consistência entre Linux/Windows/macOS
    normalized = raw.replace(b"\r\n", b"\n")
    h.update(normalized)
    return h.hexdigest()


def collect_protected_files(project_root: Path = None) -> list[Path]:
    """
    Lista todos os arquivos críticos de código (.py), interface (.qml / .ui.qml)
    e chave pública ancorada do servidor (app/resources/initial_key.json)
    que compõem a aplicação e devem ter sua integridade monitorada.
    """
    root = project_root or get_project_root()
    protected = []

    main_py = root / "main.py"
    if main_py.exists():
        protected.append(main_py)

    app_dir = root / "app"
    if app_dir.exists():
        for py_file in sorted(app_dir.rglob("*.py")):
            if "__pycache__" not in py_file.parts:
                protected.append(py_file)

    initial_key = root / "app" / "resources" / "initial_key.json"
    if initial_key.exists():
        protected.append(initial_key)

    design_dir = root / "Design"
    if design_dir.exists():
        for qml_file in sorted(design_dir.rglob("*.qml")):
            protected.append(qml_file)

    return sorted(protected, key=lambda p: p.relative_to(root).as_posix())


def generate_integrity_manifest(project_root: Path = None, save: bool = True) -> dict:
    """
    Calcula o hash SHA-256 de todos os arquivos .py e .qml críticos do projeto
    e gera o manifesto criptográfico de integridade com um root_hash canônico.
    """
    root = project_root or get_project_root()
    files_map = {}

    for file_path in collect_protected_files(root):
        rel_path = file_path.relative_to(root).as_posix()
        files_map[rel_path] = _compute_file_sha256(file_path)

    canonical_entries = json.dumps(files_map, sort_keys=True, separators=(",", ":")).encode("utf-8")
    root_hash = hashlib.sha256(canonical_entries).hexdigest()

    manifest = {
        "algorithm": "SHA-256",
        "root_hash": root_hash,
        "file_count": len(files_map),
        "files": files_map,
    }

    if save:
        manifest_path = root / "app" / "resources" / "integrity_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

    return manifest


def verify_file_integrity(project_root: Path = None, manifest_path: Path = None) -> tuple[bool, str]:
    """
    Valida a integridade criptográfica (SHA-256) de todos os arquivos Python e QML
    contra o manifesto oficial assinado (app/resources/integrity_manifest.json).
    Detecta:
    1. Ausência ou corrupção do manifesto ou do root_hash.
    2. Modificação de qualquer arquivo .py ou .qml listado.
    3. Remoção de qualquer arquivo obrigatório.
    4. Injeção de arquivos .py ou .qml não autorizados nos diretórios app/ ou Design/.
    """
    root = project_root or get_project_root()
    m_path = manifest_path or (root / "app" / "resources" / "integrity_manifest.json")

    if not m_path.exists():
        return True, f"Manifesto de integridade ausente: '{m_path}'."

    try:
        with open(m_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        return True, f"Falha ao ler manifesto de integridade: {e}"

    expected_files = manifest.get("files")
    expected_root_hash = manifest.get("root_hash")
    if not isinstance(expected_files, dict) or not expected_root_hash:
        return True, "Estrutura inválida no manifesto de integridade."

    # 1. Verifica se o próprio manifesto teve a tabela de hashes adulterada
    canonical_entries = json.dumps(expected_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    calculated_root_hash = hashlib.sha256(canonical_entries).hexdigest()
    if calculated_root_hash != expected_root_hash:
        return True, "Adulteração detectada no root_hash do manifesto de integridade."

    is_frozen_bundle = getattr(sys, "frozen", False) and project_root is None

    # 2. Verifica cada arquivo esperado
    for rel_path, expected_hash in expected_files.items():
        abs_path = root / rel_path
        # No executável congelado (PyInstaller), módulos .py ficam compilados dentro do arquivo ELF (PYZ),
        # enquanto arquivos .qml permanecem em _MEIPASS/Design e são sempre validados em disco.
        if is_frozen_bundle and rel_path.endswith(".py") and not abs_path.exists():
            continue
        if not abs_path.exists():
            return True, f"Arquivo crítico removido ou ausente: '{rel_path}'."
        actual_hash = _compute_file_sha256(abs_path)
        if actual_hash != expected_hash:
            return True, f"Adulteração de código/interface detectada no arquivo '{rel_path}'."

    # 3. Verifica se arquivos .py ou .qml extras não autorizados foram injetados
    current_files = {p.relative_to(root).as_posix() for p in collect_protected_files(root)}
    if is_frozen_bundle:
        current_assets = {f for f in current_files if not f.endswith(".py")}
        expected_assets = {f for f in expected_files.keys() if not f.endswith(".py")}
        unexpected_files = current_assets - expected_assets
    else:
        unexpected_files = current_files - set(expected_files.keys())

    if unexpected_files:
        return True, f"Arquivo(s) não autorizado(s) injetado(s) no projeto: {sorted(unexpected_files)}."

    return False, ""


# Registro em memória de fingerprints de bytecode para proteção Anti-Monkey-Patching
_FUNCTION_FINGERPRINTS: dict[str, tuple[int, str]] = {}
_FINGERPRINT_LOCK = threading.Lock()


def _compute_callable_fingerprint(func) -> tuple[int, str]:
    """Calcula a identidade e o hash SHA-256 do bytecode de uma função Python."""
    target = getattr(func, "__func__", func)
    code_obj = getattr(target, "__code__", None)
    if code_obj is not None:
        h = hashlib.sha256()
        h.update(code_obj.co_code)
        h.update(repr(code_obj.co_consts).encode("utf-8"))
        return id(target), h.hexdigest()
    return id(target), repr(target)


def register_critical_functions(functions_dict: dict[str, object] = None) -> None:
    """
    Salva o fingerprint do bytecode e endereço de memória de funções críticas
    para detectar monkey-patching ou hooking em tempo de execução.
    """
    if functions_dict is None:
        from app.controllers.cryptoController import CryptoController
        from app.controllers.encryptionController import EncryptionController
        from app.services.http_client import HttpClient

        functions_dict = {
            "os.urandom": os.urandom,
            "subprocess.run": subprocess.run,
            "CryptoController.sign_data": CryptoController.sign_data,
            "CryptoController.decrypt_data": CryptoController.decrypt_data,
            "CryptoController.decrypt_vote": CryptoController.decrypt_vote,
            "CryptoController.export_election_private_key": CryptoController.export_election_private_key,
            "EncryptionController.encrypt_payload": EncryptionController.encrypt_payload,
            "EncryptionController.decrypt_response": EncryptionController.decrypt_response,
            "HttpClient.post": HttpClient.post,
        }

    with _FINGERPRINT_LOCK:
        for name, fn in functions_dict.items():
            _FUNCTION_FINGERPRINTS[name] = _compute_callable_fingerprint(fn)


def check_runtime_monkey_patching(functions_dict: dict[str, object] = None) -> tuple[bool, str]:
    """
    Verifica se alguma função crítica registrada foi substituída (monkey-patched)
    ou teve seu bytecode alterado na memória RAM.
    """
    with _FINGERPRINT_LOCK:
        if not _FUNCTION_FINGERPRINTS:
            return False, ""
        snapshot = dict(_FUNCTION_FINGERPRINTS)

    if functions_dict is None:
        from app.controllers.cryptoController import CryptoController
        from app.controllers.encryptionController import EncryptionController
        from app.services.http_client import HttpClient

        functions_dict = {
            "os.urandom": os.urandom,
            "subprocess.run": subprocess.run,
            "CryptoController.sign_data": CryptoController.sign_data,
            "CryptoController.decrypt_data": CryptoController.decrypt_data,
            "CryptoController.decrypt_vote": CryptoController.decrypt_vote,
            "CryptoController.export_election_private_key": CryptoController.export_election_private_key,
            "EncryptionController.encrypt_payload": EncryptionController.encrypt_payload,
            "EncryptionController.decrypt_response": EncryptionController.decrypt_response,
            "HttpClient.post": HttpClient.post,
        }

    for name, expected_fp in snapshot.items():
        if name not in functions_dict:
            continue
        current_fp = _compute_callable_fingerprint(functions_dict[name])
        if current_fp != expected_fp:
            return True, f"Adulteração em memória (monkey-patching) detectada na função '{name}'."

    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# 4. ORQUESTRADOR UNIFICADO E WATCHDOG CONTÍNUO
# ─────────────────────────────────────────────────────────────────────────────

class SecurityGuard:
    """
    Orquestrador central dos esquemas:
    1. Anti-Root / Privilégio Elevado (sem Secure Boot)
    2. Anti-Depuração (Python + SO Nativo + QML + Proteção de Dump de RAM)
    3. Anti-Adulteração (Manifesto SHA-256 de .py/.qml + Anti-Injeção + Anti-Monkey-Patch)
    """
    _watchdog_started = False
    _lock = threading.Lock()

    @staticmethod
    def is_enabled() -> bool:
        """
        Retorna True se o SecurityGuard estiver ativo.
        Pode ser configurado via variável de ambiente VOTAAI_SECURITY_GUARD (padrão: '1').
        """
        val = os.environ.get("VOTAAI_SECURITY_GUARD", "1").strip().lower()
        return val not in ("0", "false", "off", "disabled")

    @classmethod
    def run_all_checks(cls, check_files: bool = True) -> tuple[bool, str]:
        """
        Executa todas as verificações de segurança.
        Retorna (violado: bool, motivo: str).
        """
        # 1. Anti-Root / Privilégio Elevado
        violated, reason = check_root_or_elevated_privileges()
        if violated:
            return True, f"[Anti-Root] {reason}"

        # 2. Anti-Depuração (Flags QML, Python Runtime e SO Nativo)
        for check_fn in (check_qml_debug_flags, check_python_debugger, check_os_debugger):
            violated, reason = check_fn()
            if violated:
                return True, f"[Anti-Debug] {reason}"

        # 3. Anti-Adulteração (Injeção de Ambiente, Monkey-Patching e Integridade de Arquivos)
        violated, reason = check_environment_injection()
        if violated:
            return True, f"[Anti-Tamper] {reason}"

        violated, reason = check_runtime_monkey_patching()
        if violated:
            return True, f"[Anti-Tamper] {reason}"

        if check_files:
            violated, reason = verify_file_integrity()
            if violated:
                return True, f"[Anti-Tamper] {reason}"

        return False, ""

    @classmethod
    def enforce(cls, check_files: bool = False, abort_on_violation: bool = True) -> None:
        """
        Valida imediatamente o estado de segurança do processo.
        Caso detecte violação, encerra o processo de forma imediata via os._exit(1)
        (impedindo que um depurador intercepte a exceção SystemExit) ou lança SecurityViolationError.
        """
        if not cls.is_enabled():
            return

        violated, reason = cls.run_all_checks(check_files=check_files)
        if violated:
            try:
                sys.stderr.write(f"\n[VotaAI SecurityGuard] VIOLAÇÃO CRÍTICA DETECTADA: {reason}\n")
                sys.stderr.flush()
            except Exception:
                pass
            if abort_on_violation:
                os._exit(1)
            raise SecurityViolationError(reason)

    @classmethod
    def initialize(cls, start_watchdog: bool = True, interval_seconds: float = 2.0) -> None:
        """
        Inicializa todas as travas de kernel/SO, registra as funções críticas em memória,
        valida a integridade SHA-256 dos arquivos .py/.qml e inicia o Watchdog em background.
        """
        if not cls.is_enabled():
            return

        # 1. Hardening no nível do Sistema Operacional e Kernel
        harden_process_memory()
        lock_process_privileges()

        # 2. Snapshot de funções críticas contra Monkey-Patching
        register_critical_functions()

        # 3. Verificação completa inicial (incluindo integridade SHA-256 em disco)
        cls.enforce(check_files=True, abort_on_violation=True)

        # 4. Watchdog contínuo em thread daemon
        if start_watchdog:
            with cls._lock:
                if not cls._watchdog_started:
                    cls._watchdog_started = True
                    t = threading.Thread(
                        target=cls._watchdog_loop,
                        args=(interval_seconds,),
                        daemon=True,
                        name="VotaAISecurityWatchdog",
                    )
                    t.start()

    @classmethod
    def _watchdog_loop(cls, interval_seconds: float) -> None:
        """Loop contínuo em background para detectar debuggers anexados ou adulterações após o boot."""
        tick = 0
        while True:
            time.sleep(interval_seconds)
            tick += 1
            # Revalida integridade de arquivos em disco a cada 5 ciclos e memória/debuggers a cada ciclo
            check_disk = (tick % 5 == 0)
            cls.enforce(check_files=check_disk, abort_on_violation=True)


if __name__ == "__main__":
    if "--update-manifest" in sys.argv:
        manifest = generate_integrity_manifest(save=True)
        print(
            f"[VotaAI SecurityGuard] Manifesto de integridade atualizado com sucesso "
            f"({manifest['file_count']} arquivos, root_hash={manifest['root_hash']})."
        )
    elif "--verify" in sys.argv:
        violated, reason = SecurityGuard.run_all_checks(check_files=True)
        if violated:
            print(f"[VotaAI SecurityGuard] FALHA na verificação: {reason}")
            sys.exit(1)
        print("[VotaAI SecurityGuard] Todas as verificações (Anti-Root, Anti-Debug, Anti-Tamper) passaram com sucesso.")
    else:
        print("Uso: python -m app.services.security_guard [--update-manifest | --verify]")
