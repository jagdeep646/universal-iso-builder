# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir configuration for the portable Windows Qt application."""

import os
from pathlib import Path


ROOT = Path(SPECPATH).resolve().parent
APP_NAME = "Universal ISO Builder"
TARGET_ARCH = os.environ.get("UIB_TARGET_ARCH", "x86_64")
PACKAGE_NAME = f"{APP_NAME}-Windows-{TARGET_ARCH}"
ENTRYPOINT = ROOT / "universal_iso_builder.py"
QML_SOURCE = ROOT / "iso_builder" / "gui" / "qml"
VERSION_FILE = ROOT / "windows_version_info.txt"

a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(QML_SOURCE), "iso_builder/gui/qml")],
    hiddenimports=[],
    hookspath=[str(ROOT / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "_tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(VERSION_FILE),
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=PACKAGE_NAME,
)
