import hashlib
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from .backends.imapi import cleanup_temp_script_from_command
from .models import BuildExecutionResult, BuildPlan
from .utils import human_size, quote_cmd


def calculate_sha256(file_path: Path, progress: Optional[Callable[[int], None]] = None) -> str:
    hasher = hashlib.sha256()
    total_read = 0
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            hasher.update(chunk)
            total_read += len(chunk)
            if progress:
                progress(total_read)
    return hasher.hexdigest()


def run_process(command: List[str], log: Callable[[str], None]) -> int:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        log(line.rstrip())
    process.wait()
    return int(process.returncode)


def execute_build_plan(
    plan: BuildPlan,
    log: Callable[[str], None],
) -> BuildExecutionResult:
    """Execute a prepared build without reading or updating Tk widgets."""
    source = plan.source
    output_iso = plan.output_iso
    label = plan.label
    backend = plan.backend
    scan = plan.scan
    command = plan.command
    warnings = plan.warnings
    options = plan.options

    try:
        log("=" * 72)
        log("Build started")
        log(f"Backend: {backend.name} -> {backend.executable}")
        log(f"Profile: {options.profile}")
        log(f"Dry run: {'ON' if options.dry_run else 'OFF'}")
        log(f"Generate SHA256: {'ON' if options.generate_hash else 'OFF'}")
        log(f"Auto package: {'ON' if options.auto_package else 'OFF'}")
        log(f"Source: {source}")
        log(f"Output: {output_iso}")
        log(f"Output package folder: {output_iso.parent}")
        log(f"Volume label: {label}")
        log(f"Files: {scan.files} | Size: {human_size(scan.total_bytes)}")
        for warning in warnings:
            log(f"Command warning: {warning}")
        log("Command:")
        log(quote_cmd(command))

        if options.dry_run:
            log("Dry run ON: actual ISO create nahi kiya gaya.")
            log("Build finished: DRY RUN")
            return BuildExecutionResult(
                outcome="DRY RUN",
                output_iso=output_iso,
            )

        output_iso.parent.mkdir(parents=True, exist_ok=True)
        return_code = run_process(command, log)
        if return_code != 0:
            raise RuntimeError(f"ISO backend failed with exit code {return_code}")

        if not output_iso.exists():
            candidates = [
                output_iso.with_suffix(output_iso.suffix + ".iso"),
                output_iso.with_suffix(".cdr"),
                Path(str(output_iso) + ".iso"),
            ]
            found = next((path for path in candidates if path.exists()), None)
            if found:
                log(f"Backend created file at {found}; renaming to {output_iso}")
                found.rename(output_iso)

        if not output_iso.exists() or output_iso.stat().st_size == 0:
            raise RuntimeError("ISO output file create nahi hua ya empty hai.")

        log(f"ISO created: {output_iso}")
        log(f"ISO size: {human_size(output_iso.stat().st_size)}")

        hash_path: Optional[Path] = None
        sha256: Optional[str] = None
        if options.generate_hash:
            log("Generating SHA256...")
            sha256 = calculate_sha256(output_iso)
            hash_path = output_iso.with_suffix(output_iso.suffix + ".sha256.txt")
            hash_path.write_text(f"{sha256}  {output_iso.name}\n", encoding="utf-8")
            log(f"SHA256: {sha256}")
            log(f"Hash saved: {hash_path}")

        log(f"Package folder ready: {output_iso.parent}")
        log("Build finished: PASS")
        return BuildExecutionResult(
            outcome="PASS",
            output_iso=output_iso,
            hash_path=hash_path,
            sha256=sha256,
        )
    except Exception as error:
        log(f"ERROR: {error}")
        log("Build finished: FAIL")
        return BuildExecutionResult(
            outcome="FAIL",
            output_iso=output_iso,
            error=str(error),
        )
    finally:
        cleanup_temp_script_from_command(command)
