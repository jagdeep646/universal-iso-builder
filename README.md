# Universal ISO Builder

Universal ISO Builder 2.0 creates non-bootable data ISO images from folders. The default
desktop interface uses PySide6 and Qt Quick. A legacy Tkinter interface is retained for
compatibility.

The app scans the source folder, validates the requested output, shows the backend
command, creates the ISO through a temporary transactional output, and can generate a
SHA256 checksum.

> Current scope: personal/internal use. Windows 10 is verified. Windows 11, macOS, and
> Linux runtime remain **NOT VERIFIED**.

## Choose a Setup Method

- **uv (recommended):** reproduces the locked environment from `pyproject.toml` and
  `uv.lock`.
- **pip:** installs the pinned GUI requirement, but does not reproduce the complete
  transitive lockfile.

Do not mix uv and pip commands in the same fresh virtual environment.

| Launcher | Interface | Use |
|---|---|---|
| `universal_iso_builder.py` | PySide6 / Qt Quick | Default app |
| `universal_iso_builder_qt.py` | PySide6 / Qt Quick | Qt packaging entrypoint |
| `universal_iso_builder_legacy_tk.py` | Tkinter | Legacy app |
| `universal_iso_builder_v1_4_1.py` | Tkinter | Historical compatibility entrypoint |

The runtime version comes from `iso_builder/constants.py`; the historical filename does
not indicate the current version.

## Requirements

- Git.
- Python 3.14.x (`pyproject.toml` requires `>=3.14,<3.15`).
- PySide6 6.11.1 for the default GUI.
- At least one supported ISO backend.
- Read access to the complete source folder.
- Write access and enough free space in the output location.

Pinned development tools are PyInstaller 6.21.0, pytest 9.0.3, Ruff 0.16.0, and
pre-commit 4.6.0. The legacy GUI also needs working Tk/Tcl support.

## Windows: Fresh Clone with uv (Recommended)

Windows 10 x64 is verified. Windows 11 is **NOT VERIFIED**.

1. Install Git and Python 3.14.
2. Install uv using the official
   [Astral installation guide](https://docs.astral.sh/uv/getting-started/installation/).
3. Open PowerShell and verify:

```powershell
git --version
python --version
uv --version
```

4. Clone the repository:

```powershell
git clone https://github.com/jagdeep646/universal-iso-builder.git
Set-Location -LiteralPath '.\universal-iso-builder'
```

5. Create/synchronize the locked environment:

```powershell
uv sync
```

6. Verify the installed app dependencies:

```powershell
uv run python -c "import PySide6, iso_builder; print('PySide6:', PySide6.__version__); print('App:', iso_builder.__version__)"
```

Expected versions are PySide6 `6.11.1` and app `2.0`.

7. Launch the default Qt app:

```powershell
uv run python -B universal_iso_builder.py
```

## Windows: Fresh Clone with pip

1. Install Git and Python 3.14, then clone the project:

```powershell
git clone https://github.com/jagdeep646/universal-iso-builder.git
Set-Location -LiteralPath '.\universal-iso-builder'
```

2. Create a virtual environment:

```powershell
python -m venv .venv
```

3. Install the default GUI dependency using that environment's interpreter:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-gui.txt
```

4. Verify and launch:

```powershell
& '.\.venv\Scripts\python.exe' -c "import PySide6, iso_builder; print('PySide6:', PySide6.__version__); print('App:', iso_builder.__version__)"
& '.\.venv\Scripts\python.exe' -B universal_iso_builder.py
```

5. Only if you will develop or test the project, install the pinned tools:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install "pyinstaller==6.21.0" "pytest==9.0.3" "ruff==0.16.0" "pre-commit==4.6.0"
```

## macOS: Fresh Clone with uv (Recommended)

The code can select built-in `hdiutil`, but macOS runtime, ISO output, packaging,
signing, and notarization are **NOT VERIFIED**. These are test instructions, not a
supported-platform PASS.

1. Install Git, Python 3.14, and uv. Use the official
   [Astral installation guide](https://docs.astral.sh/uv/getting-started/installation/).
2. Verify the tools and backend:

```bash
git --version
python3 --version
uv --version
command -v hdiutil
```

3. Clone and synchronize:

```bash
git clone https://github.com/jagdeep646/universal-iso-builder.git
cd universal-iso-builder
uv sync
```

4. Verify and launch:

```bash
uv run python -c "import PySide6, iso_builder; print('PySide6:', PySide6.__version__); print('App:', iso_builder.__version__)"
uv run python -B universal_iso_builder.py
```

Opening the window confirms only source GUI launch. It does not verify `hdiutil` output
or macOS packaging.

## macOS: Fresh Clone with pip

1. Clone the project and confirm Python 3.14.x:

```bash
git clone https://github.com/jagdeep646/universal-iso-builder.git
cd universal-iso-builder
python3 --version
```

2. Create the environment and install PySide6:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements-gui.txt
```

3. Verify and launch:

```bash
./.venv/bin/python -c "import PySide6, iso_builder; print('PySide6:', PySide6.__version__); print('App:', iso_builder.__version__)"
./.venv/bin/python -B universal_iso_builder.py
```

4. Optional development tools:

```bash
./.venv/bin/python -m pip install "pyinstaller==6.21.0" "pytest==9.0.3" "ruff==0.16.0" "pre-commit==4.6.0"
```

If installation or launch fails on a Mac, record the exact environment and report
**NOT VERIFIED**. Do not infer macOS support from Windows results.

## ISO Backends

| Platform | Backend | Project status |
|---|---|---|
| Windows | `oscdimg` from Windows ADK | Preferred; real builds verified |
| Windows | PowerShell IMAPI | Built-in fallback; real builds verified |
| macOS | `hdiutil` | Code path exists; runtime NOT VERIFIED |
| Linux/macOS | `xorriso` | External backend; runtime NOT VERIFIED |
| Linux/macOS | `genisoimage` / `mkisofs` | External fallback; runtime NOT VERIFIED |

Windows backend diagnostic:

```powershell
& '.\check_iso_backend.bat'
```

`oscdimg.exe` is not included in the repository or packaged EXE. Install Windows ADK
Deployment Tools from Microsoft when this backend is required. Do not download it from
unofficial sites or redistribute it with this app.

## First Safe Build

1. Launch the default Qt app.
2. Confirm backend detection completes.
3. Select a small test source folder.
4. Select an output folder outside the source.
5. Open **Settings** and review ISO name, volume label, profile, backend, and options.
6. Use **Show Command** and verify the paths and flags.
7. Run **Dry Test** first.
8. Confirm dry run creates neither ISO nor checksum.
9. Start a real build only after reviewing warnings and the plan.
10. Independently compare SHA256 when checksum generation is enabled.

Safety behavior:

- Existing final ISO files are rejected, not silently overwritten.
- Output inside the source folder is rejected.
- Hidden-item exclusion is reliable only with `oscdimg`; unsupported combinations are
  rejected.
- A successful import or dry run is not proof of a real ISO build.
- The app never modifies or executes source content.
- The app does not add antivirus or operating-system security bypasses.

## Legacy Tkinter GUI

With uv:

```powershell
uv run python -B universal_iso_builder_legacy_tk.py
```

With a Windows pip environment:

```powershell
& '.\.venv\Scripts\python.exe' -B universal_iso_builder_legacy_tk.py
```

With a macOS/Linux pip environment:

```bash
./.venv/bin/python -B universal_iso_builder_legacy_tk.py
```

The legacy app needs Tk/Tcl. macOS/Linux Tkinter runtime remains **NOT VERIFIED**.

## Developer Verification

### uv environment

```powershell
uv lock --check
uv run ruff check .
uv run pytest -q tests/test_default_entrypoints.py tests/test_tooling_policy.py
uv run pytest -q
uv run python -B -m iso_builder.gui.qt_app --smoke-test
```

Install/run Git hooks when working on code:

```powershell
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run pre-commit run --all-files
```

### pip environment on Windows

```powershell
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m pytest -q
& '.\.venv\Scripts\python.exe' -B -m iso_builder.gui.qt_app --smoke-test
```

### pip environment on macOS/Linux

```bash
./.venv/bin/python -m ruff check .
./.venv/bin/python -m pytest -q
./.venv/bin/python -B -m iso_builder.gui.qt_app --smoke-test
```

Automated checks do not replace a real backend ISO build or manual GUI verification.
Report only commands actually run.

## Portable Desktop Builds

Portable builds include Python, PySide6, Qt plugins, QML, and SVG assets. The target PC
does not need Python, uv, pip, PySide6, or PyInstaller. ISO backend requirements remain:
Windows can use built-in PowerShell/IMAPI, while `oscdimg` remains an optional Windows
ADK tool and is not redistributed by this project.

### Windows portable folder and ZIP

From a locked development environment:

```powershell
uv sync --locked --all-groups
& '.\build_portable_windows.ps1'
```

On a Windows x64 build machine the exact outputs are:

```text
dist/Universal ISO Builder-Windows-x86_64/
|-- Universal ISO Builder.exe
`-- _internal/
dist/Universal ISO Builder-Windows-x86_64.zip
dist/Universal ISO Builder-Windows-x86_64.zip.sha256.txt
```

The script loads the source GUI offscreen, builds the onedir package, checks its Python
runtime, Qt plugins, QML assets, and Tkinter exclusion, launches the packaged GUI in
smoke-test mode, creates the ZIP, extracts it to a fresh verification directory, launches
the extracted copy, and writes a SHA256 checksum.

For another Windows x64 PC, copy either the complete folder or the ZIP. If using the ZIP,
extract the whole archive and run `Universal ISO Builder.exe` inside the extracted folder.
Never move only the onedir EXE; `_internal` is part of the application. The Windows build
is currently unsigned, so Windows may identify the publisher as unknown. Do not bypass
SmartScreen or antivirus controls.

The older `build_qt_exe.ps1` and `build_qt_onefile_optional.ps1` scripts are retained for
compatibility and diagnostics. The portable onedir ZIP above is the recommended output.
For future private or public distribution, attach the ZIP and checksum to a GitHub
Release instead of committing generated artifacts to the repository.

### macOS target-native app and ZIP

Build macOS artifacts on macOS, never on Windows. Create a locked environment first:

```bash
uv sync --locked --all-groups
chmod +x build_portable_macos.sh
./build_portable_macos.sh arm64
```

For an Intel Mac, use an x86_64 Python environment and run:

```bash
./build_portable_macos.sh x86_64
```

Exact target-specific outputs are:

```text
dist/Universal ISO Builder-macOS-arm64.app
dist/Universal ISO Builder-macOS-arm64.zip
dist/Universal ISO Builder-macOS-arm64.zip.sha256.txt

dist/Universal ISO Builder-macOS-x86_64.app
dist/Universal ISO Builder-macOS-x86_64.zip
dist/Universal ISO Builder-macOS-x86_64.zip.sha256.txt
```

These are separate target-native builds, not a universal2 binary. The script refuses a
requested architecture that does not match the active Python process. Without
`UIB_CODESIGN_IDENTITY`, PyInstaller performs ad-hoc signing only; Gatekeeper distribution
is **NOT VERIFIED** and notarization is not performed.

For a future Developer ID build, set the identity only in the local shell. PyInstaller
enables Hardened Runtime when a real signing identity is supplied. After creating a
keychain notary profile locally, the release flow is:

```bash
UIB_CODESIGN_IDENTITY='Developer ID Application: YOUR NAME (TEAMID)' ./build_portable_macos.sh arm64
xcrun notarytool submit 'dist/Universal ISO Builder-macOS-arm64.zip' --keychain-profile 'UIB_NOTARY' --wait
xcrun stapler staple 'dist/Universal ISO Builder-macOS-arm64.app'
xcrun stapler validate 'dist/Universal ISO Builder-macOS-arm64.app'
```

Use the corresponding x86_64 names for Intel. Never commit certificate credentials,
Apple credentials, or a notary profile. macOS build, launch, `hdiutil`, Developer ID
signing, and notarization remain **NOT VERIFIED** until performed on the relevant Mac.

## Troubleshooting

### `No module named 'PySide6'`

The app is using an interpreter without GUI dependencies. Use `uv sync` with `uv run`,
or install `requirements-gui.txt` using the same virtual-environment Python that launches
the app.

### `Failed to load Python DLL` after moving an EXE

An onedir EXE was moved without `_internal`. Extract and copy the full portable folder
from `dist/Universal ISO Builder-Windows-x86_64.zip`; do not move the EXE alone.

### `oscdimg` is not detected

Install Microsoft Windows ADK Deployment Tools or use detected PowerShell IMAPI. The
project does not redistribute `oscdimg.exe`.

### Existing ISO or output-inside-source error

Choose a new ISO name and an output directory outside the source. Existing final files
are intentionally protected.

### macOS launch or `hdiutil` issue

Record macOS version, architecture, Python/PySide6 versions, backend path, exact command,
and exact error. Keep the result **NOT VERIFIED** until the manual workflow succeeds.

## Verified Status

| Area | Status |
|---|---|
| Default Qt and legacy Tkinter source GUIs on Windows 10 | VERIFIED |
| Windows `oscdimg` and IMAPI real ISO + SHA256 | VERIFIED |
| Qt onedir EXE launch | VERIFIED |
| Qt onefile relocated launch and real ISO + SHA256 | VERIFIED |
| Portable Windows x86_64 folder/ZIP build, extracted smoke launch, and visible-window launch | VERIFIED on Windows 10 build host |
| Windows 11 | NOT VERIFIED / deferred |
| macOS `.app`, ZIP, source runtime, and `hdiutil` output | NOT VERIFIED / target-native build required |
| Linux runtime and backend output | NOT VERIFIED |
| Public code signing | NOT APPLICABLE to current personal build |
| Public GitHub release | NOT CREATED |

Creating an ISO packages files; it does not prove that source content is safe. Do not
place credentials in the repository, logs, or test folders.

For architecture, complete platform cases, cleanup steps, expected logs, and the manual
report template, read [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md).
