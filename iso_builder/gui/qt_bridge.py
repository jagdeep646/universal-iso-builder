"""Qt bridge for the incremental PySide6 GUI migration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import threading

from PySide6.QtCore import Property, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from ..backends import detect_backends, select_backend
from ..backends.imapi import cleanup_temp_script_from_command
from ..constants import APP_VERSION, PROFILE_AUTO, PROFILES
from ..models import Backend, BuildOptions, BuildPlan, BuildRequest, ScanResult
from ..naming import auto_names_from_source
from ..planner import prepare_build_plan
from ..scanning import scan_source_folder
from ..utils import human_size, quote_cmd


class QtIsoBridge(QObject):
    """Expose verified backend, naming, and scan services to QML."""

    statusChanged = Signal()
    backendsChanged = Signal()
    themeChanged = Signal()
    sourceChanged = Signal()
    scanChanged = Signal()
    settingsChanged = Signal()
    planningChanged = Signal()
    commandChanged = Signal()
    availabilityChanged = Signal()
    _scanFinished = Signal(int, object, str)
    _planFinished = Signal(int, object, str)

    def __init__(
        self,
        detector: Callable[[], Sequence[Backend]] = detect_backends,
        scanner: Callable[[Path, str, bool], ScanResult] = scan_source_folder,
        namer: Callable[[Path], tuple[str, str, str]] = auto_names_from_source,
        planner: Callable[[BuildRequest, list[Backend]], BuildPlan] = prepare_build_plan,
        command_cleanup: Callable[[Sequence[str]], None] = cleanup_temp_script_from_command,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._detector = detector
        self._scanner = scanner
        self._namer = namer
        self._planner = planner
        self._command_cleanup = command_cleanup
        self._backends: list[Backend] = []
        self._status_title = "Checking backends"
        self._status_detail = "Detecting available ISO tools..."
        self._preferred_backend = "Not detected"
        self._system_dark_mode = False
        self._source_folder = ""
        self._source_name = "Not selected"
        self._source_detail = "Choose a source folder"
        self._safe_base = "Software_Setup"
        self._output_folder = ""
        self._volume_label = "SOFTWARE_SETUP"
        self._iso_name = "Software_Setup.iso"
        self._selected_profile = PROFILE_AUTO
        self._selected_backend = "Auto"
        self._include_hidden = True
        self._generate_hash = True
        self._optimize_duplicates = False
        self._auto_package = True
        self._is_scanning = False
        self._scan_files = 0
        self._scan_folders = 0
        self._scan_total_bytes = 0
        self._scan_warnings = 0
        self._scan_generation = 0
        self._is_planning = False
        self._planning_generation = 0
        self._command_text = ""
        self._command_warnings_text = ""
        self._planning_error = ""
        self._planned_output = ""
        self._scanFinished.connect(self._apply_scan_result)
        self._planFinished.connect(self._apply_plan_result)

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

    @Property(str, notify=settingsChanged)
    def outputFolder(self) -> str:
        return self._output_folder

    @Property(str, notify=settingsChanged)
    def outputPreview(self) -> str:
        if not self._output_folder:
            return "Choose an output folder"
        output_folder = Path(self._output_folder)
        if self._auto_package:
            return str(
                output_folder
                / f"{self._safe_base}_ISO"
                / self._iso_name
            )
        return str(output_folder / self._iso_name)

    @Property(list, constant=True)
    def profileOptions(self) -> list[str]:
        return list(PROFILES)

    @Property(list, notify=backendsChanged)
    def backendOptions(self) -> list[str]:
        return ["Auto"] + [
            f"{backend.name} | {backend.executable}"
            for backend in self._backends
        ]

    @Property(str, notify=settingsChanged)
    def selectedProfile(self) -> str:
        return self._selected_profile

    @Property(str, notify=settingsChanged)
    def selectedBackend(self) -> str:
        return self._selected_backend

    @Property(bool, notify=settingsChanged)
    def includeHidden(self) -> bool:
        return self._include_hidden

    @Property(bool, notify=settingsChanged)
    def generateHash(self) -> bool:
        return self._generate_hash

    @Property(bool, notify=settingsChanged)
    def optimizeDuplicates(self) -> bool:
        return self._optimize_duplicates

    @Property(bool, notify=settingsChanged)
    def autoPackage(self) -> bool:
        return self._auto_package

    @Property(bool, notify=planningChanged)
    def isPlanning(self) -> bool:
        return self._is_planning

    @Property(bool, notify=availabilityChanged)
    def canShowCommand(self) -> bool:
        return bool(
            self._source_folder
            and self._output_folder
            and self._backends
            and not self._is_scanning
            and not self._is_planning
        )

    @Property(str, notify=commandChanged)
    def commandText(self) -> str:
        return self._command_text

    @Property(str, notify=commandChanged)
    def commandWarningsText(self) -> str:
        return self._command_warnings_text

    @Property(str, notify=commandChanged)
    def planningError(self) -> str:
        return self._planning_error

    @Property(str, notify=commandChanged)
    def plannedOutput(self) -> str:
        return self._planned_output

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
            self.availabilityChanged.emit()
            return

        source = source.resolve()
        safe_base, iso_name, label = self._namer(source)
        self._scan_generation += 1
        generation = self._scan_generation
        self._source_folder = str(source)
        self._source_name = source.name or str(source)
        self._source_detail = "Scanning folder..."
        self._safe_base = safe_base
        if not self._output_folder:
            self._output_folder = str(source.parent)
        self._volume_label = label
        self._iso_name = iso_name
        self._is_scanning = True
        self._clear_scan_metrics()
        self._invalidate_command()
        self.sourceChanged.emit()
        self.scanChanged.emit()
        self.settingsChanged.emit()
        self.availabilityChanged.emit()

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
        self.availabilityChanged.emit()

    @Slot(QUrl)
    @Slot(str)
    def selectOutputFolder(self, folder: QUrl | str) -> None:
        output_text = folder.toLocalFile() if isinstance(folder, QUrl) else folder
        output = Path(output_text).expanduser()
        if not output.exists() or not output.is_dir():
            self._planning_error = "Selected output folder is not available."
            self.commandChanged.emit()
            return
        self._output_folder = str(output.resolve())
        self._invalidate_command()
        self.settingsChanged.emit()
        self.availabilityChanged.emit()

    @Slot(str)
    def setVolumeLabel(self, value: str) -> None:
        self._volume_label = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(str)
    def setIsoName(self, value: str) -> None:
        self._iso_name = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(str)
    def setProfile(self, value: str) -> None:
        if value not in PROFILES:
            return
        self._selected_profile = value
        self._update_preferred_backend()
        self._invalidate_command()
        self.settingsChanged.emit()
        self.backendsChanged.emit()

    @Slot(str)
    def setBackend(self, value: str) -> None:
        if value not in self.backendOptions:
            return
        self._selected_backend = value
        self._update_preferred_backend()
        self._invalidate_command()
        self.settingsChanged.emit()
        self.backendsChanged.emit()

    @Slot(bool)
    def setIncludeHidden(self, value: bool) -> None:
        self._include_hidden = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(bool)
    def setGenerateHash(self, value: bool) -> None:
        self._generate_hash = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(bool)
    def setOptimizeDuplicates(self, value: bool) -> None:
        self._optimize_duplicates = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(bool)
    def setAutoPackage(self, value: bool) -> None:
        self._auto_package = value
        self._invalidate_command()
        self.settingsChanged.emit()

    def _invalidate_command(self) -> None:
        self._command_text = ""
        self._command_warnings_text = ""
        self._planning_error = ""
        self._planned_output = ""
        self.commandChanged.emit()

    def _update_preferred_backend(self) -> None:
        if not self._backends:
            self._preferred_backend = "Not available"
            return
        if self._selected_backend == "Auto":
            preferred = select_backend(self._backends, self._selected_profile)
            self._preferred_backend = preferred.name if preferred else "Not available"
            return
        self._preferred_backend = self._selected_backend.split(" | ", 1)[0].strip()

    def _snapshot_build_request(self) -> BuildRequest:
        return BuildRequest(
            source_text=self._source_folder,
            output_text=self._output_folder,
            iso_name_text=self._iso_name,
            label_text=self._volume_label,
            backend_choice=self._selected_backend,
            options=BuildOptions(
                profile=self._selected_profile,
                include_hidden=self._include_hidden,
                generate_hash=self._generate_hash,
                optimize_duplicates=self._optimize_duplicates,
                auto_package=self._auto_package,
                dry_run=True,
            ),
        )

    @Slot()
    def showCommand(self) -> None:
        if not self.canShowCommand:
            self._planning_error = (
                "Select valid source/output folders, wait for scanning, "
                "and ensure an ISO backend is available."
            )
            self.commandChanged.emit()
            return

        request = self._snapshot_build_request()
        backends = list(self._backends)
        self._planning_generation += 1
        generation = self._planning_generation
        self._is_planning = True
        self._planning_error = ""
        self._command_text = ""
        self._command_warnings_text = ""
        self._planned_output = ""
        self.planningChanged.emit()
        self.commandChanged.emit()
        self.availabilityChanged.emit()

        worker = threading.Thread(
            target=self._plan_worker,
            args=(generation, request, backends),
            name=f"qt-command-plan-{generation}",
            daemon=True,
        )
        worker.start()

    def _plan_worker(
        self,
        generation: int,
        request: BuildRequest,
        backends: list[Backend],
    ) -> None:
        plan = None
        try:
            plan = self._planner(request, backends)
            self._planFinished.emit(generation, plan, "")
        except Exception as exc:
            self._planFinished.emit(generation, None, str(exc))
        finally:
            if isinstance(plan, BuildPlan):
                try:
                    self._command_cleanup(plan.command)
                except Exception:
                    pass

    @Slot(int, object, str)
    def _apply_plan_result(
        self,
        generation: int,
        result: object,
        error: str,
    ) -> None:
        if generation != self._planning_generation:
            return
        self._is_planning = False
        if error:
            self._planning_error = error
            self._command_text = ""
            self._command_warnings_text = ""
            self._planned_output = ""
        elif isinstance(result, BuildPlan):
            self._planning_error = ""
            self._command_text = quote_cmd(result.command)
            self._command_warnings_text = "\n".join(result.warnings)
            self._planned_output = str(result.output_iso)
            if result.options.auto_package:
                self._iso_name = result.output_iso.name
                self._volume_label = result.label
                self.settingsChanged.emit()
        else:
            self._planning_error = "Command preparation returned an invalid plan."
            self._command_text = ""
            self._command_warnings_text = ""
            self._planned_output = ""

        self.planningChanged.emit()
        self.commandChanged.emit()
        self.availabilityChanged.emit()

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
            if self._selected_backend not in self.backendOptions:
                self._selected_backend = "Auto"
            self._update_preferred_backend()
            preferred = (
                next(
                    (
                        backend
                        for backend in backends
                        if backend.name == self._preferred_backend
                    ),
                    None,
                )
                if self._preferred_backend != "Not available"
                else None
            )
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
        self.settingsChanged.emit()
        self.availabilityChanged.emit()
