# AGENTS.md

## 1. Purpose

This file defines repository-wide rules for AI coding agents working on Universal ISO
Builder. Explicit user instructions, repository evidence, and preserved behavior take
priority over assumptions. Do not present an unverified claim as fact; write
`NOT VERIFIED` when evidence or an executed check is missing.

## 2. Project Summary

Universal ISO Builder is a Python desktop application that scans a source folder, plans
a backend command, creates a non-bootable data ISO through transactional output, and can
generate a SHA256 checksum.

- Version `2.0` is defined in `iso_builder/constants.py`.
- `universal_iso_builder.py` is the default PySide6/Qt Quick launcher.
- `universal_iso_builder_legacy_tk.py` and `universal_iso_builder_v1_4_1.py` launch the
  legacy Tkinter GUI.
- Both GUIs use shared planning, scanning, backend, execution, cancellation, and
  transaction services under `iso_builder/`.
- Documented distribution scope is personal/internal use.
- Windows 10 and Windows backend builds are documented as verified. Windows 11, macOS,
  and Linux runtime remain `NOT VERIFIED`.

`README.md` contains historical Tkinter-first and standard-library-only wording. Where
it conflicts with current launchers, `pyproject.toml`, or tests, follow executable source
and tests and report the documentation mismatch.

## 3. Sources of Truth

Read relevant sources before editing. Precedence is:

1. Explicit user instructions for the current task.
2. The most specific applicable `AGENTS.md`.
3. Current tests and executable source behavior.
4. `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, and build scripts.
5. `README.md` and `docs/TESTING_GUIDE.md` for workflows and platform status.
6. Code comments and historical commit messages.

Important first reads are `README.md`, `docs/TESTING_GUIDE.md`, `pyproject.toml`, the
relevant tests, `iso_builder/models.py`, `iso_builder/planner.py`,
`iso_builder/execution.py`, and the applicable GUI bridge/controller.

## 4. Repository Map

Runtime entrypoints:

- `universal_iso_builder.py`: production/default Qt launcher.
- `universal_iso_builder_qt.py`: explicit Qt packaging launcher.
- `universal_iso_builder_legacy_tk.py`: explicit legacy Tkinter launcher.
- `universal_iso_builder_v1_4_1.py`: retained Tkinter compatibility launcher; its
  historical filename is not the runtime version source.

Core source:

- `iso_builder/constants.py` and `models.py`: configuration and data contracts.
- `naming.py`, `scanning.py`, and `preflight.py`: input preparation and validation.
- `planner.py`: immutable request-to-plan preparation.
- `execution.py`, `transaction.py`, and `cancellation.py`: backend lifecycle and safety.
- `iso_builder/backends/`: detection, selection, commands, and IMAPI scripts.
- `iso_builder/gui/qt_app.py`, `qt_bridge.py`, and `qml/`: default GUI.
- `iso_builder/gui/app.py`: legacy Tkinter view/controller.

Tests, docs, and configuration:

- `tests/`: unittest-style regression tests collected by pytest.
- `README.md` and `docs/TESTING_GUIDE.md`: overview and manual platform procedures.
- `pyproject.toml` and `uv.lock`: pinned uv environment.
- `.pre-commit-config.yaml`: file checks, Ruff, Gitleaks, lock check, and pre-push tests.
- `build_qt_exe.ps1` and `build_qt_onefile_optional.ps1`: Qt Windows packaging.
- `build_exe.ps1`, `build_exe.bat`, and `build_onefile_optional.bat`: legacy builds.
- `windows_version_info.txt`: Windows executable metadata.
- `check_iso_backend.bat`: Windows backend diagnostic.

Generated/local-only paths include `.venv/`, `build/`, `dist/`, `dist-onefile/`,
`dist-qt/`, `dist-qt-onefile/`, Python/tool caches, ISO files, checksums, specs, logs, and
temporary files. They are ignored and must not be edited or committed as source.

No `.github` CI configuration was found at the last inspection. Other hosted CI is
`NOT VERIFIED`.

## 5. Environment and Setup

`pyproject.toml` requires Python `>=3.14,<3.15`, pins PySide6 `6.11.1`, and pins the
development tools. Run commands from the repository root.

### Windows PowerShell

```powershell
uv sync
```

```powershell
& '.\.venv\Scripts\Activate.ps1'
```

Use PowerShell-compatible one-line Python commands:

```powershell
& '.\.venv\Scripts\python.exe' -c "import iso_builder; print(iso_builder.__version__)"
```

Never use Bash heredoc syntax such as `python - <<PY` in PowerShell instructions.

### macOS / Linux

Runtime and backend output are `NOT VERIFIED`. Follow `docs/TESTING_GUIDE.md`, record
the actual environment, and do not convert imports or unit tests into a platform-runtime
PASS. No Linux packaging script exists. macOS packaging, signing, and notarization are
`NOT VERIFIED`.

## 6. Run and Build Commands

Default Qt application:

```powershell
uv run python -B universal_iso_builder.py
```

Automated QML smoke load:

```powershell
uv run python -B -m iso_builder.gui.qt_app --smoke-test
```

Legacy Tkinter application:

```powershell
uv run python -B universal_iso_builder_legacy_tk.py
```

`python -m iso_builder` and `universal_iso_builder_v1_4_1.py` also launch legacy
Tkinter. Do not silently redirect compatibility paths.

Authorized Qt packaging on Windows:

```powershell
& '.\build_qt_exe.ps1'
& '.\build_qt_onefile_optional.ps1'
```

These scripts can install pinned PyInstaller and regenerate `dist-qt/` or
`dist-qt-onefile/`. Run them only when packaging and environment/network changes are
explicitly authorized. Keep legacy builds and output directories separate.

## 7. Verification Commands

Use the smallest relevant checks first:

```powershell
uv lock --check
uv run ruff check .
uv run pytest -q tests/test_default_entrypoints.py tests/test_tooling_policy.py
git diff --check
```

Select focused files matching the subsystem, such as `tests/test_naming.py`,
`tests/test_backends.py`, `tests/test_execution.py`, or the relevant `tests/test_qt_*.py`.

For cross-cutting or release-bound changes:

```powershell
uv run pytest -q
```

Repository hooks:

```powershell
uv run pre-commit run --all-files
```

The pre-push hook runs pytest. Ruff is a lint baseline, not a formatter. A project type
checker is `NOT VERIFIED` because none is configured in `pyproject.toml`.

GUI appearance/interaction, real ISO builds, cancellation timing, relocated EXE launch,
and platform-specific output require manual verification. Never label them PASS from an
import, mock, syntax check, or unit test alone.

## 8. Karpathy-Style Execution Rules

- Think before coding.
- Inspect relevant code, tests, and documentation before editing.
- State material assumptions and missing evidence.
- Choose the safest evidence-supported interpretation and disclose ambiguity.
- Prefer the simplest solution that fully satisfies the task.
- Make the smallest safe change; every changed line must trace to the task.
- Keep changes surgical.
- Do not perform unrelated refactoring, cleanup, renaming, or reformatting.
- Do not add speculative abstractions, configuration, dependencies, or features.
- Preserve public behavior unless the task explicitly requests a change.
- Match repository style and dependency direction.
- Reproduce bugs and add focused regression tests when practical.
- Run focused tests first, then the full suite for cross-cutting changes.
- Stop and report `NOT VERIFIED` when required evidence is missing.
- Do not label unexecuted tests as passing.

Complex, ambiguous, risky, or multi-file tasks should begin with:

```text
$karpathy-guidelines
```

## 9. Change Scope Rules

- Modify only files necessary for the task; do not clean up unrelated code.
- Preserve backend priority, profile names, command flags, naming, output locations,
  hidden-file behavior, dry runs, checksums, transactional publish, cancellation, and
  cleanup unless explicitly changed.
- Keep GUI layers dependent on shared services; lower layers must not access GUI state.
- Do not alter launchers without explicit scope and focused entrypoint tests.
- Do not manually edit generated artifacts, caches, ISO/checksum output, or `uv.lock`.
- Do not delete code, tests, data, docs, or compatibility paths without justification.
- Do not change public APIs, contracts, defaults, storage formats, or CLI behavior
  without authorization.
- Do not add/upgrade dependencies unless necessary and approved.
- Do not suppress warnings, loosen tests, add secret allowlists, or bypass hooks merely
  to make checks pass.
- Do not replace a working GUI/backend framework without explicit authorization.

## 10. Prohibited or Approval-Required Actions

Never:

- Modify files selected by the user as ISO source content.
- Execute installers or setup payloads found in source folders.
- Do not add antivirus bypasses or SmartScreen, Gatekeeper, execution-policy, or other
  security-tool bypasses.
- Hide, encrypt, or pack source executables.
- Bundle or redistribute `oscdimg.exe`.
- Store real secrets, credentials, certificates, or private machine paths in the repo.

Require explicit authorization before dependency/configuration changes, real ISO builds,
packaging/artifact regeneration, remote-state mutations, publishing, signing, deployment,
data deletion, broad refactors, framework/public API changes, commits, pushes, tags, or
branch/history changes.

Never run `git reset --hard`, `git clean -fd`, force push, or destructive checkout
without explicit authorization.

## 11. Testing and Evidence Standard

- **Confirmed**: supported directly by inspected files, actual output, or executed tests.
- **Inferred**: evidence-supported interpretation that is not directly proven.
- **NOT VERIFIED**: required proof is missing or the relevant command was not run.

Keep these separate. Failure reports must distinguish symptom, confirmed root cause (or
`NOT VERIFIED`), contributing factor, risk, recommendation, and remaining risk.

Do not claim runtime PASS after mocks, dry runs, or interrupted GUI sessions. An
intentional `KeyboardInterrupt` is not by itself a startup failure, but preceding runtime
behavior still requires evidence.

## 12. Definition of Done

A task is complete only when:

1. Requested scope is satisfied.
2. Relevant checks ran where possible and results are truthful.
3. No unrelated file was intentionally changed.
4. `git diff --check` is clean and the complete final diff was inspected.
5. Every changed line relates to the task.
6. Remaining risks and unverified areas are listed.
7. No temporary files, generated artifacts, or fake-secret canaries remain.
8. Documentation changed only when required.

Do not claim completion while critical verification is failing.

## 13. Final Response Format

Report:

1. Verdict: `PASS`, `WARN`, `FAIL`, or `NOT VERIFIED`.
2. What was inspected and confirmed.
3. Files changed and why.
4. Verification commands actually run and exact results.
5. Tests/checks not run.
6. Remaining risks and safest next step.
7. Suggested logical Git commit message.

## 14. Git Workflow

- Run `git status --short --branch` before editing.
- Preserve pre-existing user changes; do not overwrite another task's work.
- Inspect the final diff and keep one logical change per commit.
- Do not commit generated artifacts or combine unrelated fixes.
- Do not commit unless requested or explicitly authorized by the active workflow.
- Use a concise project-specific commit message when authorized.

Recommended sequence:

```text
inspect -> plan -> minimal implementation -> focused verification -> /review
-> inspect git diff -> logical commit
```

## 15. Review Workflow

Use `/review` after non-trivial implementation. Review correctness, regressions,
unintended behavior, missing tests, security/data risks, platform compatibility,
unnecessary complexity, unrelated diff, and documentation/code disagreement. Address or
report findings before completion. Review does not replace verification.

## 16. Nested Instruction Scope

No nested `AGENTS.md` was found at the last inspection. If one is added, root rules apply
repository-wide, deeper rules apply within their tree, and the most specific applicable
instructions take precedence. Explicit task instructions still apply unless they conflict
with safety or repository constraints.
