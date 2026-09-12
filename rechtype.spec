# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_all


def package_files(name):
    try:
        return collect_all(name)
    except Exception:
        return [], [], []


packages = [
    package_files("vosk"),
    package_files("pyaudio"),
    package_files("gigaam"),
    package_files("sentencepiece"),
    package_files("av"),
    package_files("soundfile"),
    package_files("onnxruntime"),
]
binaries = sum((item[1] for item in packages), [])
datas = sum((item[0] for item in packages), [])
hiddenimports = sum((item[2] for item in packages), [])
model_root = Path(os.environ.get("RECHTYPE_MODEL_ROOT", "models")).resolve()

a = Analysis(
    ["run.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas
    + [
        (str(model_root / "vosk-model-small-ru-0.22"), "models/vosk-model-small-ru-0.22"),
        (str(model_root / "gigaam" / "v3_e2e_rnnt.ckpt"), "models/gigaam"),
        (
            str(model_root / "gigaam" / "v3_e2e_rnnt_tokenizer.model"),
            "models/gigaam",
        ),
        ("LICENSE", "."),
        ("THIRD_PARTY_NOTICES.md", "."),
        ("THIRD_PARTY_LICENSES", "THIRD_PARTY_LICENSES"),
        ("RELEASE-NOTES-v0.0.3.txt", "."),
    ],
    hiddenimports=hiddenimports
    + [
        "PyQt6.sip",
        "torch",
        "torchaudio",
        "hydra",
        "omegaconf",
        "gigaam",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Qt on Windows resolves the unversioned ``icuuc.dll`` to the operating-system
# ICU.  A polluted build PATH (for example, one containing Poppler) can make
# PyInstaller collect an incompatible third-party ICU instead and break Qt at
# startup.  Keep such accidental copies out of the frozen runtime.
excluded_runtime_binaries = {
    # Accidental copies from polluted build environments.
    "icuuc.dll",
    "icudt78.dll",
    # Qt plugins/modules not used by the text-only QWidget interface.
    "qt6pdf.dll",
    "qt6svg.dll",
    "qcertonlybackend.dll",
    "qgif.dll",
    "qicns.dll",
    "qico.dll",
    "qjpeg.dll",
    "qminimal.dll",
    "qoffscreen.dll",
    "qopensslbackend.dll",
    "qpdf.dll",
    "qschannelbackend.dll",
    "qsvg.dll",
    "qsvgicon.dll",
    "qtga.dll",
    "qtiff.dll",
    "qtuiotouchplugin.dll",
    "qwbmp.dll",
    "qwebp.dll",
}
a.binaries = [
    entry
    for entry in a.binaries
    if Path(entry[0]).name.lower() not in excluded_runtime_binaries
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RechType",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="RechType",
)
