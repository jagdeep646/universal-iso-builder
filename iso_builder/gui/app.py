#!/usr/bin/env python3
"""
Universal ISO Builder - Safe setup folder to ISO creator

Goal:
- Build a non-bootable ISO from any setup/software folder without modifying source files.
- Use the best local ISO backend available for speed and compatibility.
- Fall back between installed tools where possible.
- Use only Python standard library for the GUI and orchestration.

Important:
- Python standard library does NOT include a reliable UDF/ISO writer.
- Actual ISO creation uses the best local backend available:
  Windows: oscdimg.exe from Windows ADK (recommended)
  Windows fallback: built-in PowerShell + IMAPI COM
  macOS: hdiutil (built-in)
  Linux/macOS/Windows if installed: xorriso / genisoimage / mkisofs

This app does NOT bypass antivirus and does NOT modify, hide, encrypt, or pack executables.
"""

from __future__ import annotations

# Tkinter application module.

import queue
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from iso_builder.backends import (
    detect_backends,
    find_windows_powershell,
    select_backend,
    select_requested_backend,
)
from iso_builder.backends.commands import (
    build_command,
    build_hdiutil_command,
    build_mkisofs_compatible_command,
    build_oscdimg_command,
    build_powershell_imapi_command,
    build_xorriso_command,
)
from iso_builder.backends.imapi import (
    cleanup_temp_script_from_command,
    make_windows_imapi_script,
)
from iso_builder.constants import (
    APP_NAME,
    APP_VERSION,
    PROFILE_AUTO,
    PROFILE_LEGACY,
    PROFILE_MODERN,
    PROFILE_UDF_ONLY,
    PROFILES,
    WINDOWS_OSCDIMG_PATHS,
    WINDOWS_POWERSHELL_PATHS,
)
from iso_builder.cancellation import BuildCancellation
from iso_builder.models import (
    Backend,
    BuildExecutionResult,
    BuildOptions,
    BuildPlan,
    BuildRequest,
    ScanResult,
    UIEvent,
)
from iso_builder.execution import calculate_sha256, execute_build_plan, run_process
from iso_builder.naming import (
    auto_names_from_source,
    clean_volume_label,
    normalize_iso_name,
    resolve_build_paths,
    safe_path_component,
)
from iso_builder.scanning import is_hidden_path, scan_source_folder
from iso_builder.planner import prepare_build_plan
from iso_builder.utils import human_size, quote_cmd


class IsoBuilderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1180x820")
        self.minsize(1040, 720)

        self.ui_queue: "queue.Queue[UIEvent]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.active_operation: Optional[str] = None
        self.build_cancellation: Optional[BuildCancellation] = None
        self.close_requested = False
        self.close_force_deadline: Optional[float] = None
        self.detected_backends: List[Backend] = []
        self.protocol("WM_DELETE_WINDOW", self._on_close_requested)

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.iso_name_var = tk.StringVar(value="Software_Setup.iso")
        self.label_var = tk.StringVar(value="SOFTWARE_SETUP")
        self.profile_var = tk.StringVar(value=PROFILE_AUTO)
        self.backend_var = tk.StringVar(value="Auto")
        self.include_hidden_var = tk.BooleanVar(value=True)
        self.hash_var = tk.BooleanVar(value=True)
        self.optimize_var = tk.BooleanVar(value=False)
        self.auto_package_var = tk.BooleanVar(value=True)
        self.auto_package_text_var = tk.StringVar(value="Auto name + package folder: ON")
        self.dry_run_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="Select a source folder to begin")

        self._configure_styles()
        self._build_ui()
        self.refresh_backends()
        self.after(150, self._process_ui_queue)

    def _configure_styles(self) -> None:
        self.colors = {
            "bg": "#0f172a",
            "surface": "#111827",
            "surface_2": "#162033",
            "card": "#182233",
            "card_2": "#1f2937",
            "border": "#2b3648",
            "text": "#e5e7eb",
            "muted": "#94a3b8",
            "accent": "#22c55e",
            "accent_2": "#38bdf8",
            "warning": "#f59e0b",
            "danger": "#ef4444",
        }

        self.configure(bg=self.colors["bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("App.TFrame", background=self.colors["bg"])
        style.configure("Surface.TFrame", background=self.colors["surface"])
        style.configure("Card.TFrame", background=self.colors["card"], relief="flat")
        style.configure("Inner.TFrame", background=self.colors["card_2"], relief="flat")
        style.configure("Header.TFrame", background=self.colors["surface"])
        style.configure("Status.TFrame", background=self.colors["surface_2"])

        style.configure("Title.TLabel", background=self.colors["surface"], foreground=self.colors["text"], font=("Segoe UI", 24, "bold"))
        style.configure("Subtitle.TLabel", background=self.colors["surface"], foreground=self.colors["muted"], font=("Segoe UI", 10))
        style.configure("SectionTitle.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 12, "bold"))
        style.configure("Body.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.colors["card"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("Badge.TLabel", background=self.colors["surface_2"], foreground=self.colors["accent_2"], font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("PillGood.TLabel", background="#0b2a1b", foreground="#86efac", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("PillInfo.TLabel", background="#082f49", foreground="#7dd3fc", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("PillWarn.TLabel", background="#3a2405", foreground="#fcd34d", font=("Segoe UI", 9, "bold"), padding=(10, 4))

        style.configure("Section.TLabelframe", background=self.colors["card"], borderwidth=1, relief="solid", bordercolor=self.colors["border"])
        style.configure("Section.TLabelframe.Label", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 11, "bold"))

        style.configure("App.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("StatusLabel.TLabel", background=self.colors["surface_2"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"))
        style.configure("StatusHint.TLabel", background=self.colors["surface_2"], foreground=self.colors["muted"], font=("Segoe UI", 9))

        style.configure("App.TButton", font=("Segoe UI", 10), padding=(14, 10), background=self.colors["card_2"], foreground=self.colors["text"], borderwidth=0)
        style.map("App.TButton", background=[("active", "#273447")])
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 11), background="#16a34a", foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#15803d")])

        style.configure("App.TCheckbutton", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 9))
        style.map("App.TCheckbutton", background=[("active", self.colors["card"])], foreground=[("disabled", self.colors["muted"])])

        style.configure("App.TEntry", fieldbackground="#0b1220", background="#0b1220", foreground=self.colors["text"], insertcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], padding=8)
        style.map(
            "App.TEntry",
            fieldbackground=[("!disabled", "#0b1220")],
            foreground=[("!disabled", self.colors["text"])],
        )

        style.configure("App.TCombobox", fieldbackground="#0b1220", background="#0b1220", foreground=self.colors["text"], arrowcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], padding=6)
        style.map(
            "App.TCombobox",
            fieldbackground=[("readonly", "#0b1220"), ("!disabled", "#0b1220")],
            foreground=[("readonly", self.colors["text"]), ("!disabled", self.colors["text"])],
            selectbackground=[("readonly", "#0b1220")],
            selectforeground=[("readonly", self.colors["text"])],
            background=[("readonly", "#0b1220"), ("active", "#0b1220")],
            arrowcolor=[("readonly", self.colors["text"]), ("active", self.colors["text"])],
        )

        style.configure("Vertical.TScrollbar", background=self.colors["card_2"], troughcolor="#0b1220", bordercolor=self.colors["border"], arrowcolor=self.colors["text"])

        self.option_add("*TCombobox*Listbox.background", "#0b1220")
        self.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", "#1d4ed8")
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        header = ttk.Frame(outer, style="Header.TFrame", padding=18)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        logo_wrap = tk.Frame(header, bg=self.colors["surface"], highlightthickness=0)
        logo_wrap.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))
        logo = tk.Canvas(logo_wrap, width=68, height=68, bg=self.colors["surface"], highlightthickness=0, bd=0)
        logo.pack()
        self._draw_logo(logo)

        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(
            header,
            text="Modern folder-to-ISO builder with backend auto-detect, compatibility fallback, and clean package output.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))

        badge_bar = ttk.Frame(header, style="Header.TFrame")
        badge_bar.grid(row=0, column=2, rowspan=2, sticky="e")
        ttk.Label(badge_bar, text="SAFE PACKAGING", style="PillGood.TLabel").pack(side="left", padx=(0, 8))
        ttk.Label(badge_bar, text="AUTO BACKEND", style="PillInfo.TLabel").pack(side="left", padx=(0, 8))
        ttk.Label(badge_bar, text="SHA256 READY", style="PillWarn.TLabel").pack(side="left")

        summary = ttk.Frame(outer, style="Status.TFrame", padding=(14, 10))
        summary.grid(row=1, column=0, sticky="ew", pady=(14, 14))
        summary.columnconfigure(0, weight=1)
        ttk.Label(summary, textvariable=self.status_var, style="StatusLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.summary_var, style="StatusHint.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        body = ttk.Frame(outer, style="App.TFrame")
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="App.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(body, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        # Input / Output card
        form = ttk.LabelFrame(left, text="Input / Output", style="Section.TLabelframe", padding=14)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        self._add_labeled_row(form, 0, "Source folder", self.source_var, self.pick_source, "Browse")
        self._add_labeled_row(form, 1, "Output folder", self.output_var, self.pick_output, "Browse")
        self._add_labeled_row(form, 2, "ISO file name", self.iso_name_var)
        self._add_labeled_row(form, 3, "Volume label", self.label_var)

        # Settings card
        settings = ttk.LabelFrame(left, text="ISO Settings", style="Section.TLabelframe", padding=14)
        settings.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text="Compatibility profile", style="App.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Combobox(settings, textvariable=self.profile_var, values=PROFILES, state="readonly", style="App.TCombobox").grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(settings, text="Backend", style="App.TLabel").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=6)
        self.backend_combo = ttk.Combobox(settings, textvariable=self.backend_var, values=["Auto"], state="readonly", style="App.TCombobox")
        self.backend_combo.grid(row=0, column=3, sticky="ew", pady=6)

        checks_frame = ttk.Frame(settings, style="Card.TFrame")
        checks_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        checks_frame.columnconfigure(0, weight=1)
        checks_frame.columnconfigure(1, weight=1)

        left_checks = ttk.Frame(checks_frame, style="Card.TFrame")
        left_checks.grid(row=0, column=0, sticky="w")
        right_checks = ttk.Frame(checks_frame, style="Card.TFrame")
        right_checks.grid(row=0, column=1, sticky="w")

        ttk.Checkbutton(left_checks, text="Include hidden files", variable=self.include_hidden_var, style="App.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(left_checks, text="Generate SHA256 hash", variable=self.hash_var, style="App.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(
            right_checks,
            textvariable=self.auto_package_text_var,
            variable=self.auto_package_var,
            command=self._on_auto_package_changed,
            style="App.TCheckbutton",
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(right_checks, text="Optimize duplicate files (when supported)", variable=self.optimize_var, style="App.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(right_checks, text="Dry run only", variable=self.dry_run_var, style="App.TCheckbutton").pack(anchor="w", pady=2)

        # Quick action card
        actions = ttk.LabelFrame(right, text="Quick Actions", style="Section.TLabelframe", padding=14)
        actions.grid(row=0, column=0, sticky="ew")
        actions.columnconfigure((0,1), weight=1)
        ttk.Button(actions, text="Refresh Backends", style="App.TButton", command=self.refresh_backends).grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=6)
        ttk.Button(actions, text="Scan Folder", style="App.TButton", command=self.scan_only).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(actions, text="Show Command", style="App.TButton", command=self.show_command).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=6)
        ttk.Button(actions, text="Clear Logs", style="App.TButton", command=self.clear_logs).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(actions, text="Build ISO", style="Primary.TButton", command=self.start_build).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        info = ttk.LabelFrame(right, text="Best Practice", style="Section.TLabelframe", padding=14)
        info.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        info.columnconfigure(0, weight=1)
        ttk.Label(info, text="• Source folder ko original state me rakha jata hai.", style="Body.TLabel").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Auto mode source folder ke name se ISO aur label banata hai.", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Package folder me ISO + SHA256 hash dono save hote hain.", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Windows par oscdimg best backend hai; PowerShell IMAPI fallback available hai.", style="Body.TLabel").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Label(info, text="• Ye app non-bootable data ISO banata hai.", style="Body.TLabel").grid(row=4, column=0, sticky="w", pady=2)

        tips = ttk.Frame(right, style="Card.TFrame", padding=(2, 12, 2, 0))
        tips.grid(row=2, column=0, sticky="ew")
        ttk.Label(tips, text="UI refreshed with a modern layout and custom in-app branding.", style="Muted.TLabel").pack(anchor="w")

        log_frame = ttk.LabelFrame(outer, text="Logs", style="Section.TLabelframe", padding=12)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            height=18,
            font=("Cascadia Mono", 10),
            bg="#0b1220",
            fg="#dbeafe",
            insertbackground="#dbeafe",
            selectbackground="#1d4ed8",
            selectforeground="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        footer = ttk.Frame(outer, style="App.TFrame", padding=(2, 10, 2, 0))
        footer.grid(row=4, column=0, sticky="ew")
        ttk.Label(
            footer,
            text="Note: This app creates non-bootable data ISOs. It does not bypass antivirus or run installers.",
            style="Muted.TLabel",
        ).pack(anchor="w")

    def _draw_logo(self, canvas: tk.Canvas) -> None:
        canvas.create_oval(6, 6, 62, 62, fill="#0b1220", outline="#2b3648", width=2)
        canvas.create_arc(12, 12, 56, 56, start=30, extent=280, style="arc", outline="#38bdf8", width=5)
        canvas.create_oval(22, 22, 46, 46, fill="#16a34a", outline="")
        canvas.create_rectangle(32, 15, 36, 53, fill="#e5e7eb", outline="")
        canvas.create_rectangle(20, 31, 48, 35, fill="#e5e7eb", outline="")
        canvas.create_text(34, 58, text="ISO", fill="#94a3b8", font=("Segoe UI", 8, "bold"))

    def _add_labeled_row(self, parent: ttk.LabelFrame, row: int, label: str, var: tk.StringVar, command: Optional[Callable[[], None]] = None, button_text: str = "") -> None:
        ttk.Label(parent, text=label, style="App.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(parent, textvariable=var, style="App.TEntry").grid(row=row, column=1, sticky="ew", pady=6)
        if command:
            ttk.Button(parent, text=button_text or "Browse", style="App.TButton", command=command).grid(row=row, column=2, padx=(8, 0), pady=6)

    def _set_status(self, title: str, hint: str = "") -> None:
        self.status_var.set(title)
        if hint:
            self.summary_var.set(hint)

    def _on_auto_package_changed(self) -> None:
        enabled = bool(self.auto_package_var.get())
        state = "ON" if enabled else "OFF"
        self.auto_package_text_var.set(f"Auto name + package folder: {state}")
        self.log(f"Auto package changed: {state}")
        if enabled:
            self._set_status(
                "Auto package enabled",
                "Source name will control the package folder, ISO name, and volume label",
            )
        else:
            self._set_status(
                "Manual naming enabled",
                "ISO file name and volume label fields will be used without auto naming",
            )

    def pick_source(self) -> None:
        folder = filedialog.askdirectory(title="Select source setup folder")
        if folder:
            source = Path(folder)
            self.source_var.set(folder)
            if not self.output_var.get().strip():
                self.output_var.set(str(source.parent))
            if self.auto_package_var.get():
                safe_base, iso_name, label = auto_names_from_source(source)
                self.iso_name_var.set(iso_name)
                self.label_var.set(label)
                self.log(f"Auto naming set from source: {safe_base}")
                self.log(f"Package folder will be: {safe_base}_ISO")
            self._set_status("Source selected", f"Ready to package: {source.name}")
            self.log(f"Source selected: {folder}")

    def pick_output(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_var.set(folder)
            self._set_status("Output folder selected", folder)
            self.log(f"Output selected: {folder}")

    def log(self, msg: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")
        self.update_idletasks()

    def thread_log(self, msg: str) -> None:
        self.ui_queue.put(UIEvent(kind="log", message=msg))

    def thread_status(self, title: str, hint: str = "") -> None:
        self.ui_queue.put(UIEvent(kind="status", message=title, detail=hint))

    def thread_operation_finished(self, operation: str) -> None:
        self.ui_queue.put(UIEvent(kind="operation_finished", message=operation))

    def _operation_is_active(self) -> bool:
        if self.active_operation is not None:
            return True
        return self.worker is not None and self.worker.is_alive()

    def _begin_operation(self, operation: str) -> bool:
        if getattr(self, "close_requested", False):
            return False
        if self._operation_is_active():
            return False
        self.active_operation = operation
        return True

    def _finish_operation(self, operation: str) -> None:
        if self.active_operation == operation:
            self.active_operation = None
            if operation == "build":
                self.build_cancellation = None

    def _on_close_requested(self) -> None:
        if self.close_requested:
            return
        if self.active_operation != "build":
            self.destroy()
            return

        proceed = messagebox.askyesno(
            "Build in progress",
            "ISO build abhi running hai. Build cancel karke app safely close karein?",
        )
        if not proceed:
            return

        self.close_requested = True
        self.close_force_deadline = time.monotonic() + 3.0
        if self.build_cancellation is None:
            self.build_cancellation = BuildCancellation()
        self.build_cancellation.cancel()
        self._set_status(
            "Cancelling build...",
            "Waiting for backend to stop safely",
        )
        self.log("Close requested: active build cancellation started.")
        self.after(50, self._wait_for_build_close)

    def _wait_for_build_close(self) -> None:
        if not self.close_requested:
            return

        worker_alive = self.worker is not None and self.worker.is_alive()
        if self.active_operation is None and not worker_alive:
            self.destroy()
            return

        cancellation = self.build_cancellation
        force = (
            self.close_force_deadline is not None
            and time.monotonic() >= self.close_force_deadline
        )
        if cancellation is not None:
            cancellation.cancel(force=force)
        self.after(100, self._wait_for_build_close)

    def _process_ui_queue(self) -> None:
        try:
            while True:
                event = self.ui_queue.get_nowait()
                if event.kind == "log":
                    self.log(event.message)
                elif event.kind == "status":
                    self._set_status(event.message, event.detail)
                elif event.kind == "scan_complete":
                    if isinstance(event.payload, ScanResult):
                        self._handle_scan_complete(event.payload)
                    else:
                        self._handle_operation_error("scan", "Invalid scan result received.")
                elif event.kind == "plan_complete":
                    if isinstance(event.payload, BuildPlan):
                        self._handle_plan_complete(event.message, event.payload)
                    else:
                        self._handle_operation_error(event.message, "Invalid build plan received.")
                elif event.kind == "operation_error":
                    self._handle_operation_error(event.message, event.detail)
                elif event.kind == "operation_finished":
                    self._finish_operation(event.message)
        except queue.Empty:
            pass
        self.after(150, self._process_ui_queue)

    def _handle_scan_complete(self, scan: ScanResult) -> None:
        self._set_status("Scan complete", f"{scan.files} files | {human_size(scan.total_bytes)} total size")
        self.print_scan(scan)

    def _handle_plan_complete(self, operation: str, plan: BuildPlan) -> None:
        if operation == "build" and getattr(self, "close_requested", False):
            cleanup_temp_script_from_command(plan.command)
            self._finish_operation("build")
            self.log("Build cancelled before backend execution.")
            return

        if plan.options.auto_package:
            self.iso_name_var.set(plan.output_iso.name)
            self.label_var.set(plan.label)

        if operation == "command":
            try:
                self._display_prepared_command(plan)
            finally:
                cleanup_temp_script_from_command(plan.command)
        elif operation == "build":
            self._handle_build_plan_ready(plan)
        else:
            self._handle_operation_error(operation, "Unknown plan operation.")

    def _display_prepared_command(self, plan: BuildPlan) -> None:
        self._set_status("Command prepared", f"Backend: {plan.backend.name} | Output: {plan.output_iso.name}")
        self.log("Prepared command:")
        self.log(f"  Backend: {plan.backend.name} ({plan.backend.description})")
        self.log(f"  Source: {plan.source}")
        self.log(f"  Output: {plan.output_iso}")
        self.log(f"  Output package folder: {plan.output_iso.parent}")
        self.log(f"  Label: {plan.label}")
        self.log(f"  Profile: {plan.options.profile}")
        self.log(f"  Auto package: {'ON' if plan.options.auto_package else 'OFF'}")
        self.log(quote_cmd(plan.command))
        self.print_scan(plan.scan)
        for warning in plan.warnings:
            self.log(f"Command warning: {warning}")

    def _handle_build_plan_ready(self, plan: BuildPlan) -> None:
        if plan.scan.warnings:
            warn_text = "\n".join(f"- {warning}" for warning in plan.scan.warnings[:8])
            if len(plan.scan.warnings) > 8:
                warn_text += f"\n- ...and {len(plan.scan.warnings) - 8} more"
            proceed = messagebox.askyesno(
                "Warnings Found",
                f"Scan warnings mile:\n\n{warn_text}\n\nContinue?",
            )
            if not proceed:
                cleanup_temp_script_from_command(plan.command)
                self._finish_operation("build")
                self._set_status("Build cancelled", "User cancelled after reviewing scan warnings")
                self.log("Build cancelled by user after warnings.")
                return

        try:
            self._set_status("Building ISO...", f"Source: {plan.source.name}")
            self.worker = threading.Thread(
                target=self._build_worker,
                args=(plan,),
                daemon=True,
            )
            self.worker.start()
        except Exception as error:
            cleanup_temp_script_from_command(plan.command)
            self._finish_operation("build")
            self._handle_operation_error("build", str(error))

    def _handle_operation_error(self, operation: str, error: str) -> None:
        if operation == "build" and getattr(self, "close_requested", False):
            self._set_status("Build cancelled", error)
            self.log(f"Build stopped while closing: {error}")
            return

        if operation == "scan":
            messagebox.showerror("Scan Error", error)
            self._set_status("Scan failed", error)
        elif operation == "command":
            messagebox.showerror("Command Error", error)
            self._set_status("Command failed", error)
        elif operation == "build":
            messagebox.showerror("Build Error", error)
            self._set_status("Build cannot start", error)
        else:
            messagebox.showerror("Operation Error", error)
            self._set_status("Operation failed", error)
        self.log(f"ERROR: {error}")

    def clear_logs(self) -> None:
        self.log_text.delete("1.0", "end")
        self._set_status("Logs cleared", self.summary_var.get())

    def refresh_backends(self) -> None:
        self.detected_backends = detect_backends()
        values = ["Auto"] + [f"{b.name} | {b.executable}" for b in self.detected_backends]
        self.backend_combo.configure(values=values)
        self.backend_var.set("Auto")
        self.log("Backend scan complete.")
        if not self.detected_backends:
            self._set_status("No backend detected", "Install Windows ADK oscdimg or use the built-in fallback where available")
            self.log("WARNING: Koi ISO backend nahi mila.")
            self.log("Windows: oscdimg best hai; PowerShell IMAPI fallback bhi auto-detect hona chahiye.")
            self.log("Agar PowerShell bhi detect nahi ho raha, Windows PATH/system issue hai.")
            self.log("macOS: hdiutil usually built-in hota hai. Linux: xorriso/genisoimage install karo.")
            self.log("Python standard library alone reliable UDF/ISO image create nahi karti.")
        else:
            self._set_status("Backends detected", f"{len(self.detected_backends)} backend(s) available. Auto mode best option choose karega.")
            for b in self.detected_backends:
                self.log(f"Found: {b.name} -> {b.executable} ({b.description})")

    def snapshot_build_options(self) -> BuildOptions:
        return BuildOptions(
            profile=self.profile_var.get(),
            include_hidden=bool(self.include_hidden_var.get()),
            generate_hash=bool(self.hash_var.get()),
            optimize_duplicates=bool(self.optimize_var.get()),
            auto_package=bool(self.auto_package_var.get()),
            dry_run=bool(self.dry_run_var.get()),
        )

    def snapshot_build_request(self) -> BuildRequest:
        return BuildRequest(
            source_text=self.source_var.get(),
            output_text=self.output_var.get(),
            iso_name_text=self.iso_name_var.get(),
            label_text=self.label_var.get(),
            backend_choice=self.backend_var.get(),
            options=self.snapshot_build_options(),
        )

    def get_selected_backend(self, profile: Optional[str] = None) -> Backend:
        if profile is None:
            profile = self.profile_var.get()
        return select_requested_backend(
            backends=self.detected_backends,
            backend_choice=self.backend_var.get(),
            profile=profile,
        )

    def validate_paths(self, auto_package: Optional[bool] = None) -> Tuple[Path, Path, str, str]:
        if auto_package is None:
            auto_package = bool(self.auto_package_var.get())

        source, output_iso, label, iso_name = resolve_build_paths(
            source_text=self.source_var.get(),
            output_text=self.output_var.get(),
            iso_name_text=self.iso_name_var.get(),
            label_text=self.label_var.get(),
            auto_package=auto_package,
        )
        if auto_package:
            self.iso_name_var.set(iso_name)
            self.label_var.set(label)
        return source, output_iso, label, iso_name

    def prepare(self, request: Optional[BuildRequest] = None) -> BuildPlan:
        if request is None:
            request = self.snapshot_build_request()

        plan = prepare_build_plan(request, self.detected_backends)
        if request.options.auto_package:
            self.iso_name_var.set(plan.output_iso.name)
            self.label_var.set(plan.label)
        return plan

    def print_scan(self, scan: ScanResult) -> None:
        self.log("Scan summary:")
        self.log(f"  Files: {scan.files}")
        self.log(f"  Folders: {scan.dirs}")
        self.log(f"  Empty folders: {scan.empty_dirs}")
        self.log(f"  Total size: {human_size(scan.total_bytes)}")
        self.log(f"  Largest file: {human_size(scan.largest_file_bytes)} | {scan.largest_file_path}")
        self.log(f"  Max relative path length: {scan.max_rel_path_len}")
        self.log(f"  Max absolute path length: {scan.max_abs_path_len}")
        self.log(f"  Max single name length: {scan.max_name_len}")
        self.log(f"  Unicode/non-ASCII paths: {scan.non_ascii_names}")
        self.log(f"  Hidden items: {scan.hidden_items}")
        self.log(f"  Symlinks: {scan.symlinks}")
        self.log(f"  Files over 4GB: {scan.files_over_4gb}")
        if scan.warnings:
            self.log("Warnings:")
            for w in scan.warnings:
                self.log(f"  - {w}")
        else:
            self.log("Warnings: none")

    def scan_only(self) -> None:
        if not self._begin_operation("scan"):
            messagebox.showwarning("Busy", "Another operation is already running.")
            return

        try:
            source_text = self.source_var.get().strip()
            if not source_text:
                raise ValueError("Source folder select karo.")

            source = Path(source_text).expanduser()
            if not source.exists() or not source.is_dir():
                raise ValueError("Source folder valid nahi hai.")
            profile = self.profile_var.get()
            include_hidden = bool(self.include_hidden_var.get())

            self._set_status("Scanning folder...", str(source))
            self.worker = threading.Thread(
                target=self._scan_worker,
                args=(source, profile, include_hidden),
                daemon=True,
            )
            self.worker.start()
        except Exception as e:
            self._finish_operation("scan")
            messagebox.showerror("Scan Error", str(e))
            self._set_status("Scan failed", str(e))
            self.log(f"ERROR: {e}")

    def _scan_worker(self, source: Path, profile: str, include_hidden: bool) -> None:
        try:
            scan = scan_source_folder(source, profile, include_hidden)
            self.ui_queue.put(UIEvent(kind="scan_complete", payload=scan))
        except Exception as error:
            self.ui_queue.put(UIEvent(kind="operation_error", message="scan", detail=str(error)))
        finally:
            self.thread_operation_finished("scan")

    def _prepare_worker(
        self,
        operation: str,
        request: BuildRequest,
        backends: List[Backend],
    ) -> None:
        plan_ready = False
        try:
            plan = prepare_build_plan(request, backends)
            self.ui_queue.put(UIEvent(kind="plan_complete", message=operation, payload=plan))
            plan_ready = True
        except Exception as error:
            self.ui_queue.put(UIEvent(kind="operation_error", message=operation, detail=str(error)))
        finally:
            if operation != "build" or not plan_ready:
                self.thread_operation_finished(operation)

    def show_command(self) -> None:
        if not self._begin_operation("command"):
            messagebox.showwarning("Busy", "Another operation is already running.")
            return

        try:
            request = self.snapshot_build_request()
            backends = list(self.detected_backends)
            self._set_status("Preparing command...", "Scanning source folder")
            self.worker = threading.Thread(
                target=self._prepare_worker,
                args=("command", request, backends),
                daemon=True,
            )
            self.worker.start()
        except Exception as e:
            self._finish_operation("command")
            self._handle_operation_error("command", str(e))

    def start_build(self) -> None:
        if not self._begin_operation("build"):
            messagebox.showwarning("Busy", "Another operation is already running.")
            return

        try:
            self.build_cancellation = BuildCancellation()
            request = self.snapshot_build_request()
            backends = list(self.detected_backends)
            self._set_status("Preparing build...", "Scanning source folder")
            self.worker = threading.Thread(
                target=self._prepare_worker,
                args=("build", request, backends),
                daemon=True,
            )
            self.worker.start()
        except Exception as e:
            self._finish_operation("build")
            self._handle_operation_error("build", str(e))

    def _build_worker(
        self,
        plan: BuildPlan,
    ) -> None:
        try:
            self.thread_status("Build started", f"Using backend: {plan.backend.name}")
            result = execute_build_plan(
                plan,
                self.thread_log,
                getattr(self, "build_cancellation", None),
            )

            if result.outcome == "DRY RUN":
                self.thread_status("Dry run finished", f"Output preview: {result.output_iso.name}")
            elif result.outcome == "PASS":
                self.thread_status(
                    "Build finished: PASS",
                    f"Package folder ready: {result.output_iso.parent}",
                )
            elif result.outcome == "CANCELLED":
                self.thread_status(
                    "Build cancelled",
                    "Backend stopped and temporary output cleaned",
                )
            else:
                self.thread_status("Build finished: FAIL", result.error or "Unknown build error")
        finally:
            self.thread_operation_finished("build")


def main() -> None:
    app = IsoBuilderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
