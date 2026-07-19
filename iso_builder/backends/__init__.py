"""Backend detection and selection public API."""

from .detection import (
    detect_backends,
    find_windows_powershell,
    select_backend,
    select_requested_backend,
)

__all__ = [
    "detect_backends",
    "find_windows_powershell",
    "select_backend",
    "select_requested_backend",
]
