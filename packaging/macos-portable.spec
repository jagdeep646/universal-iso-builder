# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller target-native .app configuration for the portable Qt application."""

import os
from pathlib import Path


ROOT = Path(SPECPATH).resolve().parent
APP_NAME = "Universal ISO Builder"
TARGET_ARCH = os.environ.get("UIB_TARGET_ARCH", "arm64")
if TARGET_ARCH not in {"arm64", "x86_64"}:
    raise ValueError(f"Unsupported macOS target architecture: {TARGET_ARCH}")

PACKAGE_NAME = f"{APP_NAME}-macOS-{TARGET_ARCH}"
ENTRYPOINT = ROOT / "universal_iso_builder.py"
QML_SOURCE = ROOT / "iso_builder" / "gui" / "qml"
CODESIGN_IDENTITY = os.environ.get("UIB_CODESIGN_IDENTITY") or None

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
    target_arch=TARGET_ARCH,
    codesign_identity=CODESIGN_IDENTITY,
    entitlements_file=None,
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

app = BUNDLE(
    coll,
    name=f"{PACKAGE_NAME}.app",
    icon=None,
    bundle_identifier="io.github.jagdeep646.universal-iso-builder",
    info_plist={
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": "2.0",
        "CFBundleVersion": "2.0.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
)
