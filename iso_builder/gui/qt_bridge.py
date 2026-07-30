"""Qt bridge for the incremental PySide6 GUI migration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import re
import threading

from PySide6.QtCore import Property, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from ..backends import detect_backends, select_backend
from ..backends.imapi import cleanup_temp_script_from_command
from ..cancellation import BuildCancellation
from ..constants import APP_VERSION, PROFILE_AUTO, PROFILES
from ..execution import execute_build_plan
from ..models import (
    Backend,
    BuildExecutionResult,
    BuildOptions,
    BuildPlan,
    BuildRequest,
    ScanResult,
)
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
    executionChanged = Signal()
    availabilityChanged = Signal()
    safeToClose = Signal()
    _scanFinished = Signal(int, object, str)
    _planFinished = Signal(int, object, str)
    _dryRunProgress = Signal(int, str, float)
    _dryRunFinished = Signal(int, object, str, object)
    _buildProgress = Signal(int, str, float, bool)
    _buildLog = Signal(int, str)
    _buildFinished = Signal(int, object, str, object)
    _buildWarningRequested = Signal(int, object, object, object)

    def __init__(
        self,
        detector: Callable[[], Sequence[Backend]] = detect_backends,
        scanner: Callable[[Path, str, bool], ScanResult] = scan_source_folder,
        namer: Callable[[Path], tuple[str, str, str]] = auto_names_from_source,
        planner: Callable[[BuildRequest, list[Backend]], BuildPlan] = prepare_build_plan,
        executor: Callable[..., BuildExecutionResult] = execute_build_plan,
        command_cleanup: Callable[[Sequence[str]], None] = cleanup_temp_script_from_command,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._detector = detector
        self._scanner = scanner
        self._namer = namer
        self._planner = planner
        self._executor = executor
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
        self._is_dry_running = False
        self._build_progress_indeterminate = False
        self._build_hash_path = ""
        self._execution_generation = 0
        self._build_outcome = "IDLE"
        self._build_status_text = "Ready for dry run"
        self._build_progress = 0.0
        self._build_log_text = ""
        self._build_error = ""
        self._last_execution_output = ""
        self._execution_mode = "IDLE"
        self._is_build_running = False
        self._build_progress_indeterminate = False
        self._build_hash_path = ""
        self._build_cancellation: BuildCancellation | None = None
        self._close_requested = False
        self._build_warning_pending = False
        self._build_warning_text = ""
        self._build_warning_context: tuple[threading.Event, dict[str, bool]] | None = None
        self._scanFinished.connect(self._apply_scan_result)
        self._planFinished.connect(self._apply_plan_result)
        self._dryRunProgress.connect(self._apply_dry_run_progress)
        self._dryRunFinished.connect(self._apply_dry_run_result)
        self._buildProgress.connect(self._apply_build_progress)
        self._buildLog.connect(self._apply_build_log)
        self._buildFinished.connect(self._apply_build_result)
        self._buildWarningRequested.connect(self._apply_build_warning_request)

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
            and not self._is_dry_running
            and not self._is_build_running
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

    @Property(bool, notify=executionChanged)
    def isDryRunning(self) -> bool:
        return self._is_dry_running

    @Property(bool, notify=availabilityChanged)
    def canRunDryRun(self) -> bool:
        return bool(
            self._source_folder
            and self._output_folder
            and self._backends
            and not self._is_scanning
            and not self._is_planning
            and not self._is_dry_running
            and not self._is_build_running
        )

    @Property(bool, notify=availabilityChanged)
    def canStartBuild(self) -> bool:
        return bool(
            self._source_folder
            and self._output_folder
            and self._backends
            and not self._is_scanning
            and not self._is_planning
            and not self._is_dry_running
            and not self._is_build_running
        )

    @Property(bool, notify=executionChanged)
    def isBuildRunning(self) -> bool:
        return self._is_build_running

    @Property(str, notify=executionChanged)
    def executionMode(self) -> str:
        return self._execution_mode

    @Property(str, notify=executionChanged)
    def buildOutcome(self) -> str:
        return self._build_outcome

    @Property(str, notify=executionChanged)
    def buildStatusText(self) -> str:
        return self._build_status_text

    @Property(float, notify=executionChanged)
    def buildProgress(self) -> float:
        return self._build_progress

    @Property(bool, notify=executionChanged)
    def buildProgressIndeterminate(self) -> bool:
        return self._build_progress_indeterminate

    @Property(int, notify=executionChanged)
    def buildProgressPercent(self) -> int:
        return round(self._build_progress * 100)

    @Property(str, notify=executionChanged)
    def buildLogText(self) -> str:
        return self._build_log_text

    @Property(str, notify=executionChanged)
    def buildError(self) -> str:
        return self._build_error

    @Property(str, notify=executionChanged)
    def lastExecutionOutput(self) -> str:
        return self._last_execution_output

    @Property(str, notify=executionChanged)
    def buildHashPath(self) -> str:
        return self._build_hash_path

    @Property(bool, notify=executionChanged)
    def buildWarningPending(self) -> bool:
        return self._build_warning_pending

    @Property(str, notify=executionChanged)
    def buildWarningText(self) -> str:
        return self._build_warning_text

    def _on_color_scheme_changed(self, color_scheme: Qt.ColorScheme) -> None:
        system_dark_mode = color_scheme == Qt.ColorScheme.Dark
        if self._system_dark_mode != system_dark_mode:
            self._system_dark_mode = system_dark_mode
            self.themeChanged.emit()

    @Slot(QUrl)
    @Slot(str)
    def selectSourceFolder(self, folder: QUrl | str) -> None:
        """Select a source, apply verified auto naming, then scan off the UI thread."""
        if self._is_dry_running or self._is_build_running:
            return
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
        if self._is_dry_running or self._is_build_running:
            return
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

    @Slot(QUrl, result=str)
    def localPathForUrl(self, folder: QUrl) -> str:
        return folder.toLocalFile()

    @Slot(
        str,
        str,
        str,
        str,
        str,
        bool,
        bool,
        bool,
        bool,
        result=bool,
    )
    def applyBuildSettings(
        self,
        output_text: str,
        iso_name: str,
        volume_label: str,
        profile: str,
        backend: str,
        auto_package: bool,
        include_hidden: bool,
        generate_hash: bool,
        optimize_duplicates: bool,
    ) -> bool:
        """Atomically apply one Settings-dialog draft on the Qt UI thread."""
        if self._is_dry_running or self._is_build_running:
            return False

        output = Path(output_text).expanduser()
        if not output.exists() or not output.is_dir():
            self._planning_error = "Selected output folder is not available."
            self.commandChanged.emit()
            return False
        if profile not in PROFILES:
            self._planning_error = "Selected build profile is not available."
            self.commandChanged.emit()
            return False
        if backend not in self.backendOptions:
            self._planning_error = "Selected ISO backend is not available."
            self.commandChanged.emit()
            return False

        self._output_folder = str(output.resolve())
        self._iso_name = iso_name
        self._volume_label = volume_label
        self._selected_profile = profile
        self._selected_backend = backend
        self._auto_package = auto_package
        self._include_hidden = include_hidden
        self._generate_hash = generate_hash
        self._optimize_duplicates = optimize_duplicates
        self._update_preferred_backend()
        self._invalidate_command()
        self.settingsChanged.emit()
        self.backendsChanged.emit()
        self.availabilityChanged.emit()
        return True

    @Slot(str)
    def setVolumeLabel(self, value: str) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        self._volume_label = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(str)
    def setIsoName(self, value: str) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        self._iso_name = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(str)
    def setProfile(self, value: str) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        if value not in PROFILES:
            return
        self._selected_profile = value
        self._update_preferred_backend()
        self._invalidate_command()
        self.settingsChanged.emit()
        self.backendsChanged.emit()

    @Slot(str)
    def setBackend(self, value: str) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        if value not in self.backendOptions:
            return
        self._selected_backend = value
        self._update_preferred_backend()
        self._invalidate_command()
        self.settingsChanged.emit()
        self.backendsChanged.emit()

    @Slot(bool)
    def setIncludeHidden(self, value: bool) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        self._include_hidden = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(bool)
    def setGenerateHash(self, value: bool) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        self._generate_hash = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(bool)
    def setOptimizeDuplicates(self, value: bool) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        self._optimize_duplicates = value
        self._invalidate_command()
        self.settingsChanged.emit()

    @Slot(bool)
    def setAutoPackage(self, value: bool) -> None:
        if self._is_dry_running or self._is_build_running:
            return
        self._auto_package = value
        self._invalidate_command()
        self.settingsChanged.emit()

    def _invalidate_command(self) -> None:
        self._command_text = ""
        self._command_warnings_text = ""
        self._planning_error = ""
        self._planned_output = ""
        self.commandChanged.emit()
        self._reset_dry_run_result()

    def _reset_dry_run_result(self) -> None:
        self._execution_mode = "IDLE"
        self._build_outcome = "IDLE"
        self._build_status_text = "Ready for dry run"
        self._build_progress = 0.0
        self._build_progress_indeterminate = False
        self._build_log_text = ""
        self._build_error = ""
        self._last_execution_output = ""
        self._build_hash_path = ""
        self._build_warning_pending = False
        self._build_warning_text = ""
        self._build_warning_context = None
        self.executionChanged.emit()

    def _update_preferred_backend(self) -> None:
        if not self._backends:
            self._preferred_backend = "Not available"
            return
        if self._selected_backend == "Auto":
            preferred = select_backend(self._backends, self._selected_profile)
            self._preferred_backend = preferred.name if preferred else "Not available"
            return
        self._preferred_backend = self._selected_backend.split(" | ", 1)[0].strip()

    def _snapshot_build_request(self, *, dry_run: bool = True) -> BuildRequest:
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
                dry_run=dry_run,
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

        request = self._snapshot_build_request(dry_run=True)
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
    def runDryRun(self) -> None:
        """Prepare and execute a dry-run-only snapshot off the Qt UI thread."""
        if not self.canRunDryRun:
            self._build_outcome = "FAIL"
            self._build_status_text = "Dry run unavailable"
            self._build_progress = 0.0
            self._build_log_text = ""
            self._build_error = (
                "Select valid source/output folders, wait for scanning, "
                "and ensure an ISO backend is available."
            )
            self._last_execution_output = ""
            self.executionChanged.emit()
            return

        request = self._snapshot_build_request()
        backends = list(self._backends)
        self._execution_generation += 1
        generation = self._execution_generation
        self._is_dry_running = True
        self._execution_mode = "DRY RUN"
        self._build_outcome = "RUNNING"
        self._build_status_text = "Preparing dry-run plan..."
        self._build_progress = 0.12
        self._build_progress_indeterminate = False
        self._build_log_text = ""
        self._build_error = ""
        self._last_execution_output = ""
        self._build_hash_path = ""
        self._build_warning_pending = False
        self._build_warning_text = ""
        self._build_warning_context = None
        self.executionChanged.emit()
        self.availabilityChanged.emit()

        worker = threading.Thread(
            target=self._dry_run_worker,
            args=(generation, request, backends),
            name=f"qt-dry-run-{generation}",
            daemon=True,
        )
        worker.start()

    def _dry_run_worker(
        self,
        generation: int,
        request: BuildRequest,
        backends: list[Backend],
    ) -> None:
        plan = None
        logs: list[str] = []
        try:
            plan = self._planner(request, backends)
            if not plan.options.dry_run:
                raise RuntimeError("Qt dry-run request produced a non-dry-run plan.")
            self._dryRunProgress.emit(
                generation,
                "Executing safe dry run...",
                0.62,
            )
            result = self._executor(plan, logs.append)
            self._dryRunFinished.emit(generation, result, "", logs)
        except Exception as exc:
            self._dryRunFinished.emit(generation, None, str(exc), logs)
        finally:
            if isinstance(plan, BuildPlan):
                try:
                    self._command_cleanup(plan.command)
                except Exception:
                    pass

    @Slot(int, str, float)
    def _apply_dry_run_progress(
        self,
        generation: int,
        status_text: str,
        progress: float,
    ) -> None:
        if generation != self._execution_generation or not self._is_dry_running:
            return
        self._build_status_text = status_text
        self._build_progress = min(1.0, max(0.0, progress))
        self.executionChanged.emit()

    @Slot(int, object, str, object)
    def _apply_dry_run_result(
        self,
        generation: int,
        result: object,
        error: str,
        logs: object,
    ) -> None:
        if generation != self._execution_generation:
            return

        self._is_dry_running = False
        log_lines = [str(line) for line in logs] if isinstance(logs, list) else []
        self._build_log_text = "\n".join(log_lines)
        if error:
            self._build_outcome = "FAIL"
            self._build_status_text = "Dry run failed"
            self._build_progress = 0.0
            self._build_error = error
            self._last_execution_output = ""
        elif isinstance(result, BuildExecutionResult):
            self._build_outcome = result.outcome
            self._last_execution_output = str(result.output_iso)
            self._build_error = result.error or ""
            if result.outcome == "DRY RUN":
                self._build_status_text = "Dry run complete"
                self._build_progress = 1.0
            else:
                self._build_status_text = f"Dry run {result.outcome.lower()}"
                self._build_progress = 0.0
        else:
            self._build_outcome = "FAIL"
            self._build_status_text = "Dry run failed"
            self._build_progress = 0.0
            self._build_error = "Dry-run execution returned an invalid result."
            self._last_execution_output = ""

        self.executionChanged.emit()
        self.availabilityChanged.emit()

    @Slot()
    def startBuild(self) -> None:
        """Start one verified, non-dry transactional build off the Qt UI thread."""
        if not self.canStartBuild:
            self._execution_mode = "BUILD"
            self._build_outcome = "FAIL"
            self._build_status_text = "Build unavailable"
            self._build_progress = 0.0
            self._build_progress_indeterminate = False
            self._build_log_text = ""
            self._build_error = (
                "Select valid source/output folders, wait for scanning, "
                "and ensure an ISO backend is available."
            )
            self._last_execution_output = ""
            self._build_hash_path = ""
            self.executionChanged.emit()
            return

        request = self._snapshot_build_request(dry_run=False)
        backends = list(self._backends)
        cancellation = BuildCancellation()
        self._build_cancellation = cancellation
        self._execution_generation += 1
        generation = self._execution_generation
        self._execution_mode = "BUILD"
        self._is_build_running = True
        self._build_outcome = "RUNNING"
        self._build_status_text = "Preparing build plan..."
        self._build_progress = 0.08
        self._build_progress_indeterminate = False
        self._build_log_text = ""
        self._build_error = ""
        self._last_execution_output = ""
        self._build_hash_path = ""
        self._build_warning_pending = False
        self._build_warning_text = ""
        self._build_warning_context = None
        self.executionChanged.emit()
        self.availabilityChanged.emit()

        worker = threading.Thread(
            target=self._build_worker,
            args=(generation, request, backends, cancellation),
            name=f"qt-real-build-{generation}",
            daemon=True,
        )
        worker.start()

    def _build_worker(
        self,
        generation: int,
        request: BuildRequest,
        backends: list[Backend],
        cancellation: BuildCancellation,
    ) -> None:
        plan = None
        logs: list[str] = []

        def emit_log(message: str) -> None:
            text = str(message)
            logs.append(text)
            self._buildLog.emit(generation, text)
            status, progress, indeterminate = self._progress_from_log(text)
            if status:
                self._buildProgress.emit(
                    generation,
                    status,
                    progress,
                    indeterminate,
                )

        try:
            plan = self._planner(request, backends)
            if plan.options.dry_run:
                raise RuntimeError("Qt real build produced a dry-run plan.")
            if plan.scan.warnings:
                decision_event = threading.Event()
                decision = {"approved": False}
                self._buildWarningRequested.emit(
                    generation,
                    list(plan.scan.warnings),
                    decision_event,
                    decision,
                )
                while not decision_event.wait(0.05):
                    if cancellation.is_cancelled():
                        decision_event.set()
                if not decision["approved"]:
                    emit_log("Build cancelled after scan warning review.")
                    result = BuildExecutionResult(
                        outcome="CANCELLED",
                        output_iso=plan.output_iso,
                        error="Build cancelled after scan warning review.",
                    )
                    self._buildFinished.emit(generation, result, "", logs)
                    return
            self._buildProgress.emit(
                generation,
                "Starting ISO backend...",
                0.18,
                True,
            )
            result = self._executor(plan, emit_log, cancellation)
            self._buildFinished.emit(generation, result, "", logs)
        except Exception as exc:
            self._buildFinished.emit(generation, None, str(exc), logs)
        finally:
            if isinstance(plan, BuildPlan):
                try:
                    self._command_cleanup(plan.command)
                except Exception:
                    pass

    @Slot(int, object, object, object)
    def _apply_build_warning_request(
        self,
        generation: int,
        warnings: object,
        decision_event: object,
        decision: object,
    ) -> None:
        if (
            generation != self._execution_generation
            or not self._is_build_running
            or not isinstance(decision_event, threading.Event)
            or not isinstance(decision, dict)
        ):
            if isinstance(decision_event, threading.Event):
                decision_event.set()
            return
        cancellation = self._build_cancellation
        if cancellation is not None and cancellation.is_cancelled():
            decision_event.set()
            return

        warning_lines = [str(item) for item in warnings] if isinstance(warnings, list) else []
        shown = warning_lines[:8]
        if len(warning_lines) > 8:
            shown.append(f"...and {len(warning_lines) - 8} more")
        self._build_warning_text = "\n".join(f"• {line}" for line in shown)
        self._build_warning_pending = True
        self._build_warning_context = (decision_event, decision)
        self._build_status_text = "Review scan warnings"
        self._build_progress = 0.15
        self._build_progress_indeterminate = False
        self.executionChanged.emit()

    @Slot()
    def continueBuildAfterWarnings(self) -> None:
        context = self._build_warning_context
        if not self._build_warning_pending or context is None:
            return
        decision_event, decision = context
        decision["approved"] = True
        self._build_warning_pending = False
        self._build_warning_context = None
        self._build_status_text = "Starting ISO backend..."
        self._build_progress_indeterminate = True
        self.executionChanged.emit()
        decision_event.set()

    @Slot()
    def rejectBuildWarnings(self) -> None:
        context = self._build_warning_context
        if context is None:
            return
        decision_event, decision = context
        decision["approved"] = False
        self._build_warning_pending = False
        self._build_warning_context = None
        if self._build_cancellation is not None:
            self._build_cancellation.cancel()
        self._build_status_text = "Cancelling build..."
        self._build_progress_indeterminate = True
        self.executionChanged.emit()
        decision_event.set()

    @staticmethod
    def _progress_from_log(message: str) -> tuple[str, float, bool]:
        percent_match = re.search(
            r"(?<!\d)(100|\d{1,2})(?:\.\d+)?\s*%",
            message,
        )
        if percent_match:
            percent = int(percent_match.group(1))
            return "Creating ISO...", percent / 100.0, False
        if message == "Build started":
            return "Build started", 0.20, False
        if message.startswith("Storage preflight:"):
            return "Storage verified", 0.24, False
        if message == "Transactional execution command:":
            return "Creating ISO...", 0.28, True
        if message.startswith("ISO created:"):
            return "ISO created", 0.88, False
        if message == "Generating SHA256...":
            return "Generating SHA256...", 0.92, True
        if message.startswith("Hash saved:"):
            return "SHA256 saved", 0.98, False
        return "", 0.0, False

    @Slot(int, str, float, bool)
    def _apply_build_progress(
        self,
        generation: int,
        status_text: str,
        progress: float,
        indeterminate: bool,
    ) -> None:
        if generation != self._execution_generation or not self._is_build_running:
            return
        self._build_status_text = status_text
        self._build_progress = min(1.0, max(0.0, progress))
        self._build_progress_indeterminate = indeterminate
        self.executionChanged.emit()

    @Slot(int, str)
    def _apply_build_log(self, generation: int, message: str) -> None:
        if generation != self._execution_generation:
            return
        if self._build_log_text:
            self._build_log_text += "\n"
        self._build_log_text += message
        self.executionChanged.emit()

    @Slot(int, object, str, object)
    def _apply_build_result(
        self,
        generation: int,
        result: object,
        error: str,
        logs: object,
    ) -> None:
        if generation != self._execution_generation:
            return

        cancellation = self._build_cancellation
        self._is_build_running = False
        self._build_cancellation = None
        self._build_progress_indeterminate = False
        self._build_warning_pending = False
        self._build_warning_text = ""
        self._build_warning_context = None
        log_lines = [str(line) for line in logs] if isinstance(logs, list) else []
        self._build_log_text = "\n".join(log_lines)
        if (
            cancellation is not None
            and cancellation.is_cancelled()
            and "Cancellation requested by user." not in self._build_log_text
        ):
            if self._build_log_text:
                self._build_log_text += "\n"
            self._build_log_text += "Cancellation requested by user."

        if error:
            cancelled = cancellation is not None and cancellation.is_cancelled()
            self._build_outcome = "CANCELLED" if cancelled else "FAIL"
            self._build_status_text = (
                "Build cancelled" if cancelled else "Build failed"
            )
            self._build_progress = 0.0
            self._build_error = (
                "Build cancelled by user." if cancelled else error
            )
            self._last_execution_output = ""
            self._build_hash_path = ""
        elif isinstance(result, BuildExecutionResult):
            self._build_outcome = result.outcome
            self._last_execution_output = str(result.output_iso)
            self._build_hash_path = (
                str(result.hash_path) if result.hash_path is not None else ""
            )
            self._build_error = result.error or ""
            if result.outcome == "PASS":
                self._build_status_text = "Build complete"
                self._build_progress = 1.0
            elif result.outcome == "CANCELLED":
                self._build_status_text = "Build cancelled"
                self._build_progress = 0.0
            else:
                self._build_status_text = "Build failed"
                self._build_progress = 0.0
        else:
            self._build_outcome = "FAIL"
            self._build_status_text = "Build failed"
            self._build_progress = 0.0
            self._build_error = "Build execution returned an invalid result."
            self._last_execution_output = ""
            self._build_hash_path = ""

        self.executionChanged.emit()
        self.availabilityChanged.emit()
        if self._close_requested:
            self.safeToClose.emit()

    @Slot()
    def cancelBuild(self) -> None:
        if not self._is_build_running or self._build_cancellation is None:
            return
        self._build_cancellation.cancel()
        context = self._build_warning_context
        if context is not None:
            decision_event, decision = context
            decision["approved"] = False
            self._build_warning_pending = False
            self._build_warning_context = None
            decision_event.set()
        self._build_status_text = "Cancelling build..."
        self._build_progress_indeterminate = True
        if self._build_log_text:
            self._build_log_text += "\n"
        self._build_log_text += "Cancellation requested by user."
        self.executionChanged.emit()
        QTimer.singleShot(3000, self._force_cancel_if_running)

    @Slot()
    def requestCloseAfterCancel(self) -> None:
        if not self._is_build_running:
            self.safeToClose.emit()
            return
        self._close_requested = True
        self.cancelBuild()

    @Slot()
    def _force_cancel_if_running(self) -> None:
        if self._is_build_running and self._build_cancellation is not None:
            self._build_cancellation.cancel(force=True)

    @Slot()
    def refreshBackends(self) -> None:
        """Refresh the read-only backend snapshot shown by the QML shell."""
        if self._is_dry_running or self._is_build_running:
            return
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
