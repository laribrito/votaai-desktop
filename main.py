import sys
from pathlib import Path
import os

# Disable QML disk cache to ensure fresh loading of UI files
os.environ["QML_DISABLE_DISK_CACHE"] = "1"

# No Linux (Wayland/GNOME/Zorin OS), utiliza xcb (XWayland) por padrão para garantir
# que o gerenciador de janelas renderize a barra de título nativa com botão de fechar (X) e minimizar.
if sys.platform.startswith("linux") and os.environ.get("DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb"

def _bootstrap_env_for_executable():
    """Garante que o arquivo .env seja carregado mesmo quando executado como binário Linux congelado."""
    if not getattr(sys, "frozen", False):
        return
    exe_dir = Path(sys.executable).resolve().parent
    bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir)).resolve()
    for candidate in (exe_dir / ".env", exe_dir.parent / ".env", bundle_dir / ".env"):
        if candidate.is_file():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            except Exception:
                pass
            break

_bootstrap_env_for_executable()

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from decouple import config

from app.controllers.csvController import CsvController
from app.controllers.authController import AuthController
from app.services.security_guard import SecurityGuard

import PySide6
pyside_path = os.path.dirname(PySide6.__file__)
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(pyside_path)
    os.add_dll_directory(os.path.join(pyside_path, "qml", "QtQuick", "Controls", "Basic"))

if __name__ == "__main__":
    # Ativa os esquemas de defesa: Anti-Root, Anti-Depuração, Anti-Adulteração e Watchdog contínuo
    SecurityGuard.initialize(start_watchdog=True, interval_seconds=2.0)

    app = QGuiApplication(sys.argv)
    
    # Aplica o estilo básico (o mesmo usado pelo Qt Design Studio)
    QQuickStyle.setStyle("Basic")
    
    engine = QQmlApplicationEngine()
    
    institutional_domain = config('INSTITUTIONAL_DOMAIN', default='@uesc.br')
    engine.rootContext().setContextProperty("institutionalDomain", institutional_domain)
    
    backend = CsvController(institutional_domain)
    engine.rootContext().setContextProperty("backend", backend)
    
    auth_controller = AuthController()
    engine.rootContext().setContextProperty("authController", auth_controller)
    
    from app.controllers.electionController import ElectionController
    election_controller = ElectionController(csv_controller=backend)
    engine.rootContext().setContextProperty("electionController", election_controller)
    
    from app.controllers.startElectionController import StartElectionController
    start_election_controller = StartElectionController()
    engine.rootContext().setContextProperty("startElectionController", start_election_controller)
    
    from app.controllers.closeElectionController import CloseElectionController
    close_election_controller = CloseElectionController()
    engine.rootContext().setContextProperty("closeElectionController", close_election_controller)
    
    from app.controllers.tallyElectionController import TallyElectionController
    tally_election_controller = TallyElectionController()
    engine.rootContext().setContextProperty("tallyElectionController", tally_election_controller)
    
    # Adicionando o caminho de importação das pastas do projeto QML (necessário pro Qt encontrar a pasta design)
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    qml_dir = base_dir / "Design"
    engine.addImportPath(str(qml_dir))

    for qt_qml_candidate in (
        Path(pyside_path) / "Qt" / "qml",
        Path(pyside_path) / "qml",
        base_dir / "PySide6" / "Qt" / "qml",
    ):
        if qt_qml_candidate.is_dir():
            engine.addImportPath(str(qt_qml_candidate))
    
    # Carregando o arquivo principal gerado pelo Qt Design Studio
    qml_file = qml_dir / "DesignContent" / "App.qml"
    engine.load(qml_file)
    
    if not engine.rootObjects():
        sys.exit(-1)
        
    sys.exit(app.exec())
