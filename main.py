import sys
from pathlib import Path
import os

# Disable QML disk cache to ensure fresh loading of UI files
os.environ["QML_DISABLE_DISK_CACHE"] = "1"

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from decouple import config

from app.controllers.csvController import CsvController

import PySide6
pyside_path = os.path.dirname(PySide6.__file__)
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(pyside_path)
    os.add_dll_directory(os.path.join(pyside_path, "qml", "QtQuick", "Controls", "Basic"))

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    
    # Aplica o estilo básico (o mesmo usado pelo Qt Design Studio)
    QQuickStyle.setStyle("Basic")
    
    engine = QQmlApplicationEngine()
    
    institutional_domain = config('INSTITUTIONAL_DOMAIN', default='@uesc.br')
    engine.rootContext().setContextProperty("institutionalDomain", institutional_domain)
    
    backend = CsvController(institutional_domain)
    engine.rootContext().setContextProperty("backend", backend)
    
    # Adicionando o caminho de importação das pastas do projeto QML (necessário pro Qt encontrar a pasta design)
    qml_dir = Path(__file__).parent / "Design"
    engine.addImportPath(str(qml_dir))
    
    # Carregando o arquivo principal gerado pelo Qt Design Studio
    qml_file = qml_dir / "DesignContent" / "App.qml"
    engine.load(qml_file)
    
    if not engine.rootObjects():
        sys.exit(-1)
        
    sys.exit(app.exec())
