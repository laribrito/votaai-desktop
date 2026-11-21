# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('Design', 'Design'), ('app/resources/api_routes.json', 'app/resources'), ('app/resources/initial_key.json', 'app/resources'), ('app/resources/integrity_manifest.json', 'app/resources'), ('app/resources/plus.png', 'app/resources'), ('app/resources/play.png', 'app/resources'), ('app/resources/close.png', 'app/resources'), ('app/resources/graph.png', 'app/resources'), ('.env', '.'), ('.venv/lib/python3.12/site-packages/PySide6/Qt/qml/QtQuick/Studio', 'PySide6/Qt/qml/QtQuick/Studio')],
    hiddenimports=['app.controllers.native.tpm_linux', 'app.controllers.native.cng_windows', 'app.controllers.native.enclave_mac'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'PySide6.Qt3DRender', 'PySide6.Qt3DCore', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtMultimedia', 'PySide6.QtPdf'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='votaai-desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
