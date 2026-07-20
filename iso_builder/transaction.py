import os
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Sequence


def make_temporary_output_path(
    final_output: Path,
    *,
    token: Optional[str] = None,
) -> Path:
    transaction_token = token or uuid.uuid4().hex
    suffix = final_output.suffix or ".iso"
    stem = final_output.name[: -len(final_output.suffix)] if final_output.suffix else final_output.name
    return final_output.with_name(
        f".{stem}.{transaction_token}.partial{suffix}"
    )


def retarget_output_command(
    planned_command: Sequence[str],
    final_output: Path,
    temporary_output: Path,
) -> List[str]:
    final_text = str(final_output)
    matches = [
        index
        for index, argument in enumerate(planned_command)
        if argument == final_text
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Planned backend command must contain the final output path exactly once."
        )

    execution_command = list(planned_command)
    execution_command[matches[0]] = str(temporary_output)
    return execution_command


def temporary_output_candidates(temporary_output: Path) -> List[Path]:
    candidates = [
        temporary_output,
        temporary_output.with_suffix(temporary_output.suffix + ".iso"),
        temporary_output.with_suffix(".cdr"),
        Path(str(temporary_output) + ".iso"),
    ]
    unique: List[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def normalize_backend_output(temporary_output: Path) -> Path:
    found = [
        candidate
        for candidate in temporary_output_candidates(temporary_output)
        if candidate.exists()
    ]
    if not found:
        raise RuntimeError("ISO output file create nahi hua.")
    if len(found) != 1:
        raise RuntimeError(
            "Backend created multiple temporary ISO output candidates; "
            "safe publish abort kiya gaya."
        )
    backend_output = found[0]
    if backend_output != temporary_output:
        os.rename(backend_output, temporary_output)
    return temporary_output


def publish_temporary_output(
    temporary_output: Path,
    final_output: Path,
    *,
    platform_name: Optional[str] = None,
    rename_func: Optional[Callable[[Path, Path], None]] = None,
    link_func: Optional[Callable[[Path, Path], None]] = None,
    unlink_func: Optional[Callable[[Path], None]] = None,
) -> None:
    if final_output.exists():
        raise RuntimeError(
            f"Final output appeared during build; existing ISO preserve ki gayi: {final_output}"
        )

    platform_value = platform_name or os.name
    rename_output = rename_func or os.rename
    link_output = link_func or os.link
    unlink_output = unlink_func or os.unlink

    try:
        if platform_value == "nt":
            rename_output(temporary_output, final_output)
        else:
            link_output(temporary_output, final_output)
            try:
                unlink_output(temporary_output)
            except OSError:
                # The final hard link is already complete. The executor's
                # bounded cleanup handles a leftover temporary name.
                pass
    except OSError as error:
        if final_output.exists():
            raise RuntimeError(
                f"Final output appeared during build; existing ISO preserve ki gayi: {final_output}"
            ) from error
        raise RuntimeError(
            f"Atomic ISO publish failed; final output create nahi hui: {error}"
        ) from error


def cleanup_temporary_outputs(temporary_output: Path) -> List[str]:
    errors: List[str] = []
    for candidate in temporary_output_candidates(temporary_output):
        try:
            candidate.unlink(missing_ok=True)
        except OSError as error:
            errors.append(f"{candidate}: {error}")
    return errors
