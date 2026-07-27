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
        self.minsize(1040, 720)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = min(1280, max(1040, screen_width - 80))
        window_height = min(860, max(720, screen_height - 120))
        window_x = max(0, (screen_width - window_width) // 2)
        window_y = max(0, (screen_height - window_height) // 2)
        self.geometry(
            f"{window_width}x{window_height}+{window_x}+{window_y}"
        )

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
        self.auto_package_text_var = tk.StringVar(value="Auto package: ON")
        self.dry_run_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="Select a source folder to begin")
        self.source_card_var = tk.StringVar(value="No folder selected")
        self.source_detail_var = tk.StringVar(value="Choose a source folder")
        self.backend_card_var = tk.StringVar(value="Detecting...")
        self.backend_detail_var = tk.StringVar(value="Checking available tools")
        self.profile_card_var = tk.StringVar(value=PROFILE_AUTO)
        self.integrity_card_var = tk.StringVar(value="SHA-256 enabled")
        self.output_card_var = tk.StringVar(value="Output path will appear here")

        self._configure_styles()
        self._build_ui()
        self.profile_var.trace_add("write", self._refresh_dashboard_cards)
        self.backend_var.trace_add("write", self._refresh_dashboard_cards)
        self.hash_var.trace_add("write", self._refresh_dashboard_cards)
        self.refresh_backends()
        self.after(150, self._process_ui_queue)

    def _configure_styles(self) -> None:
        self.colors = {
            "app_bg": "#111936",
            "sidebar": "#252d5b",
            "sidebar_2": "#30396d",
            "sidebar_text": "#f7f7ff",
            "sidebar_muted": "#bdc4df",
            "content": "#eef0f8",
            "surface": "#f7f8fc",
            "surface_2": "#f0f2fa",
            "card": "#fafbfe",
            "card_hover": "#f4f5fb",
            "border": "#d8dceb",
            "shadow": "#d5d8e6",
            "field": "#f4f5fa",
            "text": "#202952",
            "muted": "#68718f",
            "primary": "#6757e8",
            "primary_hover": "#5544d8",
            "primary_pressed": "#4938bd",
            "blue": "#4e88f7",
            "success": "#2fa66f",
            "warning": "#e78525",
            "danger": "#d84b65",
            "focus": "#7567ef",
            "log_bg": "#f7f8fc",
            "log_text": "#303858",
        }

        self.configure(bg=self.colors["app_bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Content.TFrame", background=self.colors["content"])
        style.configure("Card.TFrame", background=self.colors["card"])
        style.configure("Card.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("CardMuted.TLabel", background=self.colors["card"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 12, "bold"))
        style.configure("StatusTitle.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"))
        style.configure("StatusHint.TLabel", background=self.colors["card"], foreground=self.colors["muted"], font=("Segoe UI", 9))

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(12, 9),
            background=self.colors["surface_2"],
            foreground=self.colors["text"],
            borderwidth=1,
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("pressed", self.colors["shadow"]),
                ("active", self.colors["card_hover"]),
            ],
            bordercolor=[("focus", self.colors["focus"])],
        )
        style.configure(
            "Browse.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(15, 9),
            background=self.colors["primary"],
            foreground="white",
            borderwidth=0,
        )
        style.map(
            "Browse.TButton",
            background=[
                ("pressed", self.colors["primary_pressed"]),
                ("active", self.colors["primary_hover"]),
            ],
        )
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 11, "bold"),
            padding=(18, 12),
            background=self.colors["primary"],
            foreground="white",
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("pressed", self.colors["primary_pressed"]),
                ("active", self.colors["blue"]),
            ],
        )
        style.configure(
            "Sidebar.TButton",
            font=("Segoe UI", 10),
            padding=(16, 11),
            anchor="w",
            background=self.colors["sidebar"],
            foreground=self.colors["sidebar_text"],
            borderwidth=0,
        )
        style.map(
            "Sidebar.TButton",
            background=[
                ("pressed", self.colors["primary_pressed"]),
                ("active", self.colors["sidebar_2"]),
            ],
            foreground=[("disabled", self.colors["sidebar_muted"])],
        )
        style.configure(
            "SidebarActive.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 11),
            anchor="w",
            background=self.colors["primary"],
            foreground="white",
            borderwidth=0,
        )
        style.map(
            "SidebarActive.TButton",
            background=[
                ("pressed", self.colors["primary_pressed"]),
                ("active", self.colors["primary_hover"]),
            ],
        )

        style.configure(
            "Soft.TCheckbutton",
            background=self.colors["card"],
            foreground=self.colors["text"],
            font=("Segoe UI", 9),
            indicatorcolor=self.colors["field"],
            indicatorrelief="flat",
            padding=(2, 4),
        )
        style.map(
            "Soft.TCheckbutton",
            background=[("active", self.colors["card"])],
            indicatorcolor=[
                ("selected", self.colors["primary"]),
                ("!selected", self.colors["field"]),
            ],
            foreground=[("disabled", self.colors["muted"])],
        )

        style.configure(
            "Field.TEntry",
            fieldbackground=self.colors["field"],
            background=self.colors["field"],
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=7,
        )
        style.map(
            "Field.TEntry",
            fieldbackground=[("!disabled", self.colors["field"])],
            foreground=[("!disabled", self.colors["text"])],
            bordercolor=[("focus", self.colors["focus"])],
            lightcolor=[("focus", self.colors["focus"])],
            darkcolor=[("focus", self.colors["focus"])],
        )

        style.configure(
            "Field.TCombobox",
            fieldbackground=self.colors["field"],
            background=self.colors["field"],
            foreground=self.colors["text"],
            arrowcolor=self.colors["primary"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=6,
        )
        style.map(
            "Field.TCombobox",
            fieldbackground=[
                ("readonly", self.colors["field"]),
                ("!disabled", self.colors["field"]),
            ],
            foreground=[("readonly", self.colors["text"]), ("!disabled", self.colors["text"])],
            selectbackground=[("readonly", self.colors["field"])],
            selectforeground=[("readonly", self.colors["text"])],
            background=[
                ("readonly", self.colors["field"]),
                ("active", self.colors["surface_2"]),
            ],
            arrowcolor=[
                ("readonly", self.colors["primary"]),
                ("active", self.colors["primary_hover"]),
            ],
            bordercolor=[("focus", self.colors["focus"])],
        )

        style.configure(
            "Glass.Vertical.TScrollbar",
            background=self.colors["shadow"],
            troughcolor=self.colors["surface_2"],
            bordercolor=self.colors["surface_2"],
            arrowcolor=self.colors["muted"],
        )
        style.configure(
            "Glass.Horizontal.TProgressbar",
            background=self.colors["primary"],
            troughcolor=self.colors["surface_2"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["primary"],
            darkcolor=self.colors["blue"],
        )

        self.option_add("*TCombobox*Listbox.background", self.colors["surface"])
        self.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", self.colors["primary"])
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

    def _build_ui(self) -> None:
        shell = tk.Frame(self, bg=self.colors["app_bg"], bd=0)
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        sidebar = tk.Frame(
            shell,
            width=205,
            bg=self.colors["sidebar"],
            highlightthickness=1,
            highlightbackground="#525b8b",
            bd=0,
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        content = tk.Frame(
            shell,
            bg=self.colors["content"],
            highlightthickness=1,
            highlightbackground="#ffffff",
            bd=0,
        )
        content.pack(side="left", fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)

        self._build_sidebar(sidebar)

        header = tk.Frame(content, bg=self.colors["content"], bd=0)
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 10))
        header.columnconfigure(0, weight=1)

        title_area = tk.Frame(header, bg=self.colors["content"], bd=0)
        title_area.grid(row=0, column=0, sticky="nw", pady=(5, 0))
        tk.Label(
            title_area,
            text="Welcome back!",
            bg=self.colors["content"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w")
        tk.Label(
            title_area,
            text="Universal ISO Builder",
            bg=self.colors["content"],
            fg=self.colors["text"],
            font=("Segoe UI", 25, "bold"),
        ).pack(anchor="w", pady=(3, 3))
        tk.Label(
            title_area,
            text="Create safe, non-bootable data ISOs with automatic backend detection.",
            bg=self.colors["content"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        hero = tk.Canvas(
            header,
            width=250,
            height=105,
            bg=self.colors["content"],
            highlightthickness=0,
            bd=0,
        )
        hero.grid(row=0, column=1, sticky="e")
        self._draw_hero_disc(hero)

        metrics = tk.Frame(content, bg=self.colors["content"], bd=0)
        metrics.grid(row=1, column=0, sticky="ew", padx=28, pady=(4, 12))
        for column in range(4):
            metrics.columnconfigure(column, weight=1, uniform="metric")

        self._create_metric_card(
            metrics,
            0,
            "SRC",
            "Source Folder",
            self.source_card_var,
            self.source_detail_var,
            self.colors["blue"],
        )
        self._create_metric_card(
            metrics,
            1,
            "OK",
            "Backend",
            self.backend_card_var,
            self.backend_detail_var,
            self.colors["success"],
        )
        self._create_metric_card(
            metrics,
            2,
            "UDF",
            "Compatibility",
            self.profile_card_var,
            None,
            self.colors["primary"],
        )
        self._create_metric_card(
            metrics,
            3,
            "SHA",
            "Integrity",
            self.integrity_card_var,
            None,
            self.colors["warning"],
        )

        workspace = tk.Frame(content, bg=self.colors["content"], bd=0)
        workspace.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 12))
        workspace.columnconfigure(0, weight=3)
        workspace.columnconfigure(1, weight=2)
        workspace.rowconfigure(0, weight=1)

        build_card = self._make_card(workspace, padx=18, pady=8)
        build_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        build_card.columnconfigure(0, weight=1)
        build_card.rowconfigure(1, weight=1)

        ttk.Label(build_card, text="Create New ISO", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        form = tk.Frame(build_card, bg=self.colors["card"], bd=0)
        form.grid(row=1, column=0, sticky="nsew")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        source_group = self._create_field_group(
            form,
            "Source Folder",
            self.source_var,
            command=self.pick_source,
            button_text="Browse",
        )
        source_group.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.source_entry = source_group.field

        output_group = self._create_field_group(
            form,
            "Output Folder",
            self.output_var,
            command=self.pick_output,
            button_text="Browse",
        )
        output_group.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        name_group = self._create_field_group(form, "ISO File Name", self.iso_name_var)
        name_group.grid(row=2, column=0, sticky="ew", padx=(0, 7), pady=(0, 8))
        label_group = self._create_field_group(form, "Volume Label", self.label_var)
        label_group.grid(row=2, column=1, sticky="ew", padx=(7, 0), pady=(0, 8))

        profile_group = self._create_combo_group(
            form,
            "Compatibility Profile",
            self.profile_var,
            PROFILES,
        )
        profile_group.grid(row=3, column=0, sticky="ew", padx=(0, 7), pady=(0, 8))
        backend_group = self._create_combo_group(
            form,
            "Backend",
            self.backend_var,
            ["Auto"],
        )
        backend_group.grid(row=3, column=1, sticky="ew", padx=(7, 0), pady=(0, 8))
        self.backend_combo = backend_group.field

        checks = tk.Frame(
            form,
            bg=self.colors["surface_2"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=10,
            pady=7,
        )
        checks.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(2, 9))
        checks.columnconfigure(0, weight=1)
        checks.columnconfigure(1, weight=1)
        checks.columnconfigure(2, weight=1)
        ttk.Checkbutton(
            checks,
            text="Include hidden",
            variable=self.include_hidden_var,
            style="Soft.TCheckbutton",
        ).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            checks,
            text="Generate SHA256",
            variable=self.hash_var,
            style="Soft.TCheckbutton",
        ).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(
            checks,
            textvariable=self.auto_package_text_var,
            variable=self.auto_package_var,
            command=self._on_auto_package_changed,
            style="Soft.TCheckbutton",
        ).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(
            checks,
            text="Optimize duplicates",
            variable=self.optimize_var,
            style="Soft.TCheckbutton",
        ).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(
            checks,
            text="Dry run only",
            variable=self.dry_run_var,
            style="Soft.TCheckbutton",
        ).grid(row=1, column=1, sticky="w")

        ttk.Button(
            form,
            text="Create ISO",
            style="Primary.TButton",
            command=self.start_build,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        activity_card = self._make_card(workspace, padx=16, pady=16)
        activity_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        activity_card.columnconfigure(0, weight=1)
        activity_card.rowconfigure(1, weight=1)
        ttk.Label(activity_card, text="Recent Activity", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        self.log_text = tk.Text(
            activity_card,
            wrap="word",
            width=44,
            height=16,
            font=("Cascadia Mono", 9),
            bg=self.colors["log_bg"],
            fg=self.colors["log_text"],
            insertbackground=self.colors["text"],
            selectbackground=self.colors["primary"],
            selectforeground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["focus"],
            bd=0,
            padx=11,
            pady=10,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            activity_card,
            orient="vertical",
            command=self.log_text.yview,
            style="Glass.Vertical.TScrollbar",
        )
        scroll.grid(row=1, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        progress_card = self._make_card(content, padx=18, pady=13)
        progress_card.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 16))
        progress_card.columnconfigure(0, weight=3)
        progress_card.columnconfigure(1, weight=2)

        status_area = tk.Frame(progress_card, bg=self.colors["card"], bd=0)
        status_area.grid(row=0, column=0, sticky="ew", padx=(0, 18))
        status_area.columnconfigure(0, weight=1)
        ttk.Label(status_area, textvariable=self.status_var, style="StatusTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(status_area, textvariable=self.summary_var, style="StatusHint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 7)
        )
        self.activity_progress = ttk.Progressbar(
            status_area,
            orient="horizontal",
            mode="determinate",
            value=0,
            style="Glass.Horizontal.TProgressbar",
        )
        self.activity_progress.grid(row=2, column=0, sticky="ew")

        output_area = tk.Frame(
            progress_card,
            bg=self.colors["surface_2"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=12,
            pady=8,
        )
        output_area.grid(row=0, column=1, sticky="nsew")
        tk.Label(
            output_area,
            text="Output",
            bg=self.colors["surface_2"],
            fg=self.colors["text"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            output_area,
            textvariable=self.output_card_var,
            bg=self.colors["surface_2"],
            fg=self.colors["muted"],
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
            wraplength=340,
        ).pack(anchor="w", pady=(3, 0))
        tk.Label(
            progress_card,
            text="Non-bootable data ISO • Source remains unchanged • No installer is executed",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 8),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _draw_logo(self, canvas: tk.Canvas) -> None:
        canvas.create_oval(9, 9, 91, 91, fill="#eef0ff", outline="#a8b1e9", width=2)
        canvas.create_arc(13, 13, 87, 87, start=20, extent=95, style="arc", outline="#8a6ff0", width=9)
        canvas.create_arc(13, 13, 87, 87, start=120, extent=95, style="arc", outline="#6eb6ff", width=9)
        canvas.create_arc(13, 13, 87, 87, start=220, extent=115, style="arc", outline="#e39adf", width=9)
        canvas.create_oval(38, 38, 62, 62, fill="#d9ddf5", outline="#ffffff", width=3)
        canvas.create_oval(45, 45, 55, 55, fill=self.colors["sidebar"], outline="")

    def _draw_hero_disc(self, canvas: tk.Canvas) -> None:
        canvas.create_oval(72, 71, 232, 105, fill="#d9d4d0", outline="")
        canvas.create_rectangle(72, 79, 232, 94, fill="#e9e3df", outline="")
        canvas.create_oval(68, 66, 236, 96, fill="#f2ece8", outline="#ffffff", width=2)
        canvas.create_oval(86, 4, 220, 92, fill="#f1efff", outline="#ffffff", width=2)
        canvas.create_arc(90, 8, 216, 88, start=5, extent=80, style="arc", outline="#90baff", width=8)
        canvas.create_arc(90, 8, 216, 88, start=90, extent=95, style="arc", outline="#d6a6ed", width=8)
        canvas.create_arc(90, 8, 216, 88, start=190, extent=90, style="arc", outline="#ffcfb0", width=8)
        canvas.create_arc(90, 8, 216, 88, start=285, extent=70, style="arc", outline="#a69df6", width=8)
        canvas.create_oval(137, 34, 169, 62, fill="#ffffff", outline="#d7d4ed", width=3)
        canvas.create_oval(147, 42, 159, 54, fill="#d8daeb", outline="")

    def _build_sidebar(self, sidebar: tk.Frame) -> None:
        brand = tk.Frame(sidebar, bg=self.colors["sidebar"], bd=0)
        brand.pack(fill="x", padx=18, pady=(22, 15))
        logo = tk.Canvas(
            brand,
            width=100,
            height=100,
            bg=self.colors["sidebar"],
            highlightthickness=0,
            bd=0,
        )
        logo.pack()
        self._draw_logo(logo)
        tk.Label(
            brand,
            text="ISO BUILDER",
            bg=self.colors["sidebar"],
            fg=self.colors["sidebar_text"],
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(4, 0))
        tk.Label(
            brand,
            text=f"v{APP_VERSION}",
            bg=self.colors["sidebar"],
            fg=self.colors["sidebar_muted"],
            font=("Segoe UI", 9),
        ).pack(pady=(2, 0))

        navigation = tk.Frame(sidebar, bg=self.colors["sidebar"], bd=0)
        navigation.pack(fill="x", padx=14, pady=(4, 0))
        ttk.Button(
            navigation,
            text="  Dashboard",
            style="SidebarActive.TButton",
            command=lambda: self.source_entry.focus_set(),
        ).pack(fill="x", pady=3)
        ttk.Button(
            navigation,
            text="  Create ISO",
            style="Sidebar.TButton",
            command=lambda: self.source_entry.focus_set(),
        ).pack(fill="x", pady=3)
        ttk.Button(
            navigation,
            text="  Scan Folder",
            style="Sidebar.TButton",
            command=self.scan_only,
        ).pack(fill="x", pady=3)
        ttk.Button(
            navigation,
            text="  Show Command",
            style="Sidebar.TButton",
            command=self.show_command,
        ).pack(fill="x", pady=3)
        ttk.Button(
            navigation,
            text="  Refresh Backends",
            style="Sidebar.TButton",
            command=self.refresh_backends,
        ).pack(fill="x", pady=3)
        ttk.Button(
            navigation,
            text="  Activity Log",
            style="Sidebar.TButton",
            command=lambda: self.log_text.focus_set(),
        ).pack(fill="x", pady=3)
        ttk.Button(
            navigation,
            text="  Clear Logs",
            style="Sidebar.TButton",
            command=self.clear_logs,
        ).pack(fill="x", pady=3)

        safety = tk.Frame(
            sidebar,
            bg=self.colors["sidebar_2"],
            highlightthickness=1,
            highlightbackground="#596394",
            padx=13,
            pady=12,
        )
        safety.pack(side="bottom", fill="x", padx=16, pady=18)
        tk.Label(
            safety,
            text="●  System Status",
            bg=self.colors["sidebar_2"],
            fg="#83e6ad",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            safety,
            textvariable=self.status_var,
            bg=self.colors["sidebar_2"],
            fg=self.colors["sidebar_text"],
            font=("Segoe UI", 9),
            wraplength=160,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

    def _make_card(self, parent: tk.Misc, *, padx: int, pady: int) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=self.colors["card"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            bd=0,
            padx=padx,
            pady=pady,
        )

    def _create_metric_card(
        self,
        parent: tk.Frame,
        column: int,
        icon_text: str,
        heading: str,
        value_var: tk.StringVar,
        detail_var: Optional[tk.StringVar],
        accent: str,
    ) -> None:
        card = self._make_card(parent, padx=12, pady=12)
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 5, 0 if column == 3 else 5),
        )
        card.columnconfigure(1, weight=1)
        icon = tk.Canvas(
            card,
            width=48,
            height=48,
            bg=self.colors["card"],
            highlightthickness=0,
            bd=0,
        )
        icon.grid(row=0, column=0, rowspan=3, sticky="w", padx=(0, 10))
        icon.create_oval(4, 4, 44, 44, fill=self.colors["surface_2"], outline=accent, width=2)
        icon.create_text(24, 24, text=icon_text, fill=accent, font=("Segoe UI", 8, "bold"))
        ttk.Label(card, text=heading, style="CardMuted.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(
            card,
            textvariable=value_var,
            style="Card.TLabel",
            font=("Segoe UI", 9, "bold"),
            wraplength=155,
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))
        if detail_var is not None:
            tk.Label(
                card,
                textvariable=detail_var,
                bg=self.colors["card"],
                fg=accent,
                font=("Segoe UI", 8),
                wraplength=155,
                justify="left",
            ).grid(row=2, column=1, sticky="w", pady=(2, 0))

    def _create_field_group(
        self,
        parent: tk.Frame,
        label: str,
        var: tk.StringVar,
        command: Optional[Callable[[], None]] = None,
        button_text: str = "",
    ) -> tk.Frame:
        group = tk.Frame(parent, bg=self.colors["card"], bd=0)
        group.columnconfigure(0, weight=1)
        tk.Label(
            group,
            text=label,
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        field = ttk.Entry(group, textvariable=var, style="Field.TEntry")
        field.grid(row=1, column=0, sticky="ew")
        group.field = field
        if command:
            ttk.Button(
                group,
                text=button_text or "Browse",
                style="Browse.TButton",
                command=command,
            ).grid(row=1, column=1, padx=(7, 0))
        return group

    def _create_combo_group(
        self,
        parent: tk.Frame,
        label: str,
        var: tk.StringVar,
        values: List[str],
    ) -> tk.Frame:
        group = tk.Frame(parent, bg=self.colors["card"], bd=0)
        group.columnconfigure(0, weight=1)
        tk.Label(
            group,
            text=label,
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        field = ttk.Combobox(
            group,
            textvariable=var,
            values=values,
            state="readonly",
            style="Field.TCombobox",
        )
        field.grid(row=1, column=0, sticky="ew")
        group.field = field
        return group

    def _set_status(self, title: str, hint: str = "") -> None:
        self.status_var.set(title)
        if hint:
            self.summary_var.set(hint)

    def _refresh_dashboard_cards(self, *_: object) -> None:
        profile_card_var = getattr(self, "profile_card_var", None)
        if profile_card_var is not None:
            profile_card_var.set(self.profile_var.get())

        integrity_card_var = getattr(self, "integrity_card_var", None)
        if integrity_card_var is not None:
            state = "enabled" if bool(self.hash_var.get()) else "disabled"
            integrity_card_var.set(f"SHA-256 {state}")

        backend_card_var = getattr(self, "backend_card_var", None)
        if backend_card_var is not None:
            selected = self.backend_var.get().split(" | ", 1)[0].strip()
            backend_card_var.set(selected or "Auto")

    def _set_activity_busy(self, busy: bool) -> None:
        progress = getattr(self, "activity_progress", None)
        if progress is None:
            return
        try:
            if busy:
                progress.configure(mode="indeterminate")
                progress.start(12)
            else:
                progress.stop()
                progress.configure(mode="determinate", value=0)
        except tk.TclError:
            pass

    def _on_auto_package_changed(self) -> None:
        enabled = bool(self.auto_package_var.get())
        state = "ON" if enabled else "OFF"
        self.auto_package_text_var.set(f"Auto package: {state}")
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
            self.source_card_var.set(source.name or str(source))
            self.source_detail_var.set("Ready to scan")
            self._set_status("Source selected", f"Ready to package: {source.name}")
            self.log(f"Source selected: {folder}")

    def pick_output(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_var.set(folder)
            self.output_card_var.set(folder)
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
        IsoBuilderApp._set_activity_busy(self, True)
        return True

    def _finish_operation(self, operation: str) -> None:
        if self.active_operation == operation:
            self.active_operation = None
            IsoBuilderApp._set_activity_busy(self, False)
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
        source_detail_var = getattr(self, "source_detail_var", None)
        if source_detail_var is not None:
            source_detail_var.set(
                f"{scan.files} files • {human_size(scan.total_bytes)}"
            )
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
        output_card_var = getattr(self, "output_card_var", None)
        if output_card_var is not None:
            output_card_var.set(str(plan.output_iso))

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
            self.backend_card_var.set("Not detected")
            self.backend_detail_var.set("Install or repair an ISO backend")
            self._set_status("No backend detected", "Install Windows ADK oscdimg or use the built-in fallback where available")
            self.log("WARNING: Koi ISO backend nahi mila.")
            self.log("Windows: oscdimg best hai; PowerShell IMAPI fallback bhi auto-detect hona chahiye.")
            self.log("Agar PowerShell bhi detect nahi ho raha, Windows PATH/system issue hai.")
            self.log("macOS: hdiutil usually built-in hota hai. Linux: xorriso/genisoimage install karo.")
            self.log("Python standard library alone reliable UDF/ISO image create nahi karti.")
        else:
            preferred = select_backend(self.detected_backends, self.profile_var.get())
            self.backend_card_var.set(preferred.name if preferred else "Auto")
            self.backend_detail_var.set(
                f"{len(self.detected_backends)} available • ready"
            )
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
