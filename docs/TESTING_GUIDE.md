# Universal ISO Builder Testing Guide

This guide is the manual verification record for Universal ISO Builder. It is
designed for future Windows, macOS, and Linux testing without turning
unverified assumptions into PASS results.

## Result vocabulary

Use only these result labels:

- **PASS**: the exact test was run and the expected result was observed.
- **FAIL**: the exact test was run and an incorrect result was observed.
- **WARN**: the test completed but exposed a supported limitation or release
  risk.
- **NOT VERIFIED**: the test was not run, evidence was incomplete, or the
  environment was unavailable.
- **DEFERRED**: testing was intentionally postponed.

Record actual commands, application logs, OS version, CPU architecture, Python
version, Tk version, backend path/version, output size, and checksum.

## Current verified baseline

| Test area | Result |
|---|---|
| Windows 10 Home 21H1 build 19043.1889 | PASS |
| Python 3.14.5 + Tk 8.6.15 | PASS |
| Source GUI launch | PASS |
| Responsive large-folder scanning | PASS |
| oscdimg real ISO + SHA256 | PASS |
| PowerShell IMAPI real ISO + SHA256 | PASS |
| Onedir EXE build/launch | PASS |
| Onefile EXE moved to another folder and launched | PASS |
| Windows 11 | DEFERRED |
| macOS | DEFERRED |
| Linux | NOT VERIFIED |

The current scope is personal/internal use. The Windows EXE is intentionally
unsigned.

## General clean-clone procedure

Test from a clean clone whenever practical. Do not copy `.venv`, `build`,
`dist`, `dist-onefile`, `.idea`, or cached Python files from another machine.

```bash
git clone https://github.com/jagdeep646/universal-iso-builder.git
cd universal-iso-builder
git status --short --branch
```

Expected: a clean branch with no modified or untracked project files.

Record the tested commit:

```bash
git rev-parse HEAD
git log -1 --oneline
```

## macOS test plan using PyCharm

macOS is currently NOT VERIFIED. Complete every required item below before
changing its project status.

### 1. Record Mac environment

Open Terminal:

```bash
sw_vers
uname -m
```

Record:

- macOS product version and build.
- `arm64` for Apple Silicon or `x86_64` for Intel.
- Mac model if relevant.

Do not claim that one architecture is supported based only on testing the other.

### 2. Clone in PyCharm

Option A — PyCharm UI:

1. Open PyCharm.
2. Choose **Get from VCS**.
3. Repository URL:
   `https://github.com/jagdeep646/universal-iso-builder.git`
4. Choose a local directory.
5. Click **Clone**.
6. Open the cloned project.

Option B — Terminal:

```bash
git clone https://github.com/jagdeep646/universal-iso-builder.git
cd universal-iso-builder
```

Then select **File > Open** in PyCharm and open the repository folder.

If GitHub requests authentication for a private repository, use PyCharm's GitHub
account integration or the operating system Git credential manager. Never store
a personal access token in this repository.

### 3. Create the Mac virtual environment

From the PyCharm terminal:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python --version
```

In PyCharm:

1. Open **Settings/Preferences > Project > Python Interpreter**.
2. Choose **Add Interpreter > Existing Environment**.
3. Select `.venv/bin/python`.
4. Apply the setting.

The application has no third-party runtime package requirement. Do not install
PyInstaller until source runtime tests pass.

### 4. Verify Tkinter

```bash
python -c "import tkinter; root=tkinter.Tcl(); print(root.call('info','patchlevel'))"
```

Then:

```bash
python -m tkinter
```

Expected:

- The first command prints a Tcl/Tk version.
- The second command opens a Tk test window.

If import works but no window opens, Tk GUI support is NOT VERIFIED. Use a
Python distribution with functional Tk support; do not modify application code
to work around a broken Python installation.

### 5. Verify built-in hdiutil

```bash
command -v hdiutil
hdiutil help
```

Expected:

- `command -v` returns a real hdiutil path, normally under `/usr/bin`.
- Help text is displayed.

Do not install or copy a replacement hdiutil into the repository.

### 6. Run automated tests

```bash
python -B -m unittest discover -s tests -v
```

Expected:

- Final result: `OK`.
- Windows-specific tests can be reported as skipped on macOS.
- No unhandled Tkinter/thread exception.

Record the executed and skipped test counts. Do not expect the Windows baseline
count to be identical.

### 7. Launch from source

```bash
python universal_iso_builder_v1_4_1.py
```

Expected:

- Window title: `Universal ISO Builder v2.0`.
- Backend scan completes.
- `hdiutil` appears in the backend list.
- Window can be moved, resized, and closed.
- Terminal has no unhandled exception after a normal window close.

If hdiutil does not appear, save the full backend log and mark backend detection
FAIL.

### 8. Create a controlled Mac source folder

```bash
mkdir -p "$HOME/UniversalISOTestSource/Sub Folder"
printf 'plain test file\n' > "$HOME/UniversalISOTestSource/plain.txt"
printf 'unicode test\n' > "$HOME/UniversalISOTestSource/Sub Folder/café.txt"
printf 'hidden test\n' > "$HOME/UniversalISOTestSource/.hidden.txt"
```

Check:

```bash
find "$HOME/UniversalISOTestSource" -maxdepth 3 -print
```

This fixture verifies spaces, Unicode, a subfolder, and a dot-hidden file
without using private documents.

### 9. Background scan responsiveness

In the GUI:

1. Select `$HOME/UniversalISOTestSource`.
2. Keep **Include hidden files** ON.
3. Click **Scan Folder**.
4. Move and resize the window while scanning.
5. Confirm the scan summary reports the expected files, Unicode path, and
   hidden item.
6. Start a second scan after completion.

For a meaningful long scan, use a large non-sensitive folder that the test user
can read. Do not test against system-protected or private folders.

Expected:

- Window remains responsive.
- A concurrent command/build request is rejected as busy.
- Operation state clears after completion.
- Second scan starts normally.

### 10. Show Command and dry run

GUI settings:

- Source: `$HOME/UniversalISOTestSource`
- Output: a writable test directory, for example `$HOME/Desktop`
- ISO name: `MAC_DRY_VERIFY.iso`
- Label: `MAC_DRY_VERIFY`
- Profile: `Auto - Best Compatible`
- Backend: explicit `hdiutil`
- Include hidden files: ON
- Generate SHA256: ON
- Auto package: OFF
- Dry run: ON

Click **Show Command**.

The command must use the detected hdiutil executable and contain:

```text
makehybrid
-iso
-joliet
-default-volume-name
MAC_DRY_VERIFY
-udf
-o
```

Click **Build ISO**.

Expected application result:

```text
Build finished: DRY RUN
```

Verify no ISO was created:

```bash
test ! -e "$HOME/Desktop/MAC_DRY_VERIFY.iso" && echo "DRY RUN CLEAN" || echo "UNEXPECTED OUTPUT"
```

Expected: `DRY RUN CLEAN`.

### 11. Real hdiutil ISO and SHA256

Change:

- ISO name: `MAC_REAL_VERIFY.iso`
- Label: `MAC_REAL_VERIFY`
- Dry run: OFF

Keep hdiutil explicit and hidden files ON. Build the ISO.

Expected:

- Backend exit code is successful.
- Transactional command targets a hidden `.partial.iso`.
- Final ISO exists and is non-empty.
- `.iso.sha256.txt` exists.
- No `.partial.iso` remains.
- Build finishes with `PASS`.

Verify files:

```bash
ls -lh "$HOME/Desktop/MAC_REAL_VERIFY.iso" "$HOME/Desktop/MAC_REAL_VERIFY.iso.sha256.txt"
```

Verify checksum:

```bash
actual="$(shasum -a 256 "$HOME/Desktop/MAC_REAL_VERIFY.iso" | awk '{print $1}')"; saved="$(awk '{print $1}' "$HOME/Desktop/MAC_REAL_VERIFY.iso.sha256.txt")"; printf 'Actual=%s\nSaved=%s\nMatch=%s\n' "$actual" "$saved" "$([ "$actual" = "$saved" ] && printf True || printf False)"
```

Expected: `Match=True`.

Check partial cleanup:

```bash
find "$HOME/Desktop" -maxdepth 1 -name '.MAC_REAL_VERIFY.*.partial*' -print
```

Expected: no output.

### 12. Mount and inspect the Mac ISO

```bash
hdiutil attach "$HOME/Desktop/MAC_REAL_VERIFY.iso"
```

Record the device and mount point returned by hdiutil.

Inspect the mounted volume:

```bash
find "/Volumes/MAC_REAL_VERIFY" -maxdepth 3 -print
```

Verify:

- `plain.txt` exists.
- `Sub Folder/café.txt` exists with a readable name.
- `.hidden.txt` exists because hidden files were enabled.

Detach using the actual device or mounted volume reported by `hdiutil attach`:

```bash
hdiutil detach "/Volumes/MAC_REAL_VERIFY"
```

Do not guess PASS if the mount name differs. Use the actual returned mount point.

### 13. Hidden exclusion guard

Set **Include hidden files** OFF while hdiutil is explicitly selected and click
**Show Command**.

Expected application error:

```text
Selected backend 'hdiutil' cannot reliably exclude hidden items.
Turn Include hidden files ON or select oscdimg.
```

No ISO or temporary output should be created.

### 14. Existing-output protection

Keep the successful `MAC_REAL_VERIFY.iso` in place and attempt the same build
again.

Expected:

- Planning/build is rejected because output already exists.
- Existing ISO size and SHA256 remain unchanged.
- No replacement or truncation occurs.

### 15. Output-inside-source protection

Select an output folder inside `$HOME/UniversalISOTestSource`.

Expected:

- The application rejects output located inside the source.
- No build process starts.

### 16. Close/cancel behavior

Use a sufficiently large, non-sensitive source so hdiutil remains active long
enough to cancel.

1. Start a real build.
2. Close the application while the backend is active.
3. Confirm cancellation in the dialog.
4. Wait for the GUI to close.

Expected:

- Child backend process is stopped.
- No final ISO is published for an incomplete build.
- No `.partial.iso` remains.
- A pre-existing final ISO, if any, is preserved.

If the build completes before cancellation, this test is NOT VERIFIED; use a
larger controlled source and repeat.

### 17. UDF Only limitation on macOS

Select `UDF Only - Modern`, explicit hdiutil, and click **Show Command**.

Current inspected code is expected to request:

```text
-iso -joliet ... -udf
```

That is a hybrid request, not proof of pure UDF-only output. Record the command
and mounted filesystem behavior as a known limitation. Do not mark pure UDF-only
PASS unless an independent ISO inspection proves it.

### 18. Optional macOS PyInstaller experiment

Do this only after all source tests pass. A Mac application must be built on
macOS; the Windows EXE cannot be converted into a Mac application.

Install the same currently pinned PyInstaller version:

```bash
python -m pip install --disable-pip-version-check "pyinstaller==6.21.0"
```

Onedir/windowed experiment:

```bash
python -m PyInstaller --noconfirm --clean --windowed --onedir --name "Universal ISO Builder" universal_iso_builder_v1_4_1.py
```

Inspect:

```bash
find dist -maxdepth 3 -print
```

Launch the generated `.app` through Finder/PyCharm or:

```bash
open "dist/Universal ISO Builder.app"
```

The exact output bundle and launch behavior are currently NOT VERIFIED.

Optional onefile experiment:

```bash
python -m PyInstaller --noconfirm --clean --windowed --onefile --name "Universal ISO Builder" universal_iso_builder_v1_4_1.py
```

Important:

- Apple Silicon and Intel artifacts are architecture-dependent.
- Unsigned apps can be blocked or warned about by Gatekeeper.
- Do not disable Gatekeeper or remove quarantine attributes as a test shortcut.
- macOS signing and notarization require an appropriate Apple Developer setup
  and are outside the current personal Windows release scope.

### 19. Mac cleanup

Only remove the exact controlled test paths you created:

```bash
test_root="$HOME/UniversalISOTestSource"; case "$test_root" in "$HOME/UniversalISOTestSource") rm -rf -- "$test_root" ;; *) printf 'Refusing unexpected path: %s\n' "$test_root" ;; esac
rm -f "$HOME/Desktop/MAC_DRY_VERIFY.iso" "$HOME/Desktop/MAC_DRY_VERIFY.iso.sha256.txt"
rm -f "$HOME/Desktop/MAC_REAL_VERIFY.iso" "$HOME/Desktop/MAC_REAL_VERIFY.iso.sha256.txt"
```

Before running cleanup, print each path and confirm it is the intended test
fixture. Never use wildcard recursive deletion against an unverified path.

## Windows regression checklist

Use PowerShell one-line commands.

### Environment

```powershell
git status --short --branch
```

```powershell
& '.\.venv\Scripts\python.exe' --version
```

```powershell
& '.\.venv\Scripts\python.exe' -c "import tkinter; root=tkinter.Tcl(); print(root.call('info','patchlevel'))"
```

### Automated suite

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v
```

### Source GUI

```powershell
& '.\.venv\Scripts\python.exe' '.\universal_iso_builder_v1_4_1.py'
```

### Backend check

```powershell
& '.\check_iso_backend.bat'
```

### Recommended onedir

```powershell
& '.\build_exe.ps1'
```

Copy and test the complete `dist\Universal ISO Builder` folder.

### Onefile

```powershell
& '.\build_onefile_optional.bat'
```

Move only `dist-onefile\Universal ISO Builder.exe` to another folder and launch
it. Confirm it does not require adjacent `_internal`.

### Independent Windows SHA256

```powershell
$actual=(Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\path\output.iso').Hash; $saved=((Get-Content -LiteralPath 'C:\path\output.iso.sha256.txt' -Raw).Split()[0]); [pscustomobject]@{Actual=$actual;Saved=$saved;Match=($actual -eq $saved)}
```

### Authenticode status

```powershell
Get-AuthenticodeSignature -LiteralPath '.\dist-onefile\Universal ISO Builder.exe' | Select-Object Status,StatusMessage
```

Current personal v2.0 expectation: `NotSigned`.

## Linux test outline

Linux is currently NOT VERIFIED.

1. Record distribution, version, desktop session, and CPU architecture.
2. Clone cleanly and create `.venv`.
3. Confirm Tkinter opens a test window.
4. Install at least one supported backend using the distribution's trusted
   package manager: xorriso, genisoimage, or mkisofs.
5. Run the full automated suite and record skips.
6. Launch the GUI.
7. Verify explicit backend detection.
8. Repeat dry-run, real ISO, SHA256, mount/contents, overwrite, hidden guard,
   Unicode, spaces, cancellation, and partial-cleanup tests.
9. Do not claim UDF support for genisoimage/mkisofs; inspect the actual command
   warning.

No Linux package/build script is currently provided.

## Manual test report template

Copy this section into a dated report:

```text
Universal ISO Builder test report

Date:
Tester:
Commit:
Tag:
Platform:
OS version/build:
CPU architecture:
Python:
Tk/Tcl:
Backend:
Backend path/version:

Automated tests:
- Executed:
- Skipped:
- Result:

Manual tests:
- GUI launch:
- Backend detection:
- Scan responsiveness:
- Show Command:
- Dry run/no output:
- Real ISO:
- Independent SHA256:
- Mounted contents:
- Spaces:
- Unicode:
- Hidden items:
- Existing output:
- Output-inside-source:
- Close/cancel:
- Partial cleanup:
- Packaging:

Security/release:
- Signature status:
- Artifact size:
- Artifact SHA256:

Known warnings:
NOT VERIFIED:
Final verdict:
```

Attach actual command output. Do not replace missing evidence with assumptions.
