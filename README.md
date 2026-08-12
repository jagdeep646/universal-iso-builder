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

## Windows EXE Builds

Recommended Qt onedir build:

```powershell
& '.\build_qt_exe.ps1'
```

Output:

```text
dist-qt/Universal ISO Builder/
├── Universal ISO Builder.exe
└── _internal/
```

Copy the complete folder. Moving only the onedir EXE causes a missing Python DLL error.

Optional standalone onefile build:

```powershell
& '.\build_qt_onefile_optional.ps1'
```

Output:

```text
dist-qt-onefile/Universal ISO Builder.exe
```

Onefile can be moved alone, but it is larger and starts more slowly because it extracts
Qt/Python files to a temporary directory. The current personal build is intentionally
unsigned. Do not add antivirus or SmartScreen bypass behavior.

macOS packaging, signing, and notarization are **NOT VERIFIED**. Follow the experimental
steps in `docs/TESTING_GUIDE.md`; do not present them as a release build.

## Troubleshooting

### `No module named 'PySide6'`

The app is using an interpreter without GUI dependencies. Use `uv sync` with `uv run`,
or install `requirements-gui.txt` using the same virtual-environment Python that launches
the app.

### `Failed to load Python DLL` after moving an EXE

An onedir EXE was moved without `_internal`. Copy the full folder from
`dist-qt/Universal ISO Builder/`, or use the optional onefile build.

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
| Windows 11 | NOT VERIFIED / deferred |
| macOS source runtime and `hdiutil` output | NOT VERIFIED / deferred |
| Linux runtime and backend output | NOT VERIFIED |
| Public code signing | NOT APPLICABLE to current personal build |
| Public GitHub release | NOT CREATED |

Creating an ISO packages files; it does not prove that source content is safe. Do not
place credentials in the repository, logs, or test folders.

For architecture, complete platform cases, cleanup steps, expected logs, and the manual
report template, read [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md).
