from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Backend:
    name: str
    executable: str
    priority: int
    description: str
    supports_udf: bool
    supports_joliet: bool
    supports_iso_level3: bool
    source: str


@dataclass
class ScanResult:
    files: int = 0
    dirs: int = 0
    total_bytes: int = 0
    largest_file_bytes: int = 0
    largest_file_path: str = ""
    max_rel_path_len: int = 0
    max_name_len: int = 0
    non_ascii_names: int = 0
    hidden_items: int = 0
    symlinks: int = 0
    unreadable: int = 0
    empty_dirs: int = 0
    files_over_4gb: int = 0
    warnings: List[str] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


@dataclass(frozen=True)
class BuildOptions:
    """Immutable snapshot of user-selected settings for one build."""

    profile: str
    include_hidden: bool
    generate_hash: bool
    optimize_duplicates: bool
    auto_package: bool
    dry_run: bool


@dataclass(frozen=True)
class BuildRequest:
    """Immutable snapshot of all GUI inputs needed to prepare one build."""

    source_text: str
    output_text: str
    iso_name_text: str
    label_text: str
    backend_choice: str
    options: BuildOptions


@dataclass
class BuildPlan:
    """Structured build data passed between preparation and execution layers."""

    source: Path
    output_iso: Path
    label: str
    backend: Backend
    scan: ScanResult
    command: List[str]
    warnings: List[str]
    options: BuildOptions


@dataclass(frozen=True)
class BuildExecutionResult:
    """GUI-independent outcome returned after executing one build plan."""

    outcome: str
    output_iso: Path
    hash_path: Optional[Path] = None
    sha256: Optional[str] = None
    error: Optional[str] = None
