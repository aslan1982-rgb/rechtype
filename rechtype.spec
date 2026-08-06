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
    package_files("soundfile"),
    package_files("onnxruntime"),
]
binaries = sum((item[0] for item in packages), [])
datas = sum((item[1] for item in packages), [])
hiddenimports = sum((item[2] for item in packages), [])
model_root = Path(os.environ.get("RECHTYPE_MODEL_ROOT", "models")).resolve()

a = Analysis(
    ["run.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas
    + [
        (str(model_root / "vosk-model-small-ru-0.22"), "models/vosk-model-small-ru-0.22"),
        (str(model_root / "gigaam"), "models/gigaam"),
        ("LICENSE", "."),
        ("THIRD_PARTY_NOTICES.md", "."),
        ("RELEASE-NOTES-v0.0.1.txt", "."),
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
