# Universal ISO Builder

Universal ISO Builder is a Python/Tkinter desktop application that creates
non-bootable data ISO images from folders. It scans the source, selects an
available platform backend, shows the exact command, creates the ISO through a
transactional temporary output, and can generate a SHA256 checksum.

Current application version: **2.0**

Current distribution scope: **personal/internal use**

## Project status

| Area | Status | Evidence |
|---|---|---|
| Windows 10 x64 source GUI | VERIFIED | Windows 10 Home 21H1, build 19043.1889 |
| Windows onedir EXE | VERIFIED | PyInstaller 6.21.0; complete folder launch tested |
| Windows onefile EXE | VERIFIED | Copied to another folder and launched without `_internal` |
| Windows oscdimg real ISO + SHA256 | VERIFIED | Real builds and checksum comparisons completed |
| Windows PowerShell IMAPI real ISO + SHA256 | VERIFIED | Real v2.0 service pipeline build completed |
| Windows 11 | NOT VERIFIED / deferred | Requires a Windows 11 test machine |
| macOS `hdiutil` | NOT VERIFIED / deferred | Follow `docs/TESTING_GUIDE.md` |
| Linux backends | NOT VERIFIED | Requires a Linux test machine |
| Public code signing | NOT APPLICABLE to current personal build | Current EXE is intentionally unsigned |
| Public GitHub Release | NOT CREATED | `v2.0` is an internal Git tag only |

The annotated `v2.0` tag points to commit `ccb6f56`. Documentation added after
that tag belongs to subsequent project history; do not move or rewrite the
published tag.

## What the application does

- Detects supported ISO backends.
- Scans folders in a background worker so the Tkinter window stays responsive.
- Reports file count, folder count, size, long paths, Unicode names, hidden
  items, symlinks, unreadable entries, empty directories, and files over 4 GB.
- Generates safe ISO names and volume labels.
- Supports automatic package-folder naming.
- Shows the exact backend command before execution.
- Supports dry runs that do not create an ISO.
- Checks available output space before a real build.
- Refuses output paths located inside the source folder.
- Refuses to overwrite an existing ISO.
- Builds through a hidden sibling partial ISO and publishes the final ISO only
  after backend success.
- Cleans known partial outputs and temporary IMAPI PowerShell scripts.
- Can generate an adjacent `.iso.sha256.txt` file.
- Cancels an active child process when the application is closed during a build.

## What the application does not do

- It does not create bootable installation media.
- It does not modify source files.
- It does not execute installers or setup programs found in the source.
- It does not hide, encrypt, or pack source executables.
- It does not bypass antivirus, SmartScreen, Gatekeeper, or execution policy.
- It does not bundle or redistribute Microsoft `oscdimg.exe`.
- It does not guarantee that every backend represents hidden files, symlinks,
  permissions, or filesystem metadata in the same way.

## Runtime requirements

The application runtime uses the Python standard library only.

Required:

- Python with Tkinter/Tcl support.
- At least one detected ISO backend.
- Enough free space for the estimated ISO plus overhead.
- Read access to the complete source tree.
- Write access to the selected output directory.

Python/Tk baseline actually verified on Windows:

- Python 3.14.5
- Tk/Tcl 8.6.15

The exact minimum Python version has not been formally established. For new
environments, use a currently supported Python 3 release with working Tkinter,
then run the complete test suite before treating that interpreter as supported.

### Backend availability

| Platform | Backend | Source | Current project status |
|---|---|---|---|
| Windows | `oscdimg` | Windows ADK Deployment Tools | Preferred; real build verified |
| Windows | `powershell_imapi` | Windows PowerShell + IMAPI COM | Fallback; real build verified |
| macOS | `hdiutil` | Built into macOS | Code path exists; runtime NOT VERIFIED |
| Linux/macOS | `xorriso` | External installation | Code path exists; runtime NOT VERIFIED |
| Linux/macOS | `genisoimage` | External installation | Code path exists; runtime NOT VERIFIED |
| Linux/macOS | `mkisofs` | External installation | Code path exists; runtime NOT VERIFIED |

`oscdimg.exe` is detected from `PATH` or known Windows ADK locations. It is not
included in PyInstaller output. Keep that behavior: the installed ADK license
does not establish `oscdimg.exe` as a redistributable project binary.

## Quick start from source

### Windows PowerShell

```powershell
git clone https://github.com/jagdeep646/universal-iso-builder.git
```

```powershell
Set-Location -LiteralPath '.\universal-iso-builder'
```

```powershell
python -m venv .venv
```

```powershell
& '.\.venv\Scripts\Activate.ps1'
```

```powershell
& '.\.venv\Scripts\python.exe' -m tkinter
```

```powershell
& '.\.venv\Scripts\python.exe' '.\universal_iso_builder_v1_4_1.py'
```

The filename `universal_iso_builder_v1_4_1.py` is intentionally retained as a
thin compatibility launcher. The runtime version is defined by
`iso_builder.constants.APP_VERSION` and is currently `2.0`.

### macOS or Linux shell

```bash
git clone https://github.com/jagdeep646/universal-iso-builder.git
cd universal-iso-builder
python3 -m venv .venv
source .venv/bin/activate
python -m tkinter
python universal_iso_builder_v1_4_1.py
```

If the repository is private, authenticate through PyCharm or the operating
system Git credential manager. Do not save a personal access token inside the
repository, shell-history examples, or project configuration files.

Do not treat a successful import as a GUI test. `python -m tkinter` must open a
small Tk test window, and the application itself must open normally.

For detailed macOS/PyCharm instructions and the required runtime checklist, see
[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md).

## Normal GUI workflow

1. Launch the application.
2. Confirm that backend detection completes.
3. Select a source folder.
4. Select an output folder outside the source.
5. Select a compatibility profile.
6. Leave backend on `Auto`, or explicitly select the backend under test.
7. Choose whether hidden files, SHA256, duplicate optimization, automatic
   packaging, and dry run are enabled.
8. Click **Scan Folder** and review all warnings.
9. Click **Show Command** and confirm source, output, label, profile, backend,
   and flags.
10. Use a dry run first.
11. Disable dry run and click **Build ISO** only after the plan is correct.
12. Verify the final ISO and checksum independently.

## Compatibility profiles

| Profile | Intended behavior |
|---|---|
| Auto - Best Compatible | Prefer the first available UDF-capable backend |
| Modern Windows - UDF + ISO | Modern hybrid/UDF-oriented backend command |
| Old PC - ISO9660 + Joliet | Legacy/Joliet-oriented backend command |
| UDF Only - Modern | Require a backend marked UDF-capable |

Profile names describe intent, but exact filesystem output is backend-specific:

- `oscdimg` uses `-u2 -udfver102` for UDF Only.
- PowerShell IMAPI creates ISO9660 + Joliet + UDF and logs that pure UDF-only
  control is unavailable.
- The current `hdiutil` builder always requests ISO + Joliet and adds UDF for
  non-legacy profiles. Therefore its UDF Only result is expected to be hybrid,
  not proven pure-UDF. This is NOT VERIFIED until macOS testing is completed.
- `genisoimage` and `mkisofs` are treated as ISO/Joliet fallbacks and are not
  selected for UDF Only.

## Hidden files

Reliable hidden-item exclusion is currently implemented only for `oscdimg`.

- `Include hidden files = ON`: allowed for every backend.
- `Include hidden files = OFF`: non-oscdimg backends are rejected because the
  application cannot guarantee exclusion semantics.

On macOS, keep hidden files enabled for normal hdiutil testing. Explicitly test
the expected rejection with hidden files disabled.

## Output safety model

The application validates and prepares a complete immutable build request before
starting backend work.

For a real build:

1. Scan and validate source/output paths.
2. Estimate ISO space requirement.
3. Create a hidden sibling path such as
   `.NAME.<token>.partial.iso`.
4. Retarget exactly one backend output argument to that temporary path.
5. Run the backend.
6. Reject missing, empty, ambiguous, or failed output.
7. Publish the completed ISO without overwriting an existing final ISO.
8. Generate SHA256 if enabled.
9. Clean known temporary-output candidates.

On Windows, filesystem type detection can proactively reject FAT/FAT32 output
for an estimated ISO larger than 4 GB. On non-Windows systems, free-space
checking still runs, but filesystem-type detection currently returns
`NOT VERIFIED`; platform-specific filesystem limits must be tested manually.

## Windows EXE builds

Build dependency:

- PyInstaller 6.21.0, pinned by all provided Windows build scripts.

### Recommended onedir build

```powershell
& '.\build_exe.ps1'
```

or:

```powershell
& '.\build_exe.bat'
```

Output:

```text
dist/
└── Universal ISO Builder/
    ├── Universal ISO Builder.exe
    └── _internal/
```

The complete folder must be copied. Moving only the onedir EXE causes a missing
`_internal\python*.dll` error.

### Optional single-file build

```powershell
& '.\build_onefile_optional.bat'
```

Output:

```text
dist-onefile/
└── Universal ISO Builder.exe
```

The onefile build can be moved by itself. PyInstaller extracts its bundled
runtime to a temporary `_MEI...` directory when launched. This causes a larger
file, slower startup, and potentially more security-product heuristic warnings.
Do not add bypass behavior.

The verified v2.0 onefile size was approximately 12.08 MB. Rebuilds can change
the exact size and SHA256, so always calculate a fresh checksum.

### Build-script guarantees

- Paths are anchored to the script directory.
- PyInstaller is pinned.
- Tkinter/Tcl is checked before building.
- Cleanup is scoped to the application-specific build/output directories.
- Native command failures return failure.
- `BUILD PASS` requires the expected EXE to exist.
- Onedir and onefile outputs are isolated.
- Windows version metadata is loaded from `windows_version_info.txt`.

## Automated tests

Run from the repository root:

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v
```

macOS/Linux:

```bash
source .venv/bin/activate
python -B -m unittest discover -s tests -v
```

Windows-only build-script and IMAPI tests may be skipped on non-Windows
platforms. A test run is successful only when the final summary is `OK`; record
the number of executed and skipped tests.

The v2.0 Windows baseline completed 101 tests successfully before this
documentation update.

Tests cover:

- Backend detection/selection and command snapshots.
- UDF compatibility enforcement.
- Hidden-file option semantics.
- Naming and Windows reserved filenames.
- Source scanning and warnings.
- Storage preflight.
- Background GUI operations and event ordering.
- SHA256 and execution results.
- IMAPI script lifecycle.
- Transactional output publication.
- Cancellation and close behavior.
- Windows output decoding.
- PyInstaller build-script safety.
- Version metadata and repository line-ending policy.

Automated unit tests do not replace a real backend ISO build on each supported
operating system.

## Project architecture

```text
universal_iso_builder_v1_4_1.py   compatibility entrypoint
iso_builder/
├── constants.py                  version, profiles, known backend paths
├── models.py                     build and UI data contracts
├── naming.py                     names, labels, path validation
├── scanning.py                   source-tree scan and warnings
├── preflight.py                  space/filesystem validation
├── planner.py                    BuildRequest -> BuildPlan
├── execution.py                  process, transaction, SHA256, result
├── transaction.py                partial output and safe publish
├── cancellation.py               child-process cancellation
├── utils.py                      formatting and command display
├── backends/
│   ├── detection.py              backend discovery and selection
│   ├── commands.py               backend-specific command builders
│   └── imapi.py                  temporary Windows IMAPI script
└── gui/
    └── app.py                    Tkinter view/controller and UI event queue
tests/                             automated regression suite
docs/TESTING_GUIDE.md             manual platform test procedures
```

Dependency direction should remain:

```text
GUI -> planner/execution -> backends/scanning/naming -> models/constants/utils
```

Lower layers must not import or access Tkinter widgets.

## Security and trust notes

- The current personal Windows EXE is unsigned.
- Windows can display `Unknown Publisher` or SmartScreen warnings.
- Do not claim that an unsigned build is signed or trusted.
- Do not use a self-signed certificate to imply public publisher trust.
- Do not download missing Python DLLs from third-party websites.
- Do not redistribute `oscdimg.exe`; ask the user to install the Windows ADK.
- Do not publish checksums copied from an older build.
- Review source-folder warnings before building unknown content.
- Creating an ISO packages files; it does not make those files safe.

## Known limitations and deferred work

- Windows 11 runtime is deferred and NOT VERIFIED.
- macOS runtime, hdiutil output, macOS PyInstaller packaging, signing, and
  notarization are deferred and NOT VERIFIED.
- Linux runtime and backend output are NOT VERIFIED.
- Symlink behavior differs by backend.
- Hidden exclusion is oscdimg-only.
- Pure UDF-only behavior is not available on every UDF-capable backend.
- Non-Windows output filesystem type is not currently detected.
- Long-path support depends on the OS, filesystem, Python build, and backend.
- Onefile startup and temporary extraction are PyInstaller behavior.
- The repository currently has no project `LICENSE` file; public distribution
  terms are therefore not defined.

## Git and release workflow

Before committing:

```powershell
git status --short --branch
git diff --check
```

Run focused tests for the changed subsystem, then the full test suite.

Build artifacts are ignored:

- `.venv/`
- `build/`
- `dist/`
- `dist-onefile/`
- `*.spec`
- `*.iso`
- checksum outputs

Repository line endings are controlled by `.gitattributes`:

- Python/text: LF
- Windows BAT/CMD/PowerShell: CRLF
- EXE/DLL/images/ISO: binary

Public GitHub Release creation is currently cancelled. Keep local artifacts and
their matching checksum together for personal use.
