"""Read-only Qt bridge for the incremental PySide6 GUI migration."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..backends import detect_backends, select_backend
from ..constants import APP_VERSION, PROFILE_AUTO
from ..models import Backend


class QtIsoBridge(QObject):
    """Expose backend availability to QML without changing build behavior."""

    statusChanged = Signal()
    backendsChanged = Signal()

    def __init__(
        self,
        detector: Callable[[], Sequence[Backend]] = detect_backends,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._detector = detector
        self._backends: list[Backend] = []
        self._status_title = "Checking backends"
        self._status_detail = "Detecting available ISO tools..."
        self._preferred_backend = "Not detected"

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return APP_VERSION

    @Property(str, notify=statusChanged)
    def statusTitle(self) -> str:
        return self._status_title

    @Property(str, notify=statusChanged)
    def statusDetail(self) -> str:
        return self._status_detail

    @Property(str, notify=backendsChanged)
    def preferredBackend(self) -> str:
        return self._preferred_backend

    @Property(int, notify=backendsChanged)
    def backendCount(self) -> int:
        return len(self._backends)

    @Property(list, notify=backendsChanged)
    def backendNames(self) -> list[str]:
        return [backend.name for backend in self._backends]

    @Slot()
    def refreshBackends(self) -> None:
        """Refresh the read-only backend snapshot shown by the QML shell."""
        try:
            backends = list(self._detector())
        except Exception as exc:
            self._backends = []
            self._preferred_backend = "Detection failed"
            self._status_title = "Backend check failed"
            self._status_detail = str(exc)
        else:
            self._backends = backends
            preferred = select_backend(backends, PROFILE_AUTO)
            if preferred is None:
                self._preferred_backend = "Not available"
                self._status_title = "Backend required"
                self._status_detail = "No compatible ISO backend was detected."
            else:
                self._preferred_backend = preferred.name
                self._status_title = "System ready"
                self._status_detail = (
                    f"{len(backends)} backend"
                    f"{'s' if len(backends) != 1 else ''} available"
                )

        self.backendsChanged.emit()
        self.statusChanged.emit()
