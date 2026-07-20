import re
from pathlib import Path
from typing import Tuple


def clean_volume_label(label: str) -> str:
    """Safe label for common ISO/UDF tools. Keep it simple for old systems."""
    label = (label or "SOFTWARE_SETUP").strip().upper()
    label = re.sub(r"[^A-Z0-9_]", "_", label)
    label = re.sub(r"_+", "_", label).strip("_")
    if not label:
        label = "SOFTWARE_SETUP"
    return label[:32]


def normalize_iso_name(name: str) -> str:
    name = (name or "Software_Setup.iso").strip()
    name = re.sub(r"[<>:\"/\\|?*]", "_", name)
    if not name.lower().endswith(".iso"):
        name += ".iso"
    return name


def validate_manual_iso_name(name: str) -> str:
    """Validate a user-entered ISO filename before it reaches filesystem APIs."""
    raw_name = name or ""
    if not raw_name.strip():
        return normalize_iso_name(raw_name)

    if raw_name != raw_name.strip() or raw_name.endswith("."):
        raise ValueError("ISO filename space ya dot se start/end nahi ho sakta.")
    if re.search(r"[<>:\"/\\|?*]", raw_name):
        raise ValueError("ISO filename me Windows-invalid character hai.")
    if re.search(r"[\x00-\x1f]", raw_name):
        raise ValueError("ISO filename me control character allowed nahi hai.")

    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
        "COM¹", "COM²", "COM³",
        "LPT¹", "LPT²", "LPT³",
    }
    base_name = raw_name.split(".", 1)[0].upper()
    if base_name in reserved:
        raise ValueError(f"ISO filename Windows reserved device name use nahi kar sakta: {base_name}")

    return normalize_iso_name(raw_name)


def safe_path_component(name: str, fallback: str = "Software_Setup") -> str:
    """Create a safe Windows/macOS/Linux folder/file base name while keeping it readable."""
    name = (name or fallback).strip()
    name = re.sub(r"[<>:\"/\\|?*]", "_", name)
    name = re.sub(r"[\x00-\x1f]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(" .")
    if not name:
        name = fallback

    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if name.upper() in reserved:
        name = f"{name}_SETUP"

    return name[:120]


def auto_names_from_source(source: Path) -> Tuple[str, str, str]:
    """Return (safe_base_name, iso_file_name, volume_label) from original source folder name."""
    safe_base = safe_path_component(source.name, "Software_Setup")
    iso_name = normalize_iso_name(safe_base)
    label = clean_volume_label(source.name)
    return safe_base, iso_name, label


def resolve_build_paths(
    source_text: str,
    output_text: str,
    iso_name_text: str,
    label_text: str,
    auto_package: bool,
) -> Tuple[Path, Path, str, str]:
    """Validate raw path inputs and return resolved source/output build paths."""
    source_text = source_text.strip()
    output_text = output_text.strip()

    if not source_text:
        raise ValueError("Source folder select karo.")
    if not output_text:
        raise ValueError("Output folder select karo.")

    source = Path(source_text).expanduser()
    output_folder = Path(output_text).expanduser()

    if not source.exists() or not source.is_dir():
        raise ValueError("Source folder valid nahi hai.")
    if not output_folder.exists() or not output_folder.is_dir():
        raise ValueError("Output folder valid nahi hai.")

    if auto_package:
        safe_base, iso_name, label = auto_names_from_source(source)
        package_folder = output_folder / f"{safe_base}_ISO"
        output_iso = package_folder / iso_name
    else:
        iso_name = validate_manual_iso_name(iso_name_text)
        label = clean_volume_label(label_text)
        output_iso = output_folder / iso_name

    source_resolved = source.resolve()
    output_iso_resolved = output_iso.resolve()

    try:
        output_iso_resolved.relative_to(source_resolved)
    except ValueError:
        pass
    else:
        raise ValueError(
            "Output ISO source folder ke andar nahi ho sakta. Alag output folder select karo."
        )

    if output_iso_resolved.exists():
        raise FileExistsError(f"Output ISO already exists: {output_iso_resolved}")

    return source_resolved, output_iso_resolved, label, iso_name
