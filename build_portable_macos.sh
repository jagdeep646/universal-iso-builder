#!/usr/bin/env bash
# Build and verify a target-native portable macOS Qt .app and ZIP.

set -euo pipefail

APP_NAME="Universal ISO Builder"
PYINSTALLER_VERSION="6.21.0"
PYSIDE_VERSION="6.11.1"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$ROOT/.venv/bin/python"
SPEC="$ROOT/packaging/macos-portable.spec"
DIST="$ROOT/dist"
BUILD="$ROOT/build"
TARGET_ARCH="${1:-}"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "ERROR: macOS packages must be built on macOS." >&2
    exit 1
fi
if [[ "$TARGET_ARCH" != "arm64" && "$TARGET_ARCH" != "x86_64" ]]; then
    echo "Usage: ./build_portable_macos.sh arm64|x86_64" >&2
    exit 2
fi
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: pinned environment missing. Run 'uv sync --locked --all-groups' first." >&2
    exit 1
fi

PYTHON_ARCH="$($PYTHON -c 'import platform; print(platform.machine())')"
if [[ "$PYTHON_ARCH" != "$TARGET_ARCH" ]]; then
    echo "ERROR: Python architecture '$PYTHON_ARCH' does not match requested '$TARGET_ARCH'." >&2
    echo "Use a matching native Python environment (Rosetta x86_64 Python for x86_64 on Apple Silicon)." >&2
    exit 1
fi

PACKAGE_NAME="$APP_NAME-macOS-$TARGET_ARCH"
APP_BUNDLE="$DIST/$PACKAGE_NAME.app"
COLLECT_FOLDER="$DIST/$PACKAGE_NAME"
ZIP_FILE="$DIST/$PACKAGE_NAME.zip"
CHECKSUM_FILE="$ZIP_FILE.sha256.txt"
WORK_PATH="$BUILD/portable-macos-$TARGET_ARCH"
APP_EXECUTABLE="$APP_BUNDLE/Contents/MacOS/$APP_NAME"
QML_MAIN="$APP_BUNDLE/Contents/Resources/iso_builder/gui/qml/Main.qml"

"$PYTHON" -c "import PyInstaller, PySide6; assert PyInstaller.__version__ == '$PYINSTALLER_VERSION'; assert PySide6.__version__ == '$PYSIDE_VERSION'; print('Packaging dependencies:', PyInstaller.__version__, PySide6.__version__)"
QT_QPA_PLATFORM=offscreen "$PYTHON" -B -m iso_builder.gui.qt_app --smoke-test

rm -rf -- "$APP_BUNDLE" "$COLLECT_FOLDER" "$WORK_PATH"
rm -f -- "$ZIP_FILE" "$CHECKSUM_FILE"

export UIB_TARGET_ARCH="$TARGET_ARCH"
"$PYTHON" -m PyInstaller --noconfirm --clean --distpath "$DIST" --workpath "$WORK_PATH" "$SPEC"

# BUNDLE is the distributable macOS output; remove COLLECT's intermediate onedir tree.
rm -rf -- "$COLLECT_FOLDER"

[[ -x "$APP_EXECUTABLE" ]] || { echo "ERROR: app executable missing: $APP_EXECUTABLE" >&2; exit 1; }
[[ -f "$QML_MAIN" ]] || { echo "ERROR: packaged QML missing: $QML_MAIN" >&2; exit 1; }

QT_QPA_PLATFORM=offscreen "$APP_EXECUTABLE" --smoke-test
lipo -info "$APP_EXECUTABLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

ditto -c -k --sequesterRsrc --keepParent "$APP_BUNDLE" "$ZIP_FILE"
unzip -t "$ZIP_FILE"
ZIP_HASH="$(shasum -a 256 "$ZIP_FILE" | awk '{print $1}')"
printf '%s  %s\n' "$ZIP_HASH" "$(basename "$ZIP_FILE")" > "$CHECKSUM_FILE"

if [[ -n "${UIB_CODESIGN_IDENTITY:-}" ]]; then
    SIGNING_STATUS="Developer ID identity requested: $UIB_CODESIGN_IDENTITY"
else
    SIGNING_STATUS="Ad-hoc signed by PyInstaller; notarization NOT performed"
fi

echo ""
echo "PORTABLE macOS BUILD PASS"
echo "Architecture: $TARGET_ARCH"
echo "App: $APP_BUNDLE"
echo "ZIP: $ZIP_FILE"
echo "ZIP bytes: $(stat -f '%z' "$ZIP_FILE")"
echo "ZIP SHA256: $ZIP_HASH"
echo "Checksum: $CHECKSUM_FILE"
echo "Signing: $SIGNING_STATUS"
