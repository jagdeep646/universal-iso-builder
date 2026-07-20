import hashlib
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from .backends.imapi import cleanup_temp_script_from_command
from .cancellation import BuildCancellation, BuildCancelled
from .models import BuildExecutionResult, BuildPlan
from .preflight import validate_output_storage
from .transaction import (
    cleanup_temporary_outputs,
    make_temporary_output_path,
    normalize_backend_output,
    publish_temporary_output,
    retarget_output_command,
)
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


def run_process(
    command: List[str],
    log: Callable[[str], None],
    cancellation: Optional[BuildCancellation] = None,
) -> int:
    if cancellation is not None:
        cancellation.raise_if_cancelled()

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if cancellation is not None:
        cancellation.register_process(process)
    try:
        assert process.stdout is not None
        for line in process.stdout:
            log(line.rstrip())
        process.wait()
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        return int(process.returncode)
    finally:
        if cancellation is not None:
            cancellation.clear_process(process)
        if process.stdout is not None:
            process.stdout.close()


def execute_build_plan(
    plan: BuildPlan,
    log: Callable[[str], None],
    cancellation: Optional[BuildCancellation] = None,
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
    temporary_output: Optional[Path] = None

    try:
        if cancellation is not None:
            cancellation.raise_if_cancelled()

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
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            log("Dry run ON: actual ISO create nahi kiya gaya.")
            log("Build finished: DRY RUN")
            return BuildExecutionResult(
                outcome="DRY RUN",
                output_iso=output_iso,
            )

        if cancellation is not None:
            cancellation.raise_if_cancelled()
        storage = validate_output_storage(output_iso, scan.total_bytes)
        log(
            "Storage preflight: "
            f"required estimate {human_size(storage.required_bytes)} | "
            f"free {human_size(storage.free_bytes)} | "
            f"filesystem {storage.filesystem or 'NOT VERIFIED'}"
        )
        output_iso.parent.mkdir(parents=True, exist_ok=True)
        if output_iso.exists():
            raise RuntimeError(f"Output ISO already exists: {output_iso}")

        temporary_output = make_temporary_output_path(output_iso)
        execution_command = retarget_output_command(
            command,
            output_iso,
            temporary_output,
        )
        log("Transactional execution command:")
        log(quote_cmd(execution_command))

        return_code = run_process(execution_command, log, cancellation)
        if return_code != 0:
            raise RuntimeError(f"ISO backend failed with exit code {return_code}")

        if cancellation is not None:
            cancellation.raise_if_cancelled()
        normalize_backend_output(temporary_output)
        if temporary_output.stat().st_size == 0:
            raise RuntimeError("ISO output file create nahi hua ya empty hai.")

        if cancellation is not None:
            cancellation.raise_if_cancelled()
        publish_temporary_output(temporary_output, output_iso)
        log(f"ISO created: {output_iso}")
        log(f"ISO size: {human_size(output_iso.stat().st_size)}")

        hash_path: Optional[Path] = None
        sha256: Optional[str] = None
        if options.generate_hash:
            log("Generating SHA256...")

            def check_hash_cancellation(_total_read: int) -> None:
                if cancellation is not None:
                    cancellation.raise_if_cancelled()

            sha256 = calculate_sha256(
                output_iso,
                check_hash_cancellation if cancellation is not None else None,
            )
            if cancellation is not None:
                cancellation.raise_if_cancelled()
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
    except BuildCancelled as error:
        log(f"CANCELLED: {error}")
        if output_iso.exists():
            log(f"Completed ISO preserved: {output_iso}")
        log("Build finished: CANCELLED")
        return BuildExecutionResult(
            outcome="CANCELLED",
            output_iso=output_iso,
            error=str(error),
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
        if temporary_output is not None:
            for cleanup_error in cleanup_temporary_outputs(temporary_output):
                log(f"WARNING: Temporary output cleanup failed: {cleanup_error}")
        cleanup_temp_script_from_command(command)
