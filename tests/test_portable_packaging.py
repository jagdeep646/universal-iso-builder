import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pyinstaller_specs_have_valid_python_syntax() -> None:
    for path in ("packaging/windows-portable.spec", "packaging/macos-portable.spec"):
        ast.parse(read_text(path), filename=path)


def test_windows_spec_is_qt_only_onedir_with_resources() -> None:
    spec = read_text("packaging/windows-portable.spec")

    assert 'ENTRYPOINT = ROOT / "universal_iso_builder.py"' in spec
    assert 'datas=[(str(QML_SOURCE), "iso_builder/gui/qml")]' in spec
    assert 'excludes=["tkinter", "_tkinter"]' in spec
    assert "exclude_binaries=True" in spec
    assert "console=False" in spec
    assert "upx=False" in spec
    assert "COLLECT(" in spec
    assert 'PACKAGE_NAME = f"{APP_NAME}-Windows-{TARGET_ARCH}"' in spec
    assert 'hookspath=[str(ROOT / "packaging" / "hooks")]' in spec


def test_windows_script_builds_and_verifies_complete_zip() -> None:
    script = read_text("build_portable_windows.ps1")

    assert "uv sync --locked --all-groups" in script
    assert "--smoke-test" in script
    assert "Compress-Archive" in script
    assert "Expand-Archive" in script
    assert "Get-FileHash -Algorithm SHA256" in script
    assert "python3*.dll" in script
    assert "_internal\\PySide6\\plugins" in script
    assert "Share the complete folder or ZIP" in script
    assert "--onefile" not in script


def test_macos_spec_is_target_native_qt_app_bundle() -> None:
    spec = read_text("packaging/macos-portable.spec")

    assert 'TARGET_ARCH not in {"arm64", "x86_64"}' in spec
    assert 'ENTRYPOINT = ROOT / "universal_iso_builder.py"' in spec
    assert 'datas=[(str(QML_SOURCE), "iso_builder/gui/qml")]' in spec
    assert 'excludes=["tkinter", "_tkinter"]' in spec
    assert "exclude_binaries=True" in spec
    assert "target_arch=TARGET_ARCH" in spec
    assert "BUNDLE(" in spec
    assert "UIB_CODESIGN_IDENTITY" in spec
    assert "universal2" not in spec
    assert 'hookspath=[str(ROOT / "packaging" / "hooks")]' in spec


def test_custom_qml_hook_excludes_unused_heavy_modules() -> None:
    hook = read_text("packaging/hooks/hook-PySide6.QtQml.py")

    assert '"QtQuick/Controls/Basic"' in hook
    assert '"QtQuick/Dialogs"' in hook
    assert '"QtQuick/Effects"' in hook
    assert '"Qt/labs/folderlistmodel"' in hook
    assert "QtWebEngine" not in hook
    assert "QtQuick3D" not in hook
    assert "QtCharts" not in hook


def test_macos_script_refuses_cross_build_and_verifies_archive() -> None:
    script = read_text("build_portable_macos.sh")

    assert '"$(uname -s)" != "Darwin"' in script
    assert "PYTHON_ARCH" in script
    assert "matching native Python environment" in script
    assert "ditto -c -k --sequesterRsrc --keepParent" in script
    assert 'unzip -t "$ZIP_FILE"' in script
    assert "shasum -a 256" in script
    assert "codesign --verify --deep --strict" in script
    assert "notarization NOT performed" in script
    assert 'rm -rf -- "$COLLECT_FOLDER"' in script
    assert "--onefile" not in script


def test_repository_tracks_specs_and_normalizes_portable_scripts() -> None:
    ignore = read_text(".gitignore")
    attributes = read_text(".gitattributes")

    assert "!packaging/*.spec" in ignore
    assert "*.spec text eol=lf" in attributes
    assert "*.sh text eol=lf" in attributes


def test_readme_documents_portable_outputs_and_target_machine_use() -> None:
    readme = read_text("README.md")

    assert "& '.\\build_portable_windows.ps1'" in readme
    assert "dist/Universal ISO Builder-Windows-x86_64.zip" in readme
    assert "does not need Python, uv, pip, PySide6, or PyInstaller" in readme
    assert "./build_portable_macos.sh arm64" in readme
    assert "./build_portable_macos.sh x86_64" in readme
    assert "not a universal2 binary" in readme
    assert "notarization is not performed" in readme
    assert "PyInstaller\nenables Hardened Runtime" in readme
    assert "xcrun notarytool submit" in readme
    assert "xcrun stapler staple" in readme
    assert "attach the ZIP and checksum to a GitHub" in readme
