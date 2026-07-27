"""Qt bridge for the incremental PySide6 GUI migration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import threading

from PySide6.QtCore import Property, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from ..backends import detect_backends, select_backend
from ..constants import APP_VERSION, PROFILE_AUTO
from ..models import Backend, ScanResult
from ..naming import auto_names_from_source
from ..scanning import scan_source_folder
from ..utils import human_size


class QtIsoBridge(QObject):
    """Expose verified backend, naming, and scan services to QML."""

    statusChanged = Signal()
    backendsChanged = Signal()
    themeChanged = Signal()
    sourceChanged = Signal()
    scanChanged = Signal()
    _scanFinished = Signal(int, object, str)

    def __init__(
        self,
        detector: Callable[[], Sequence[Backend]] = detect_backends,
        scanner: Callable[[Path, str, bool], ScanResult] = scan_source_folder,
        namer: Callable[[Path], tuple[str, str, str]] = auto_names_from_source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._detector = detector
        self._scanner = scanner
        self._namer = namer
        self._backends: list[Backend] = []
        self._status_title = "Checking backends"
        self._status_detail = "Detecting available ISO tools..."
        self._preferred_backend = "Not detected"
        self._system_dark_mode = False
        self._source_folder = ""
        self._source_name = "Not selected"
        self._source_detail = "Choose a source folder"
        self._volume_label = "SOFTWARE_SETUP"
        self._iso_name = "Software_Setup.iso"
        self._is_scanning = False
        self._scan_files = 0
        self._scan_folders = 0
        self._scan_total_bytes = 0
        self._scan_warnings = 0
        self._scan_generation = 0
        self._scanFinished.connect(self._apply_scan_result)

        application = QGuiApplication.instance()
        if isinstance(application, QGuiApplication):
            style_hints = application.styleHints()
            self._system_dark_mode = (
                style_hints.colorScheme() == Qt.ColorScheme.Dark
            )
            style_hints.colorSchemeChanged.connect(self._on_color_scheme_changed)

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

    @Property(bool, notify=themeChanged)
    def systemDarkMode(self) -> bool:
        return self._system_dark_mode

    @Property(str, notify=sourceChanged)
    def sourceFolder(self) -> str:
        return self._source_folder

    @Property(str, notify=sourceChanged)
    def sourceName(self) -> str:
        return self._source_name

    @Property(str, notify=sourceChanged)
    def sourceDetail(self) -> str:
        return self._source_detail

    @Property(str, notify=sourceChanged)
    def volumeLabel(self) -> str:
        return self._volume_label

    @Property(str, notify=sourceChanged)
    def isoName(self) -> str:
        return self._iso_name

    @Property(bool, notify=scanChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(int, notify=scanChanged)
    def scanFiles(self) -> int:
        return self._scan_files

    @Property(int, notify=scanChanged)
    def scanFolders(self) -> int:
        return self._scan_folders

    @Property(str, notify=scanChanged)
    def scanSizeText(self) -> str:
        return human_size(self._scan_total_bytes)

    @Property(int, notify=scanChanged)
    def scanWarnings(self) -> int:
        return self._scan_warnings

    def _on_color_scheme_changed(self, color_scheme: Qt.ColorScheme) -> None:
        system_dark_mode = color_scheme == Qt.ColorScheme.Dark
        if self._system_dark_mode != system_dark_mode:
            self._system_dark_mode = system_dark_mode
            self.themeChanged.emit()

    @Slot(QUrl)
    @Slot(str)
    def selectSourceFolder(self, folder: QUrl | str) -> None:
        """Select a source, apply verified auto naming, then scan off the UI thread."""
        source_text = folder.toLocalFile() if isinstance(folder, QUrl) else folder
        source = Path(source_text).expanduser()
        if not source.exists() or not source.is_dir():
            self._scan_generation += 1
            self._source_folder = ""
            self._source_name = "Invalid source"
            self._source_detail = "Selected source folder is not available."
            self._is_scanning = False
            self._clear_scan_metrics()
            self.sourceChanged.emit()
            self.scanChanged.emit()
            return

        source = source.resolve()
        _safe_base, iso_name, label = self._namer(source)
        self._scan_generation += 1
        generation = self._scan_generation
        self._source_folder = str(source)
        self._source_name = source.name or str(source)
        self._source_detail = "Scanning folder..."
        self._volume_label = label
        self._iso_name = iso_name
        self._is_scanning = True
        self._clear_scan_metrics()
        self.sourceChanged.emit()
        self.scanChanged.emit()

        worker = threading.Thread(
            target=self._scan_source_worker,
            args=(generation, source),
            name=f"qt-source-scan-{generation}",
            daemon=True,
        )
        worker.start()

    def _clear_scan_metrics(self) -> None:
        self._scan_files = 0
        self._scan_folders = 0
        self._scan_total_bytes = 0
        self._scan_warnings = 0

    def _scan_source_worker(self, generation: int, source: Path) -> None:
        try:
            result = self._scanner(source, PROFILE_AUTO, True)
            self._scanFinished.emit(generation, result, "")
        except Exception as exc:
            self._scanFinished.emit(generation, None, str(exc))

    @Slot(int, object, str)
    def _apply_scan_result(
        self,
        generation: int,
        result: object,
        error: str,
    ) -> None:
        if generation != self._scan_generation:
            return

        self._is_scanning = False
        if error:
            self._clear_scan_metrics()
            self._source_detail = f"Scan failed: {error}"
        elif isinstance(result, ScanResult):
            self._scan_files = result.files
            self._scan_folders = result.dirs
            self._scan_total_bytes = result.total_bytes
            self._scan_warnings = len(result.warnings)
            self._source_detail = (
                f"{result.files} files • {human_size(result.total_bytes)}"
            )
        else:
            self._clear_scan_metrics()
            self._source_detail = "Scan failed: invalid scan result."

        self.sourceChanged.emit()
        self.scanChanged.emit()

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
