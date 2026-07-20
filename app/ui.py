"""Interfaz grafica moderna para el sistema de alertas de services."""

from __future__ import annotations

from datetime import date
from contextlib import redirect_stderr, redirect_stdout
import os
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import pandas as pd

from app.config import load_settings
from app.service_store import (
    list_service_contacts,
    update_service_phone,
    record_seguimiento,
    update_seguimiento_estado,
    list_seguimiento,
    get_seguimiento_aviso_ids,
)

# ── Paleta de colores ──────────────────────────────────────────────────────────
C_PRIMARY      = "#1565C0"   # azul principal
C_PRIMARY_DK   = "#0D47A1"   # azul oscuro (hover)
C_SUCCESS      = "#2E7D32"   # verde
C_SUCCESS_DK   = "#1B5E20"
C_WARNING      = "#E65100"   # naranja
C_WARNING_DK   = "#BF360C"
C_NEUTRAL      = "#455A64"   # gris azulado
C_NEUTRAL_DK   = "#263238"
C_BG           = "#F0F4F8"   # fondo general
C_CARD         = "#FFFFFF"   # fondo de tarjeta
C_BORDER       = "#CFD8DC"   # borde suave
C_TEXT         = "#212121"
C_TEXT_MUTED   = "#78909C"
C_HEADER_FG    = "#FFFFFF"
C_DOT_OK       = "#43A047"
C_DOT_BUSY     = "#FB8C00"
C_DOT_ERROR    = "#E53935"
FONT_FAMILY    = "Segoe UI"


def _apply_styles(root: tk.Tk) -> None:
    """Configura ttk.Style para toda la aplicacion."""
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=C_BG)

    # Frame y LabelFrame
    style.configure("TFrame", background=C_BG)
    style.configure("Card.TFrame", background=C_CARD, relief="flat")
    style.configure(
        "TLabelframe",
        background=C_CARD,
        bordercolor=C_BORDER,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=C_CARD,
        foreground=C_NEUTRAL,
        font=(FONT_FAMILY, 10, "bold"),
    )

    # Labels
    style.configure("TLabel", background=C_BG, foreground=C_TEXT, font=(FONT_FAMILY, 10))
    style.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT, font=(FONT_FAMILY, 10))
    style.configure("Muted.TLabel", background=C_CARD, foreground=C_TEXT_MUTED, font=(FONT_FAMILY, 9))
    style.configure("Section.TLabel", background=C_CARD, foreground=C_NEUTRAL, font=(FONT_FAMILY, 11, "bold"))
    style.configure("Status.TLabel", background=C_BG, foreground=C_NEUTRAL, font=(FONT_FAMILY, 10))

    # Botones — primario (azul)
    style.configure(
        "Primary.TButton",
        background=C_PRIMARY, foreground="white",
        font=(FONT_FAMILY, 10, "bold"),
        relief="flat", borderwidth=0, padding=(14, 7),
    )
    style.map("Primary.TButton",
              background=[("active", C_PRIMARY_DK), ("disabled", "#B0BEC5")],
              foreground=[("disabled", "#ECEFF1")])

    # Botones — éxito (verde)
    style.configure(
        "Success.TButton",
        background=C_SUCCESS, foreground="white",
        font=(FONT_FAMILY, 10, "bold"),
        relief="flat", borderwidth=0, padding=(14, 7),
    )
    style.map("Success.TButton",
              background=[("active", C_SUCCESS_DK), ("disabled", "#B0BEC5")],
              foreground=[("disabled", "#ECEFF1")])

    # Botones — advertencia (naranja)
    style.configure(
        "Warning.TButton",
        background=C_WARNING, foreground="white",
        font=(FONT_FAMILY, 10, "bold"),
        relief="flat", borderwidth=0, padding=(14, 7),
    )
    style.map("Warning.TButton",
              background=[("active", C_WARNING_DK), ("disabled", "#B0BEC5")],
              foreground=[("disabled", "#ECEFF1")])

    # Botones — neutro (gris)
    style.configure(
        "Neutral.TButton",
        background=C_NEUTRAL, foreground="white",
        font=(FONT_FAMILY, 10),
        relief="flat", borderwidth=0, padding=(14, 7),
    )
    style.map("Neutral.TButton",
              background=[("active", C_NEUTRAL_DK), ("disabled", "#B0BEC5")],
              foreground=[("disabled", "#ECEFF1")])

    # Botones — danger (rojo)
    style.configure(
        "Danger.TButton",
        background="#C62828", foreground="white",
        font=(FONT_FAMILY, 10, "bold"),
        relief="flat", borderwidth=0, padding=(10, 6),
    )
    style.map("Danger.TButton",
              background=[("active", "#B71C1C"), ("disabled", "#B0BEC5")],
              foreground=[("disabled", "#ECEFF1")])

    # Botones — outline (borde, fondo blanco)
    style.configure(
        "Outline.TButton",
        background=C_CARD, foreground=C_NEUTRAL,
        font=(FONT_FAMILY, 10),
        relief="solid", borderwidth=1, padding=(10, 6),
        bordercolor=C_BORDER,
    )
    style.map("Outline.TButton",
              background=[("active", "#ECEFF1"), ("disabled", "#ECEFF1")],
              bordercolor=[("active", C_NEUTRAL)])

    # Combobox
    style.configure(
        "TCombobox",
        background=C_CARD, foreground=C_TEXT,
        selectbackground=C_CARD, selectforeground=C_TEXT,
        font=(FONT_FAMILY, 10),
        padding=(6, 5),
    )
    style.map("TCombobox", fieldbackground=[("readonly", C_CARD)])

    # Treeview
    style.configure(
        "Treeview",
        background=C_CARD, fieldbackground=C_CARD,
        foreground=C_TEXT, font=(FONT_FAMILY, 10),
        rowheight=26,
    )
    style.configure(
        "Treeview.Heading",
        background="#ECEFF1", foreground=C_NEUTRAL,
        font=(FONT_FAMILY, 10, "bold"), relief="flat",
    )
    style.map("Treeview", background=[("selected", "#BBDEFB")], foreground=[("selected", C_TEXT)])

    # Entry
    style.configure("TEntry", font=(FONT_FAMILY, 10), padding=(6, 5))

    # Scrollbar
    style.configure("TScrollbar", background=C_BORDER, troughcolor=C_BG, relief="flat")


class AppUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PORTA — Alertas de Services")
        self.root.geometry("900x660")
        self.root.minsize(780, 560)
        self.running = False
        self._dot_color = C_DOT_OK

        today = date.today()
        self.month_var = tk.StringVar(value=str(today.month))
        self.year_var  = tk.StringVar(value=str(today.year))
        self.status_var = tk.StringVar(value="Listo")
        self._range_periods: list[str] = []  # periodos seleccionados para rango

        _apply_styles(root)
        self._build()

    def _build(self) -> None:
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=C_PRIMARY, height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="  PORTA   ·   Alertas de Services",
            bg=C_PRIMARY, fg=C_HEADER_FG,
            font=(FONT_FAMILY, 14, "bold"),
        ).pack(side=tk.LEFT, padx=20, pady=12)

        # ── Barra de acciones compacta ────────────────────────────────────────
        self._build_action_bar()

        # ── Panel de salida ───────────────────────────────────────────────────
        body = ttk.Frame(self.root, style="TFrame")
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 12))
        self._build_output_panel(body)

        self._write(
            "Sistema listo.\n\n"
            "·  Generar Excel  — crea el reporte sin enviar mensajes.\n"
            "·  Simular        — muestra qué se enviaría sin enviar nada.\n"
            "·  Ejecutar       — envía WhatsApp según la configuración del .env.\n"
            "·  Meses...       — generá Excel para uno o más meses a la vez.\n"
            "·  Revisar        — revisá services próximos y enviá avisos manualmente.\n"
        )

    # ── Barra de acciones compacta ────────────────────────────────────────────
    def _build_action_bar(self) -> None:
        """Barra compacta de dos filas: proceso mensual y tarea diaria."""
        panel = tk.Frame(self.root, bg=C_CARD,
                         highlightbackground=C_BORDER, highlightthickness=1)
        panel.pack(fill=tk.X)

        # ── Fila 1: Proceso mensual ────────────────────────────────────────────
        r1 = tk.Frame(panel, bg=C_CARD)
        r1.pack(fill=tk.X, padx=14, pady=(10, 5))

        tk.Label(r1, text="MENSUAL", bg=C_CARD, fg=C_TEXT_MUTED,
                 font=(FONT_FAMILY, 8, "bold")).pack(side=tk.LEFT, padx=(0, 10))

        month_values = [f"{m:02d} — {_month_name(m)}" for m in range(1, 13)]
        self.month_combo = ttk.Combobox(
            r1, width=13, state="readonly",
            textvariable=self.month_var, values=month_values,
        )
        self.month_combo.set(f"{int(self.month_var.get()):02d} — {_month_name(int(self.month_var.get()))}")
        self.month_combo.pack(side=tk.LEFT, padx=(0, 6))

        current_year = date.today().year
        self.year_combo = ttk.Combobox(
            r1, width=6, state="readonly",
            textvariable=self.year_var,
            values=[str(y) for y in range(current_year - 5, current_year + 3)],
        )
        self.year_combo.set(self.year_var.get())
        self.year_combo.pack(side=tk.LEFT, padx=(0, 10))

        self.generate_button = ttk.Button(
            r1, text="Generar Excel", style="Neutral.TButton",
            command=lambda: self._start_task("generate_excel"),
        )
        self.generate_button.pack(side=tk.LEFT, padx=3)

        self.test_button = ttk.Button(
            r1, text="Simular", style="Warning.TButton",
            command=lambda: self._start_task("test"),
        )
        self.test_button.pack(side=tk.LEFT, padx=3)

        self.run_button = ttk.Button(
            r1, text="Ejecutar", style="Success.TButton",
            command=lambda: self._start_task("run"),
        )
        self.run_button.pack(side=tk.LEFT, padx=3)

        ttk.Separator(r1, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=14, pady=1)

        ttk.Button(r1, text="📁  Reportes", style="Outline.TButton",
                   command=self._open_reports).pack(side=tk.LEFT, padx=3)
        ttk.Button(r1, text="📋  Logs", style="Outline.TButton",
                   command=self._open_logs).pack(side=tk.LEFT, padx=3)
        ttk.Button(r1, text="📞  Teléfonos", style="Outline.TButton",
                   command=self._open_contacts).pack(side=tk.LEFT, padx=3)

        # Divider entre filas
        tk.Frame(panel, bg=C_BORDER, height=1).pack(fill=tk.X, padx=14)

        # ── Fila 2: Tarea diaria ───────────────────────────────────────────────
        r2 = tk.Frame(panel, bg=C_CARD)
        r2.pack(fill=tk.X, padx=14, pady=(5, 10))

        tk.Label(r2, text="DIARIO", bg=C_CARD, fg=C_TEXT_MUTED,
                 font=(FONT_FAMILY, 8, "bold")).pack(side=tk.LEFT, padx=(0, 10))

        self.daily_button = ttk.Button(
            r2, text="Enviar avisos", style="Success.TButton",
            command=self._start_daily_task,
        )
        self.daily_button.pack(side=tk.LEFT, padx=3)

        self.daily_test_button = ttk.Button(
            r2, text="Simular avisos", style="Warning.TButton",
            command=self._start_daily_test_task,
        )
        self.daily_test_button.pack(side=tk.LEFT, padx=3)

        self.review_button = ttk.Button(
            r2, text="📋  Revisar services", style="Primary.TButton",
            command=lambda: ServicesReviewWindow(self.root),
        )
        self.review_button.pack(side=tk.LEFT, padx=3)

        ttk.Separator(r2, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=14, pady=1)

        self.my_number_button = ttk.Button(
            r2, text="📱  Mi número", style="Outline.TButton",
            command=self._start_test_my_number,
        )
        self.my_number_button.pack(side=tk.LEFT, padx=3)

        ttk.Button(
            r2, text="📊  Meses...", style="Outline.TButton",
            command=self._open_months_dialog,
        ).pack(side=tk.LEFT, padx=3)

    # ── Panel de salida ───────────────────────────────────────────────────────
    def _build_output_panel(self, parent: ttk.Frame) -> None:
        status_row = ttk.Frame(parent, style="TFrame")
        status_row.pack(fill=tk.X, pady=(0, 5))

        self._dot_label = tk.Label(
            status_row, text="●", fg=C_DOT_OK, bg=C_BG,
            font=(FONT_FAMILY, 13),
        )
        self._dot_label.pack(side=tk.LEFT)

        ttk.Label(
            status_row, textvariable=self.status_var, style="Status.TLabel",
        ).pack(side=tk.LEFT, padx=(5, 0))

        self.output = scrolledtext.ScrolledText(
            parent,
            font=("Consolas", 10),
            bg="#1E2A38", fg="#CFD8DC",
            insertbackground="white",
            relief="flat",
            wrap=tk.WORD,
            padx=10, pady=8,
        )
        self.output.pack(fill=tk.BOTH, expand=True)
        self.output.configure(state=tk.DISABLED)

        # Tags para colorear la salida
        self.output.tag_configure("ok",    foreground="#69F0AE")
        self.output.tag_configure("error", foreground="#FF5252")
        self.output.tag_configure("info",  foreground="#82B1FF")

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _start_task(self, action: str) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecución activa.")
            return

        period = _build_period(self.year_var.get(), self.month_var.get())
        if period is None:
            messagebox.showerror("Periodo inválido", "Use formato YYYY-MM, por ejemplo 2025-12.")
            return

        if action == "run":
            settings = load_settings()
            if not settings.modo_prueba:
                if not messagebox.askyesno(
                    "Confirmar envío",
                    "MODO_PRUEBA=false.\nEsta acción puede enviar WhatsApp reales.\n¿Desea continuar?",
                ):
                    return

        self.running = True
        self._set_buttons(False)
        self._set_status("Ejecutando...", C_DOT_BUSY)
        self._write(f"\n▶  Iniciando: {action}  |  periodo: {period}\n", tag="info")
        threading.Thread(target=self._run_task, args=(action, period), daemon=True).start()

    def _start_range_task_with_periods(self, periods: list[str]) -> None:
        """Lanza la generación de Excel para los periodos dados (llamado desde MonthsRangeDialog)."""
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecución activa.")
            return
        self.running = True
        self._set_buttons(False)
        self._set_status("Generando reportes...", C_DOT_BUSY)
        self._write(f"\n▶  Generando reporte para {len(periods)} mes(es)...\n", tag="info")
        threading.Thread(target=self._run_range_task, args=(periods,), daemon=True).start()

    def _start_daily_task(self) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecución activa.")
            return
        settings = load_settings()
        if not settings.modo_prueba:
            if not messagebox.askyesno(
                "Confirmar envío",
                "Se enviarán WhatsApp reales a clientes con vencimientos próximos.\n¿Desea continuar?",
            ):
                return
        self._launch_daily(force_test=False)

    def _start_daily_test_task(self) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecución activa.")
            return
        self._launch_daily(force_test=True)

    def _start_test_my_number(self) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecución activa.")
            return
        settings = load_settings()
        if not settings.whatsapp_test_number:
            messagebox.showerror(
                "Número no configurado",
                "Configure WHATSAPP_TEST_NUMBER en el .env con su número personal.\n"
                "Ejemplo: WHATSAPP_TEST_NUMBER=5491112345678",
            )
            return
        if not messagebox.askyesno(
            "Probar con mi número",
            f"Se enviará el primer vencimiento pendiente a:\n{settings.whatsapp_test_number}\n\n"
            "Es un mensaje real. ¿Desea continuar?",
        ):
            return
        self.running = True
        self._set_buttons(False)
        self._set_status("Enviando prueba...", C_DOT_BUSY)
        self._write(f"\n📱  Enviando prueba a {settings.whatsapp_test_number}...\n", tag="info")
        threading.Thread(target=self._run_test_my_number, daemon=True).start()

    def _launch_daily(self, force_test: bool) -> None:
        self.running = True
        self._set_buttons(False)
        label = "simulación de tarea diaria" if force_test else "tarea diaria"
        self._set_status("Ejecutando...", C_DOT_BUSY)
        self._write(f"\n▶  Iniciando {label}...\n", tag="info")
        threading.Thread(target=self._run_daily_task, args=(force_test,), daemon=True).start()

    # ── Runners (en hilo) ─────────────────────────────────────────────────────
    def _run_task(self, action: str, period: str) -> None:
        try:
            from main import run
            writer = TkTextWriter(self)
            with redirect_stdout(writer), redirect_stderr(writer):
                if action == "generate_excel":
                    exit_code = run(only_excel=True, period=period)
                elif action == "test":
                    exit_code = run(force_test=True, period=period)
                else:
                    exit_code = run(period=period)
            self.root.after(0, self._task_done, exit_code)
        except Exception as exc:
            self.root.after(0, self._task_failed, exc)

    def _run_range_task(self, periods: list[str]) -> None:
        from main import run
        writer = TkTextWriter(self)
        errors: list[str] = []
        with redirect_stdout(writer), redirect_stderr(writer):
            for i, period in enumerate(periods, 1):
                self.root.after(0, self._set_status, f"Mes {i}/{len(periods)}: {period}...", C_DOT_BUSY)
                try:
                    exit_code = run(only_excel=True, period=period)
                    if exit_code != 0:
                        errors.append(period)
                        print(f"[!] {period}: proceso finalizo con error.", flush=True)
                except Exception as exc:
                    errors.append(period)
                    print(f"[!] {period}: {exc}", flush=True)
        if errors:
            self.root.after(0, self._write, f"\n⚠  Errores en: {', '.join(errors)}\n", "error")
            self.root.after(0, self._task_done, 1)
        else:
            self.root.after(0, self._range_done, len(periods))

    def _run_daily_task(self, force_test: bool) -> None:
        try:
            from app.config import ensure_directories, load_settings
            from app.daily_alerts import run_daily_alert_check
            from app.logger import setup_logger
            from dataclasses import replace

            settings = load_settings()
            if force_test:
                settings = replace(settings, modo_prueba=True)
            ensure_directories(settings)

            writer = TkTextWriter(self)
            with redirect_stdout(writer), redirect_stderr(writer):
                logger = setup_logger(settings.log_dir)
                output_path = run_daily_alert_check(settings, logger)
                print(f"Tarea diaria finalizada. Reporte: {output_path}")

            self.root.after(0, self._task_done, 0)
        except Exception as exc:
            self.root.after(0, self._task_failed, exc)

    def _run_test_my_number(self) -> None:
        try:
            from app.config import ensure_directories, load_settings
            from app.daily_alerts import send_test_alert
            from app.logger import setup_logger

            settings = load_settings()
            ensure_directories(settings)

            writer = TkTextWriter(self)
            with redirect_stdout(writer), redirect_stderr(writer):
                logger = setup_logger(settings.log_dir)
                result = send_test_alert(settings, logger)
                print(result)

            self.root.after(0, self._task_done, 0)
        except Exception as exc:
            self.root.after(0, self._task_failed, exc)

    # ── Callbacks de finalización ─────────────────────────────────────────────
    def _task_done(self, exit_code: int) -> None:
        self.running = False
        self._set_buttons(True)
        if exit_code == 0:
            self._set_status("Proceso finalizado", C_DOT_OK)
            self._write("✓  Proceso finalizado correctamente.\n", tag="ok")
        else:
            self._set_status("Finalizado con errores", C_DOT_ERROR)
            self._write(f"⚠  Proceso finalizado con código {exit_code}.\n", tag="error")

    def _range_done(self, count: int) -> None:
        self.running = False
        self._set_buttons(True)
        self._set_status("Reportes generados", C_DOT_OK)
        self._write(f"✓  {count} mes(es) generados correctamente.\n", tag="ok")

    def _task_failed(self, exc: Exception) -> None:
        self.running = False
        self._set_buttons(True)
        self._set_status("Error", C_DOT_ERROR)
        self._write(f"✗  ERROR: {exc}\n", tag="error")
        messagebox.showerror("Error", str(exc))

    # ── Utilidades de UI ──────────────────────────────────────────────────────
    def _set_buttons(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for btn in (
            self.generate_button, self.test_button, self.run_button,
            self.daily_button, self.daily_test_button, self.my_number_button,
            self.review_button,
        ):
            btn.configure(state=state)

    def _set_status(self, text: str, dot_color: str = C_DOT_OK) -> None:
        self.status_var.set(text)
        self._dot_label.configure(fg=dot_color)

    def _write(self, text: str, tag: str = "") -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text, tag if tag else ())
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def _open_reports(self) -> None:
        _open_folder(load_settings().output_dir)

    def _open_logs(self) -> None:
        _open_folder(load_settings().log_dir)

    def _open_contacts(self) -> None:
        ContactsWindow(self.root)

    def _open_months_dialog(self) -> None:
        MonthsRangeDialog(self.root, self)


# ── Diálogo: selección de meses para reporte ─────────────────────────────────
class MonthsRangeDialog:
    """Popup para seleccionar meses y generar reporte de rango."""

    def __init__(self, parent: tk.Tk, app: "AppUI") -> None:
        self.app = app
        self._period_map: list[str] = []
        self.window = tk.Toplevel(parent)
        self.window.title("Reporte de meses seleccionados")
        self.window.geometry("360x460")
        self.window.resizable(False, False)
        self.window.configure(bg=C_BG)
        _apply_styles(self.window)
        self._build()

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self.window, bg=C_PRIMARY, height=44)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Reporte de meses", bg=C_PRIMARY, fg="white",
                 font=(FONT_FAMILY, 12, "bold")).pack(side=tk.LEFT, padx=16, pady=10)

        body = tk.Frame(self.window, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        tk.Label(
            body,
            text="Seleccioná uno o más meses con Ctrl+click.\nSe generará un Excel con una hoja por mes.",
            bg=C_BG, fg=C_TEXT_MUTED, font=(FONT_FAMILY, 9), justify="left",
        ).pack(anchor="w", pady=(0, 8))

        # Listbox
        list_frame = tk.Frame(body, bg=C_CARD,
                               highlightbackground=C_BORDER, highlightthickness=1)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self._listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            font=(FONT_FAMILY, 10),
            bg=C_CARD, fg=C_TEXT,
            selectbackground=C_PRIMARY, selectforeground="white",
            activestyle="none",
            relief="flat",
            highlightthickness=0,
            bd=0,
        )
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)

        # Poblar (últimos 24 meses, más reciente al inicio)
        today = date.today()
        for i in range(23, -1, -1):
            month = (today.month - 1 - i) % 12 + 1
            year  = today.year + ((today.month - 1 - i) // 12)
            period = f"{year:04d}-{month:02d}"
            self._listbox.insert(tk.END, f"{_month_name(month)} {year}")
            self._period_map.append(period)
            if month == today.month and year == today.year:
                self._listbox.selection_set(tk.END)

        # Botones
        btn_frame = tk.Frame(body, bg=C_BG)
        btn_frame.pack(fill=tk.X)

        ttk.Button(
            btn_frame, text="📊  Generar seleccionados", style="Neutral.TButton",
            command=self._generate,
        ).pack(fill=tk.X, pady=(0, 6))

        row = tk.Frame(btn_frame, bg=C_BG)
        row.pack(fill=tk.X)
        ttk.Button(
            row, text="Seleccionar todo", style="Outline.TButton",
            command=lambda: self._listbox.selection_set(0, tk.END),
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(
            row, text="Limpiar", style="Outline.TButton",
            command=lambda: self._listbox.selection_clear(0, tk.END),
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

    def _generate(self) -> None:
        if self.app.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecución activa.", parent=self.window)
            return
        indices = self._listbox.curselection()
        if not indices:
            messagebox.showwarning("Sin selección", "Seleccioná al menos un mes de la lista.", parent=self.window)
            return
        periods = sorted(self._period_map[i] for i in indices)
        labels_sorted = [self._listbox.get(self._period_map.index(p)) for p in periods]
        if not messagebox.askyesno(
            "Confirmar generación",
            f"Se generará el Excel para {len(periods)} mes(es):\n\n" +
            "\n".join(f"  · {l}" for l in labels_sorted) +
            "\n\n¿Continuar?",
            parent=self.window,
        ):
            return
        self.window.destroy()
        self.app._start_range_task_with_periods(periods)


# ── Widget auxiliar: tarjeta ──────────────────────────────────────────────────
class _Card(tk.Frame):
    """Frame con borde y fondo de tarjeta blanca."""
    def __init__(self, parent, title: str = "", **kwargs) -> None:
        super().__init__(parent, bg=C_CARD, highlightbackground=C_BORDER,
                         highlightthickness=1, **kwargs)
        if title:
            tk.Label(
                self, text=title, bg=C_CARD, fg=C_NEUTRAL,
                font=(FONT_FAMILY, 11, "bold"),
            ).pack(anchor="w", padx=14, pady=(10, 4))
        self.inner = ttk.Frame(self, style="Card.TFrame")
        self.inner.pack(fill=tk.X, padx=14, pady=(0, 12))


# ── Ventana de teléfonos ──────────────────────────────────────────────────────
class ContactsWindow:
    def __init__(self, parent: tk.Tk) -> None:
        self.settings = load_settings()
        self.window = tk.Toplevel(parent)
        self.window.title("Teléfonos de clientes")
        self.window.geometry("980x540")
        self.window.minsize(820, 440)
        self.window.configure(bg=C_BG)
        self.search_var = tk.StringVar()
        self.phone_var  = tk.StringVar()
        self.selected_aviso_id = ""
        _apply_styles(self.window)
        self._build()
        self._load_contacts()

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self.window, bg=C_PRIMARY, height=44)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Teléfonos de clientes", bg=C_PRIMARY, fg="white",
                 font=(FONT_FAMILY, 12, "bold")).pack(side=tk.LEFT, padx=16, pady=8)

        frame = ttk.Frame(self.window, style="TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        # Búsqueda
        top = ttk.Frame(frame, style="TFrame")
        top.pack(fill=tk.X, pady=(0, 8))
        tk.Label(top, text="Buscar:", bg=C_BG, fg=C_TEXT,
                 font=(FONT_FAMILY, 10)).pack(side=tk.LEFT)
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=36)
        search_entry.pack(side=tk.LEFT, padx=(8, 6))
        search_entry.bind("<Return>", lambda _: self._load_contacts())
        ttk.Button(top, text="Buscar", style="Primary.TButton",
                   command=self._load_contacts).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Actualizar", style="Outline.TButton",
                   command=self._load_contacts).pack(side=tk.LEFT, padx=4)

        # Tabla
        columns = ("cliente", "equipo", "serial", "lugar", "telefono", "vencimiento", "actualizado")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        headings = {
            "cliente": "Cliente", "equipo": "Equipo", "serial": "Serial",
            "lugar": "Lugar", "telefono": "Teléfono",
            "vencimiento": "Próximo service", "actualizado": "Actualizado",
        }
        widths = {
            "cliente": 210, "equipo": 150, "serial": 130, "lugar": 70,
            "telefono": 130, "vencimiento": 120, "actualizado": 140,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor=tk.W)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        vsb.pack(side=tk.LEFT, fill=tk.Y, pady=(0, 10))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Bottom
        bottom = ttk.Frame(frame.master if False else frame, style="TFrame")
        bottom.pack(fill=tk.X)
        tk.Label(bottom, text="Teléfono:", bg=C_BG, fg=C_TEXT,
                 font=(FONT_FAMILY, 10)).pack(side=tk.LEFT)
        ttk.Entry(bottom, textvariable=self.phone_var, width=26).pack(side=tk.LEFT, padx=(8, 6))
        ttk.Button(bottom, text="Guardar teléfono", style="Primary.TButton",
                   command=self._save_phone).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="Enviar aviso ahora", style="Success.TButton",
                   command=self._send_now).pack(side=tk.LEFT, padx=(10, 4))
        tk.Label(bottom, text="Formato: código de país + área + número, sin espacios.",
                 bg=C_BG, fg=C_TEXT_MUTED, font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(10, 0))

    def _load_contacts(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        contacts = list_service_contacts(self.settings, self.search_var.get())
        for _, row in contacts.iterrows():
            aviso_id = str(row.get("aviso_id", ""))
            self.tree.insert("", tk.END, iid=aviso_id, values=(
                row.get("cliente", ""), row.get("equipo", ""), row.get("serial", ""),
                row.get("lugar", ""), row.get("telefono_cliente", ""),
                row.get("fecha_estimada_proximo_service", ""), row.get("updated_at", ""),
            ))

    def _on_select(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        self.selected_aviso_id = selected[0]
        values = self.tree.item(selected[0], "values")
        self.phone_var.set(values[4] if len(values) > 4 else "")

    def _save_phone(self) -> None:
        if not self.selected_aviso_id:
            messagebox.showinfo("Selección requerida", "Seleccione un registro de la lista.")
            return
        try:
            update_service_phone(self.settings, self.selected_aviso_id, self.phone_var.get().strip())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        self._load_contacts()
        messagebox.showinfo("Teléfono guardado", "El teléfono quedó guardado en la base local.")

    def _send_now(self) -> None:
        if not self.selected_aviso_id:
            messagebox.showinfo("Selección requerida", "Seleccione un registro de la lista.")
            return
        phone = self.phone_var.get().strip()
        if not phone:
            messagebox.showwarning("Sin teléfono", "El cliente seleccionado no tiene teléfono cargado.")
            return
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        cliente = values[0] if len(values) > 0 else ""
        equipo  = values[1] if len(values) > 1 else ""
        serial  = values[2] if len(values) > 2 else ""
        venc    = values[5] if len(values) > 5 else ""

        if not messagebox.askyesno(
            "Confirmar envío",
            f"Enviar aviso de service a:\n\nCliente: {cliente}\nEquipo: {equipo}\n"
            f"Serial: {serial}\nVencimiento: {venc}\nTeléfono: {phone}",
        ):
            return

        def _run() -> None:
            try:
                from app.notifier_whatsapp import build_service_message, normalize_phone, send_whatsapp_text
                import pandas as pd
                row = pd.Series({"equipo": equipo, "serial": serial,
                                 "horas_actuales": "", "fecha_estimada_proximo_service": venc})
                dest = normalize_phone(phone, self.settings.whatsapp_country_prefix)
                send_whatsapp_text(dest, build_service_message(row), self.settings)
                self.window.after(0, lambda: messagebox.showinfo(
                    "Aviso enviado", f"Mensaje enviado correctamente a {dest}."))
            except Exception as exc:
                self.window.after(0, lambda: messagebox.showerror("Error al enviar", str(exc)))

        threading.Thread(target=_run, daemon=True).start()


# ── Ventana de revisión manual de services ────────────────────────────────────
class ServicesReviewWindow:
    """Ventana con dos pestañas: proximos a vencer y vencidos, con envio manual por fila."""

    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.settings = load_settings()
        self.window = tk.Toplevel(parent)
        self.window.title("Revisión de Services")
        self.window.geometry("1180x640")
        self.window.minsize(900, 500)
        self.window.configure(bg=C_BG)
        _apply_styles(self.window)
        self._status_var = tk.StringVar(value="Cargando datos...")
        self._proximos: pd.DataFrame = pd.DataFrame()
        self._vencidos: pd.DataFrame = pd.DataFrame()
        self._enviados: pd.DataFrame = pd.DataFrame()
        self._build()
        threading.Thread(target=self._load_data, daemon=True).start()

    def _build(self) -> None:
        hdr = tk.Frame(self.window, bg=C_PRIMARY, height=44)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Revisión de Services", bg=C_PRIMARY, fg="white",
                 font=(FONT_FAMILY, 12, "bold")).pack(side=tk.LEFT, padx=16, pady=8)

        top = ttk.Frame(self.window, style="TFrame")
        top.pack(fill=tk.X, padx=14, pady=(8, 0))
        ttk.Label(top, textvariable=self._status_var, style="Status.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="↺  Actualizar", style="Outline.TButton",
                   command=self._refresh).pack(side=tk.RIGHT)

        self._notebook = ttk.Notebook(self.window)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)
        self._tab_proximos = ttk.Frame(self._notebook, style="TFrame")
        self._tab_vencidos = ttk.Frame(self._notebook, style="TFrame")
        self._tab_enviados = ttk.Frame(self._notebook, style="TFrame")
        self._notebook.add(self._tab_proximos, text="  Próximos a vencer  ")
        self._notebook.add(self._tab_vencidos, text="  Vencidos  ")
        self._notebook.add(self._tab_enviados, text="  Enviados  ")

    def _load_data(self) -> None:
        try:
            from app.lector_datos import load_source_data
            from app.procesador_services import process_services
            self.window.after(0, lambda: self._status_var.set("Conectando a TacticaSoft..."))
            raw = load_source_data(self.settings)
            self.window.after(0, lambda: self._status_var.set("Procesando equipos..."))
            df = process_services(raw, self.settings)

            # Ids ya enviados manualmente → filtrar de proximos/vencidos
            seg_ids = get_seguimiento_aviso_ids(self.settings)

            if not df.empty and "dias_restantes" in df.columns:
                dias = pd.to_numeric(df["dias_restantes"], errors="coerce")
                proximos = df[dias.between(0, 7)].copy().sort_values("dias_restantes")
                vencidos = df[dias < 0].copy().sort_values("dias_restantes")
                if seg_ids:
                    proximos = proximos[~proximos["id_interno_aviso"].astype(str).isin(seg_ids)]
                    vencidos = vencidos[~vencidos["id_interno_aviso"].astype(str).isin(seg_ids)]
            else:
                proximos = vencidos = pd.DataFrame()

            # Seguimiento de enviados manuales
            self._enviados = list_seguimiento(self.settings)

            self._proximos = proximos
            self._vencidos = vencidos
            self.window.after(0, self._render_tabs)
        except Exception as exc:
            self.window.after(0, lambda: self._status_var.set(f"Error: {exc}"))

    def _render_tabs(self) -> None:
        n_prox = len(self._proximos)
        n_venc = len(self._vencidos)
        n_env  = len(self._enviados)
        self._status_var.set(f"{n_prox} próximos a vencer  ·  {n_venc} vencidos  ·  {n_env} enviados")
        self._notebook.tab(0, text=f"  Próximos a vencer ({n_prox})  ")
        self._notebook.tab(1, text=f"  Vencidos ({n_venc})  ")
        self._notebook.tab(2, text=f"  Enviados ({n_env})  ")
        self._build_table(self._tab_proximos, self._proximos)
        self._build_table(self._tab_vencidos, self._vencidos)
        self._build_enviados_table(self._tab_enviados, self._enviados)

    def _build_table(self, parent: ttk.Frame, df: pd.DataFrame) -> None:
        for w in parent.winfo_children():
            w.destroy()

        if df.empty:
            ttk.Label(parent, text="Sin registros.", style="Muted.TLabel").pack(pady=30)
            return

        # Cabecera fija
        hdr = tk.Frame(parent, bg="#ECEFF1")
        hdr.pack(fill=tk.X, padx=2, pady=(2, 0))
        for text, w in [("Cliente", 28), ("Equipo", 22), ("Fecha estimada", 14), ("Días", 9), ("Teléfono", 18), ("", 13)]:
            tk.Label(hdr, text=text, bg="#ECEFF1", fg=C_NEUTRAL,
                     font=(FONT_FAMILY, 9, "bold"), width=w, anchor="w").pack(side=tk.LEFT, padx=4, pady=5)

        # Área scrollable
        outer = tk.Frame(parent, bg=C_BG)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=C_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=C_BG)
        cw = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))

        def _on_scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_scroll))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        for i, (_, row) in enumerate(df.iterrows()):
            bg = C_CARD if i % 2 == 0 else "#F5F7FA"
            self._build_row(inner, row, bg)

    def _build_row(self, parent: tk.Frame, row: pd.Series, bg: str) -> None:
        from app.notifier_whatsapp import normalize_phone

        cliente   = str(row.get("cliente", ""))
        serial    = str(row.get("serial", ""))
        tel_raw   = str(row.get("telefono_cliente", "") or "")
        aviso_id  = str(row.get("id_interno_aviso", "") or "")
        id_empresa = row.get("id_empresa", None)

        fecha = row.get("fecha_estimada_proximo_service", "")
        fecha_str = fecha.strftime("%d/%m/%Y") if hasattr(fecha, "strftime") else str(fecha or "")

        try:
            dias_int = int(float(row.get("dias_restantes", "")))
            if dias_int < 0:
                dias_txt, dias_color = f"{abs(dias_int)}d vencido", "#C62828"
            elif dias_int == 0:
                dias_txt, dias_color = "Hoy", C_WARNING
            else:
                dias_txt, dias_color = f"en {dias_int}d", (C_SUCCESS if dias_int > 3 else C_WARNING)
        except (ValueError, TypeError):
            dias_txt, dias_color = "", C_TEXT

        f = tk.Frame(parent, bg=bg, pady=5)
        f.pack(fill=tk.X, padx=2, pady=1)

        tk.Label(f, text=cliente,   bg=bg, fg=C_TEXT, font=(FONT_FAMILY, 10), anchor="w", width=28).pack(side=tk.LEFT, padx=(8, 4))
        tk.Label(f, text=serial,    bg=bg, fg=C_TEXT, font=(FONT_FAMILY, 10), anchor="w", width=22).pack(side=tk.LEFT, padx=4)
        tk.Label(f, text=fecha_str, bg=bg, fg=C_TEXT, font=(FONT_FAMILY, 10), anchor="w", width=14).pack(side=tk.LEFT, padx=4)
        tk.Label(f, text=dias_txt,  bg=bg, fg=dias_color, font=(FONT_FAMILY, 10, "bold"), anchor="w", width=9).pack(side=tk.LEFT, padx=4)

        # Teléfono editable
        phone_var = tk.StringVar(value=tel_raw)
        ttk.Entry(f, textvariable=phone_var, width=18, font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=4)

        # Botón guardar en BD local
        send_btn_ref: list = [None]

        def _on_phone_change(*_):
            raw = phone_var.get().strip()
            normalized = normalize_phone(raw, self.settings.whatsapp_country_prefix)
            ok = 12 <= len(normalized) <= 13
            if send_btn_ref[0]:
                send_btn_ref[0].configure(
                    state=tk.NORMAL if ok else tk.DISABLED,
                    style="Primary.TButton" if ok else "Neutral.TButton",
                )

        phone_var.trace_add("write", _on_phone_change)

        if aviso_id:
            ttk.Button(
                f, text="💾", style="Outline.TButton", width=3,
                command=lambda v=phone_var, aid=aviso_id, eid=id_empresa: self._save_phone_local(v.get().strip(), aid, eid),
            ).pack(side=tk.LEFT, padx=(0, 4))

        tel_inicial = normalize_phone(tel_raw, self.settings.whatsapp_country_prefix)
        tel_ok_inicial = 12 <= len(tel_inicial) <= 13
        send_btn = ttk.Button(
            f, text="Enviar",
            style="Primary.TButton" if tel_ok_inicial else "Neutral.TButton",
            command=lambda r=row, pv=phone_var: self._enviar(
                r,
                normalize_phone(pv.get().strip(), self.settings.whatsapp_country_prefix),
                12 <= len(normalize_phone(pv.get().strip(), self.settings.whatsapp_country_prefix)) <= 13,
            ),
        )
        if not tel_ok_inicial:
            send_btn.configure(state=tk.DISABLED)
        send_btn.pack(side=tk.LEFT, padx=(0, 8))
        send_btn_ref[0] = send_btn

    def _save_phone_local(self, new_number: str, aviso_id: str, id_empresa=None) -> None:
        if not new_number:
            messagebox.showwarning("Sin número", "Ingresá un número antes de guardar.", parent=self.window)
            return
        try:
            update_service_phone(self.settings, aviso_id, new_number)
            messagebox.showinfo("Guardado", "Teléfono guardado en la base local.", parent=self.window)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self.window)

    def _enviar(self, row: pd.Series, tel: str, tel_ok: bool) -> None:
        if not tel_ok:
            messagebox.showwarning("Teléfono inválido", "Este equipo no tiene teléfono válido.", parent=self.window)
            return

        cliente   = str(row.get("cliente", ""))
        serial    = str(row.get("serial", ""))
        fecha     = row.get("fecha_estimada_proximo_service", "")
        fecha_str = fecha.strftime("%d/%m/%Y") if hasattr(fecha, "strftime") else str(fecha or "")

        if not messagebox.askyesno(
            "Confirmar envío",
            f"Enviar aviso de service a:\n\nCliente:     {cliente}\nEquipo:      {serial}\nVencimiento: {fecha_str}\nTeléfono:    +{tel}\n\n¿Continuar?",
            parent=self.window,
        ):
            return

        def _send() -> None:
            try:
                from app.notifier_whatsapp import build_service_message, send_whatsapp_text
                msg = build_service_message(row, operario_whatsapp=self.settings.operario_whatsapp)
                send_whatsapp_text(tel, msg, self.settings)
                # Registrar en seguimiento
                aviso_id  = str(row.get("id_interno_aviso", "") or "")
                fecha     = row.get("fecha_estimada_proximo_service", "")
                fecha_str = fecha.strftime("%Y-%m-%d") if hasattr(fecha, "strftime") else str(fecha or "")
                record_seguimiento(
                    self.settings, aviso_id,
                    str(row.get("cliente", "")),
                    str(row.get("serial", "")),
                    str(row.get("equipo", "")),
                    fecha_str, tel,
                )
                self.window.after(0, self._refresh)
                self.window.after(0, lambda: messagebox.showinfo(
                    "Enviado", f"Mensaje enviado a +{tel}.\nLa fila pasó a la pestaña Enviados.", parent=self.window))
            except Exception as exc:
                self.window.after(0, lambda: messagebox.showerror("Error al enviar", str(exc), parent=self.window))

        threading.Thread(target=_send, daemon=True).start()

    def _build_enviados_table(self, parent: ttk.Frame, df: pd.DataFrame) -> None:
        for w in parent.winfo_children():
            w.destroy()

        if df.empty:
            ttk.Label(parent, text="Sin mensajes enviados manualmente.", style="Muted.TLabel").pack(pady=30)
            return

        # Cabecera
        hdr = tk.Frame(parent, bg="#ECEFF1")
        hdr.pack(fill=tk.X, padx=2, pady=(2, 0))
        for text, w in [("Fecha envío", 17), ("Cliente", 26), ("Serial", 16), ("Teléfono", 14), ("Próximo service", 14), ("", 16)]:
            tk.Label(hdr, text=text, bg="#ECEFF1", fg=C_NEUTRAL,
                     font=(FONT_FAMILY, 9, "bold"), width=w, anchor="w").pack(side=tk.LEFT, padx=4, pady=5)

        # Área scrollable
        outer = tk.Frame(parent, bg=C_BG)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=C_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=C_BG)
        cw = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))

        def _on_scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_scroll))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Colores por estado
        _BG_ESTADO = {
            "coordinado":    "#E8F5E9",
            "sin_respuesta": "#FFEBEE",
        }
        _FG_ESTADO = {
            "pendiente":     C_TEXT_MUTED,
            "coordinado":    C_SUCCESS,
            "sin_respuesta": "#C62828",
        }
        _LABEL_ESTADO = {
            "pendiente":     "Pendiente",
            "coordinado":    "✓ Coordinado",
            "sin_respuesta": "✗ Sin respuesta",
        }

        for i, (_, row) in enumerate(df.iterrows()):
            estado = str(row.get("estado", "pendiente"))
            bg = _BG_ESTADO.get(estado, C_CARD if i % 2 == 0 else "#F5F7FA")

            seg_id = int(row.get("id", 0))

            fecha_env = row.get("fecha_envio", "")
            try:
                fecha_env_str = pd.to_datetime(fecha_env).strftime("%d/%m/%Y %H:%M")
            except Exception:
                fecha_env_str = str(fecha_env or "")

            fecha_est = row.get("fecha_estimada", "")
            try:
                fecha_est_str = pd.to_datetime(fecha_est).strftime("%d/%m/%Y")
            except Exception:
                fecha_est_str = str(fecha_est or "")

            f = tk.Frame(inner, bg=bg, pady=5)
            f.pack(fill=tk.X, padx=2, pady=1)

            tk.Label(f, text=fecha_env_str,                    bg=bg, fg=C_TEXT,  font=(FONT_FAMILY, 10), anchor="w", width=17).pack(side=tk.LEFT, padx=(8, 4))
            tk.Label(f, text=str(row.get("cliente", "")),      bg=bg, fg=C_TEXT,  font=(FONT_FAMILY, 10), anchor="w", width=26).pack(side=tk.LEFT, padx=4)
            tk.Label(f, text=str(row.get("serial", "")),       bg=bg, fg=C_TEXT,  font=(FONT_FAMILY, 10), anchor="w", width=16).pack(side=tk.LEFT, padx=4)
            tk.Label(f, text=str(row.get("telefono", "")),     bg=bg, fg=C_TEXT,  font=(FONT_FAMILY, 10), anchor="w", width=14).pack(side=tk.LEFT, padx=4)
            tk.Label(f, text=fecha_est_str,                    bg=bg, fg=C_TEXT,  font=(FONT_FAMILY, 10), anchor="w", width=14).pack(side=tk.LEFT, padx=4)

            if estado == "pendiente":
                # Botones ✓ y ✗
                ttk.Button(
                    f, text="✓", style="Success.TButton", width=3,
                    command=lambda sid=seg_id: self._update_seguimiento(sid, "coordinado"),
                ).pack(side=tk.LEFT, padx=(4, 2))
                ttk.Button(
                    f, text="✗", style="Danger.TButton", width=3,
                    command=lambda sid=seg_id: self._update_seguimiento(sid, "sin_respuesta"),
                ).pack(side=tk.LEFT, padx=(2, 8))
            else:
                tk.Label(
                    f, text=_LABEL_ESTADO.get(estado, estado),
                    bg=bg, fg=_FG_ESTADO.get(estado, C_TEXT),
                    font=(FONT_FAMILY, 10, "bold"), anchor="w", width=16,
                ).pack(side=tk.LEFT, padx=(4, 8))

    def _update_seguimiento(self, seguimiento_id: int, estado: str) -> None:
        try:
            update_seguimiento_estado(self.settings, seguimiento_id, estado)
            self._refresh()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self.window)

    def _refresh(self) -> None:
        for tab in (self._tab_proximos, self._tab_vencidos, self._tab_enviados):
            for w in tab.winfo_children():
                w.destroy()
        self._status_var.set("Actualizando...")
        threading.Thread(target=self._load_data, daemon=True).start()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _build_period(year_value: str, month_value: str) -> str | None:
    try:
        year = int(year_value.strip())
        month = int(month_value.split("—", 1)[0].strip().split("-", 1)[0].strip())
    except Exception:
        return None
    if not (1900 <= year <= 3000) or not (1 <= month <= 12):
        return None
    return f"{year:04d}-{month:02d}"


def _month_name(month: int) -> str:
    return {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }[month]


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.startfile(path)


class TkTextWriter:
    def __init__(self, ui: AppUI) -> None:
        self.ui = ui

    def write(self, text: str) -> int:
        if text:
            self.ui.root.after(0, self.ui._write, text)
        return len(text)

    def flush(self) -> None:
        return None


def launch_ui() -> None:
    root = tk.Tk()
    AppUI(root)
    root.mainloop()
