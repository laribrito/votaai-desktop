# -*- mode: python ; coding: utf-8 -*-
import ctypes
import hashlib
import marshal
import os
import subprocess
import zlib
from pathlib import Path
from types import CodeType
from PyInstaller.config import CONF

SPEC_DIR = Path(SPECPATH).resolve()
NATIVE_C_SRC = SPEC_DIR / "app" / "services" / "votaai_native_core.c"
NATIVE_SO_OUT = SPEC_DIR / "app" / "services" / "_votaai_native_core.so"

# 1. Compila o núcleo nativo C com Control Flow Flattening (CFF), ocultação de símbolos e strip
subprocess.run(
    [
        "gcc",
        "-shared",
        "-fPIC",
        "-O2",
        "-fvisibility=hidden",
        str(NATIVE_C_SRC),
        "-o",
        str(NATIVE_SO_OUT),
    ],
    check=True,
)
subprocess.run(["strip", "--strip-unneeded", str(NATIVE_SO_OUT)], check=True)

# 2. Atualiza o manifesto de integridade SHA-256 + native_seal antes do empacotamento
subprocess.run(
    [
        str(SPEC_DIR / ".venv" / "bin" / "python"),
        "-m",
        "app.services.security_guard",
        "--update-manifest",
    ],
    cwd=str(SPEC_DIR),
    check=True,
)


def _strip_code_metadata(co: CodeType) -> CodeType:
    """Remove caminhos de arquivos originais recursivamente do CodeObject (docstrings já removidas via optimize=2)."""
    new_consts = tuple(
        _strip_code_metadata(c) if isinstance(c, CodeType) else c
        for c in co.co_consts
    )
    return co.replace(co_filename="<obf>", co_consts=new_consts)


def _build_cff_encrypted_loader(mod_name: str, orig_co: CodeType, native_lib: ctypes.CDLL) -> CodeType:
    """
    Serializa, comprime e cifra o CodeObject original com o stream cipher CFF nativo
    (_votaai_native_core.so) e retorna um stub de carregamento com fluxo de controle
    achatado (Control Flow Flattening) e símbolos locais de 2 caracteres (_s, _b, _k, ...).
    """
    sanitized_co = _strip_code_metadata(orig_co)
    raw_payload = zlib.compress(marshal.dumps(sanitized_co), level=9)
    seed = int.from_bytes(hashlib.sha256(mod_name.encode("utf-8")).digest()[:4], "little") | 1

    buf = (ctypes.c_uint8 * len(raw_payload)).from_buffer_copy(raw_payload)
    rc = native_lib.votaai_transform_bytecode(buf, len(raw_payload), ctypes.c_uint32(seed))
    if rc != 0:
        raise RuntimeError(f"Falha ao cifrar bytecode do módulo {mod_name}")
    encrypted_bytes = bytes(buf)

    loader_src = f"""
_s = 0
_b = bytearray({encrypted_bytes!r})
_k = {seed}
while _s < 8:
    if _s == 0:
        import sys as _y, os as _o, ctypes as _c, marshal as _m, zlib as _z
        _s = 1 if ((_k * (_k + 1)) & 1) == 0 else 7
    elif _s == 1:
        _r = getattr(_y, "_MEIPASS", _o.getcwd())
        _s = 2
    elif _s == 2:
        _l = _c.CDLL(_o.path.join(_r, "app", "services", "_votaai_native_core.so"))
        _s = 3
    elif _s == 3:
        _l.votaai_native_guard_check.argtypes = [_c.c_uint32]
        _l.votaai_native_guard_check.restype = _c.c_int
        if _l.votaai_native_guard_check(_c.c_uint32(_k)) != 0:
            _o._exit(1)
        _s = 4
    elif _s == 4:
        _l.votaai_transform_bytecode.argtypes = [_c.c_void_p, _c.c_size_t, _c.c_uint32]
        _l.votaai_transform_bytecode.restype = _c.c_int
        _f = (_c.c_uint8 * len(_b)).from_buffer(_b)
        _s = 5 if _l.votaai_transform_bytecode(_f, len(_b), _c.c_uint32(_k)) == 0 else 7
    elif _s == 5:
        _co = _m.loads(_z.decompress(bytes(_b)))
        _s = 6
    elif _s == 6:
        for _i in range(len(_b)):
            _b[_i] = 0
        exec(_co, globals())
        del _s, _b, _k, _y, _o, _c, _m, _z, _r, _l, _f, _co, _i
        break
    else:
        _o._exit(1)
"""
    return compile(loader_src, "<obf>", "exec", optimize=2)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(str(NATIVE_SO_OUT), 'app/services')],
    datas=[('Design', 'Design'), ('app/resources/api_routes.json', 'app/resources'), ('app/resources/initial_key.json', 'app/resources'), ('app/resources/integrity_manifest.json', 'app/resources'), ('app/resources/plus.png', 'app/resources'), ('app/resources/play.png', 'app/resources'), ('app/resources/close.png', 'app/resources'), ('app/resources/graph.png', 'app/resources'), ('.env', '.'), ('.venv/lib/python3.12/site-packages/PySide6/Qt/qml/QtQuick/Studio', 'PySide6/Qt/qml/QtQuick/Studio')],
    hiddenimports=['app.controllers.native.tpm_linux', 'app.controllers.native.cng_windows', 'app.controllers.native.enclave_mac'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'PySide6.Qt3DRender', 'PySide6.Qt3DCore', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtMultimedia', 'PySide6.QtPdf'],
    noarchive=False,
    optimize=2,
)

# 3. Ofusca e cifra todos os módulos 'app.*' dentro do cache de código do PYZ
_native_lib = ctypes.CDLL(str(NATIVE_SO_OUT))
_native_lib.votaai_transform_bytecode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
_native_lib.votaai_transform_bytecode.restype = ctypes.c_int

_code_cache = CONF['code_cache'].get(id(a.pure))
if _code_cache is None:
    _code_cache = {}
    CONF['code_cache'][id(a.pure)] = _code_cache

for _mod_name, _src_path, _typecode in a.pure:
    if (_mod_name == "app" or _mod_name.startswith("app.")) and _src_path and _src_path not in ("-", None):
        _orig_co = _code_cache.get(_mod_name)
        if _orig_co is None:
            _orig_co = compile(Path(_src_path).read_bytes(), "<obf>", "exec", optimize=2)
        _code_cache[_mod_name] = _build_cff_encrypted_loader(_mod_name, _orig_co, _native_lib)

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
