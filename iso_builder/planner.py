from typing import List

from .backends.commands import build_command, validate_hidden_file_option
from .backends.detection import select_requested_backend
from .constants import PATH_WARNING_THRESHOLD
from .models import Backend, BuildPlan, BuildRequest
from .naming import resolve_build_paths
from .scanning import scan_source_folder


def prepare_build_plan(request: BuildRequest, backends: List[Backend]) -> BuildPlan:
    """Create a complete build plan without reading or updating Tk widgets."""
    options = request.options
    source, output_iso, label, _ = resolve_build_paths(
        source_text=request.source_text,
        output_text=request.output_text,
        iso_name_text=request.iso_name_text,
        label_text=request.label_text,
        auto_package=options.auto_package,
    )
    backend = select_requested_backend(
        backends=backends,
        backend_choice=request.backend_choice,
        profile=options.profile,
    )
    validate_hidden_file_option(backend, options.include_hidden)
    scan = scan_source_folder(source, options.profile, options.include_hidden)
    command, command_warnings = build_command(
        backend=backend,
        source=source,
        output_iso=output_iso,
        label=label,
        profile=options.profile,
        include_hidden=options.include_hidden,
        optimize_duplicates=options.optimize_duplicates,
    )
    if len(str(output_iso)) > PATH_WARNING_THRESHOLD:
        command_warnings.append(
            f"Output ISO absolute path {len(str(output_iso))} chars hai. "
            "Old Windows/tools ya disabled long-path support par build fail ho sakta hai."
        )
    return BuildPlan(
        source=source,
        output_iso=output_iso,
        label=label,
        backend=backend,
        scan=scan,
        command=command,
        warnings=command_warnings,
        options=options,
    )
