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
    get_seguimiento,
    registrar_reenvio,
    update_seguimiento_estado,
    list_seguimiento,
    get_seguimiento_aviso_ids,
    list_historial,
    update_historial_fecha_coordinada,
    desestimar_service,
    restaurar_service,
    get_desestimados_aviso_ids,
    list_descartados,
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

        self.rutas_button = ttk.Button(
            r2, text="🗺  Hojas de ruta", style="Primary.TButton",
            command=self._open_hojas_ruta,
        )
        self.rutas_button.pack(side=tk.LEFT, padx=3)

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

    def _open_hojas_ruta(self) -> None:
        try:
            from app.ui_hojas_ruta import HojasRutaWindow
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "Hojas de ruta no disponible",
                f"No se pudo abrir el módulo:\n{exc}\n\n"
                "Instalá las dependencias con:\n"
                "  pip install gspread google-auth reportlab requests",
            )
            return
        HojasRutaWindow(self.root)


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
        self._proximos:    pd.DataFrame = pd.DataFrame()
        self._vencidos:    pd.DataFrame = pd.DataFrame()
        self._enviados:    pd.DataFrame = pd.DataFrame()
        self._historial:   pd.DataFrame = pd.DataFrame()
        self._descartados: pd.DataFrame = pd.DataFrame()
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
        self._tab_proximos    = ttk.Frame(self._notebook, style="TFrame")
        self._tab_vencidos    = ttk.Frame(self._notebook, style="TFrame")
        self._tab_enviados    = ttk.Frame(self._notebook, style="TFrame")
        self._tab_historial   = ttk.Frame(self._notebook, style="TFrame")
        self._tab_descartados = ttk.Frame(self._notebook, style="TFrame")
        self._notebook.add(self._tab_proximos,    text="  Próximos a vencer  ")
        self._notebook.add(self._tab_vencidos,    text="  Vencidos  ")
        self._notebook.add(self._tab_enviados,    text="  Enviados  ")
        self._notebook.add(self._tab_historial,   text="  Historial  ")
        self._notebook.add(self._tab_descartados, text="  Desestimados  ")

    def _load_data(self) -> None:
        try:
            from app.lector_datos import load_source_data
            from app.procesador_services import process_services
            self.window.after(0, lambda: self._status_var.set("Conectando a TacticaSoft..."))
            raw = load_source_data(self.settings)
            self.window.after(0, lambda: self._status_var.set("Procesando equipos..."))
            df = process_services(raw, self.settings)

            # Ids ya enviados manualmente o desestimados → filtrar de proximos/vencidos
            seg_ids  = get_seguimiento_aviso_ids(self.settings)
            desc_ids = get_desestimados_aviso_ids(self.settings)
            excluir  = seg_ids | desc_ids

            if not df.empty and "dias_restantes" in df.columns:
                dias = pd.to_numeric(df["dias_restantes"], errors="coerce")
                proximos = df[dias.between(0, 7)].copy().sort_values("dias_restantes")
                vencidos = df[dias < 0].copy().sort_values("dias_restantes")
                if excluir:
                    proximos = proximos[~proximos["id_interno_aviso"].astype(str).isin(excluir)]
                    vencidos = vencidos[~vencidos["id_interno_aviso"].astype(str).isin(excluir)]
            else:
                proximos = vencidos = pd.DataFrame()

            # Seguimiento de enviados manuales
            self._enviados    = list_seguimiento(self.settings)
            self._historial   = list_historial(self.settings)
            self._descartados = list_descartados(self.settings)

            self._proximos = proximos
            self._vencidos = vencidos
            self.window.after(0, self._render_tabs)
        except Exception as exc:
            self.window.after(0, lambda: self._status_var.set(f"Error: {exc}"))

    def _render_tabs(self) -> None:
        n_prox = len(self._proximos)
        n_venc = len(self._vencidos)
        n_env  = len(self._enviados)
        n_hist = len(self._historial)
        n_desc = len(self._descartados)
        self._status_var.set(
            f"{n_prox} próximos  ·  {n_venc} vencidos  ·  {n_env} enviados  ·  {n_desc} desestimados"
        )
        self._notebook.tab(0, text=f"  Próximos a vencer ({n_prox})  ")
        self._notebook.tab(1, text=f"  Vencidos ({n_venc})  ")
        self._notebook.tab(2, text=f"  Enviados ({n_env})  ")
        self._notebook.tab(3, text=f"  Historial ({n_hist})  ")
        self._notebook.tab(4, text=f"  Desestimados ({n_desc})  ")
        self._build_table(self._tab_proximos, self._proximos)
        self._build_table(self._tab_vencidos, self._vencidos)
        self._build_enviados_table(self._tab_enviados, self._enviados)
        self._build_historial_table(self._tab_historial, self._historial)
        self._build_descartados_table(self._tab_descartados, self._descartados)

    def _build_table(self, parent: ttk.Frame, df: pd.DataFrame) -> None:
        for w in parent.winfo_children():
            w.destroy()

        if df.empty:
            ttk.Label(parent, text="Sin registros.", style="Muted.TLabel").pack(pady=30)
            return

        from app.notifier_whatsapp import normalize_phone

        # ── Barra de celda (tipo barra de fórmulas de Excel) ──────────────────
        cell_bar = tk.Frame(parent, bg=C_CARD,
                            highlightbackground=C_BORDER, highlightthickness=1)
        cell_bar.pack(fill=tk.X, padx=2, pady=(2, 0))
        tk.Label(cell_bar, text="Celda:", bg=C_CARD, fg=C_TEXT_MUTED,
                 font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(8, 4), pady=4)
        cell_var = tk.StringVar()
        cell_entry = ttk.Entry(cell_bar, textvariable=cell_var, font=(FONT_FAMILY, 10))
        cell_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=4)

        # ── Treeview ──────────────────────────────────────────────────────────
        tree_frame = tk.Frame(parent, bg=C_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("cliente", "serial", "fecha", "dias", "telefono")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        tree.heading("cliente",  text="Cliente",         anchor=tk.W)
        tree.heading("serial",   text="Serial / Equipo", anchor=tk.W)
        tree.heading("fecha",    text="Fecha estimada",  anchor=tk.W)
        tree.heading("dias",     text="Días",            anchor=tk.W)
        tree.heading("telefono", text="Teléfono",        anchor=tk.W)

        tree.column("cliente",  width=240, minwidth=120, stretch=True)
        tree.column("serial",   width=170, minwidth=80,  stretch=True)
        tree.column("fecha",    width=120, minwidth=100, stretch=False)
        tree.column("dias",     width=100, minwidth=80,  stretch=False)
        tree.column("telefono", width=160, minwidth=100, stretch=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree.tag_configure("vencido", foreground="#C62828")
        tree.tag_configure("hoy",     foreground=C_WARNING)
        tree.tag_configure("proximo", foreground=C_WARNING)
        tree.tag_configure("ok",      foreground=C_SUCCESS)
        tree.tag_configure("odd",     background="#F5F7FA")

        # Poblar e indexar filas
        _row_index: dict[str, pd.Series] = {}
        for i, (_, row) in enumerate(df.iterrows()):
            iid = str(row.get("id_interno_aviso") or i)
            fecha = row.get("fecha_estimada_proximo_service", "")
            fecha_str = fecha.strftime("%d/%m/%Y") if hasattr(fecha, "strftime") else str(fecha or "")
            try:
                dias_int = int(float(row.get("dias_restantes", "")))
                if dias_int < 0:
                    dias_txt, color_tag = f"{abs(dias_int)}d vencido", "vencido"
                elif dias_int == 0:
                    dias_txt, color_tag = "Hoy", "hoy"
                else:
                    dias_txt, color_tag = f"en {dias_int}d", ("proximo" if dias_int <= 3 else "ok")
            except (ValueError, TypeError):
                dias_txt, color_tag = "", ""
            tel = str(row.get("telefono_cliente", "") or "")
            tags = (color_tag, "odd") if (color_tag and i % 2 != 0) else \
                   (color_tag,) if color_tag else \
                   ("odd",) if i % 2 != 0 else ()
            tree.insert("", tk.END, iid=iid, values=(
                str(row.get("cliente", "")),
                str(row.get("serial", "")),
                fecha_str, dias_txt, tel,
            ), tags=tags)
            _row_index[iid] = row

        # Click en celda → muestra valor en barra de celda, seleccionado para copiar
        def _on_cell_click(event=None):
            region = tree.identify_region(event.x, event.y)
            if region != "cell":
                return
            col_id  = tree.identify_column(event.x)   # '#1', '#2', ...
            row_iid = tree.identify_row(event.y)
            if not row_iid:
                return
            col_idx = int(col_id.replace("#", "")) - 1
            values  = tree.item(row_iid, "values")
            if 0 <= col_idx < len(values):
                cell_var.set(str(values[col_idx]))
                cell_entry.after(10, lambda: (
                    cell_entry.focus_set(),
                    cell_entry.selection_range(0, tk.END),
                ))
        tree.bind("<ButtonRelease-1>", _on_cell_click)

        # Ctrl+C copia la fila entera al portapapeles
        def _copy_row(event=None):
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0], "values")
                tree.clipboard_clear()
                tree.clipboard_append("\t".join(str(v) for v in vals))
        tree.bind("<Control-c>", _copy_row)

        # ── Panel de acción ────────────────────────────────────────────────────
        action = tk.Frame(parent, bg=C_CARD,
                          highlightbackground=C_BORDER, highlightthickness=1)
        action.pack(fill=tk.X, padx=2, pady=(4, 2))

        hint = tk.Label(action, text="Seleccioná una fila para editar teléfono o enviar aviso.",
                        bg=C_CARD, fg=C_TEXT_MUTED, font=(FONT_FAMILY, 9))
        hint.pack(side=tk.LEFT, padx=12, pady=7)

        info_lbl = tk.Label(action, text="", bg=C_CARD, fg=C_TEXT,
                            font=(FONT_FAMILY, 10, "bold"))

        tk.Label(action, text="Teléfono:", bg=C_CARD, fg=C_TEXT,
                 font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=(10, 4), pady=7)
        phone_var = tk.StringVar()
        ttk.Entry(action, textvariable=phone_var, width=20).pack(side=tk.LEFT, padx=4, pady=7)

        save_btn = ttk.Button(action, text="💾", style="Outline.TButton",
                              width=3, state=tk.DISABLED)
        save_btn.pack(side=tk.LEFT, padx=(0, 4), pady=7)

        send_btn = ttk.Button(action, text="Enviar aviso", style="Primary.TButton",
                              state=tk.DISABLED)
        send_btn.pack(side=tk.LEFT, padx=4, pady=7)

        desest_btn = ttk.Button(action, text="✕  Desestimar", style="Danger.TButton",
                                state=tk.DISABLED)
        desest_btn.pack(side=tk.LEFT, padx=(12, 4), pady=7)

        _sel: dict = {"iid": None}

        def _on_select(event=None):
            sel = tree.selection()
            if not sel or sel[0] == _sel["iid"]:
                return
            _sel["iid"] = sel[0]
            row = _row_index.get(sel[0])
            if row is None:
                return

            hint.pack_forget()
            info_lbl.config(text=f"{row.get('cliente', '')}  ·  {row.get('serial', '')}")
            info_lbl.pack(side=tk.LEFT, padx=(12, 8), pady=7)

            phone_var.set(str(row.get("telefono_cliente", "") or ""))
            aviso_id   = str(row.get("id_interno_aviso", "") or "")
            id_empresa = row.get("id_empresa", None)

            save_btn.configure(
                state=tk.NORMAL,
                command=lambda: self._save_phone_local(
                    phone_var.get().strip(), aviso_id, id_empresa),
            )
            send_btn.configure(
                state=tk.NORMAL,
                command=lambda r=row: self._enviar(
                    r,
                    normalize_phone(phone_var.get().strip(), self.settings.whatsapp_country_prefix),
                    12 <= len(normalize_phone(phone_var.get().strip(), self.settings.whatsapp_country_prefix)) <= 13,
                ),
            )
            aviso_id = str(row.get("id_interno_aviso", "") or "")
            desest_btn.configure(
                state=tk.NORMAL,
                command=lambda aid=aviso_id, r=row: self._desestimar(aid, r),
            )

        tree.bind("<<TreeviewSelect>>", _on_select)

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
                    mensaje=msg,
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
                    command=lambda sid=seg_id: self._confirmar_coordinado(sid),
                ).pack(side=tk.LEFT, padx=(4, 2))
                ttk.Button(
                    f, text="✗", style="Danger.TButton", width=3,
                    command=lambda sid=seg_id: self._update_seguimiento(sid, "sin_respuesta"),
                ).pack(side=tk.LEFT, padx=(2, 8))
            elif estado == "sin_respuesta":
                tk.Label(
                    f, text=_LABEL_ESTADO.get(estado, estado),
                    bg=bg, fg=_FG_ESTADO.get(estado, C_TEXT),
                    font=(FONT_FAMILY, 10, "bold"), anchor="w", width=16,
                ).pack(side=tk.LEFT, padx=(4, 2))
                ttk.Button(
                    f, text="↻  Reenviar", style="Primary.TButton", width=12,
                    command=lambda sid=seg_id: self._reenviar(sid),
                ).pack(side=tk.LEFT, padx=(2, 8))
            else:
                tk.Label(
                    f, text=_LABEL_ESTADO.get(estado, estado),
                    bg=bg, fg=_FG_ESTADO.get(estado, C_TEXT),
                    font=(FONT_FAMILY, 10, "bold"), anchor="w", width=16,
                ).pack(side=tk.LEFT, padx=(4, 8))

            # Marca de cuantas veces se reenvio
            try:
                reenvios = int(row.get("reenvios", 0) or 0)
            except (TypeError, ValueError):
                reenvios = 0
            if reenvios:
                tk.Label(
                    f, text=f"↻ {reenvios}", bg=bg, fg=C_WARNING,
                    font=(FONT_FAMILY, 9, "bold"), anchor="w", width=5,
                ).pack(side=tk.LEFT, padx=(0, 4))

    def _reenviar(self, seguimiento_id: int) -> None:
        """Reenvia el aviso a un cliente que no respondio.

        Repite el mismo texto que se envio la primera vez. Si ese registro es
        viejo y no tiene el mensaje guardado, lo reconstruye con los datos
        disponibles.
        """
        registro = get_seguimiento(self.settings, seguimiento_id)
        if registro is None:
            messagebox.showerror("Reenviar", "No se encontró el registro.", parent=self.window)
            return

        tel = str(registro.get("telefono", "") or "").strip()
        if not tel:
            messagebox.showwarning(
                "Sin teléfono",
                "Este registro no tiene teléfono cargado.",
                parent=self.window,
            )
            return

        mensaje = str(registro.get("mensaje", "") or "").strip()
        if not mensaje:
            mensaje = self._reconstruir_mensaje(registro)

        reenvios = int(registro.get("reenvios", 0) or 0)
        cliente = str(registro.get("cliente", ""))
        equipo = str(registro.get("equipo", "") or registro.get("serial", ""))

        aviso_previo = ""
        if reenvios:
            aviso_previo = f"\n\nYa se le reenvió {reenvios} vez/veces."

        if not self._confirmar_reenvio(cliente, equipo, tel, mensaje, aviso_previo):
            return

        def _send() -> None:
            try:
                from app.notifier_whatsapp import send_whatsapp_text
                send_whatsapp_text(tel, mensaje, self.settings)
                total = registrar_reenvio(self.settings, seguimiento_id)
                self.window.after(0, self._refresh)
                self.window.after(0, lambda: messagebox.showinfo(
                    "Reenviado",
                    f"Mensaje reenviado a +{tel}.\n\n"
                    f"Reenvíos de este aviso: {total}\n"
                    "La fila volvió al estado Pendiente.",
                    parent=self.window,
                ))
            except Exception as exc:
                self.window.after(0, lambda: messagebox.showerror(
                    "Error al reenviar", str(exc), parent=self.window))

        threading.Thread(target=_send, daemon=True).start()

    def _reconstruir_mensaje(self, registro: dict) -> str:
        """Arma el mensaje para registros viejos que no lo tienen guardado."""
        from app.notifier_whatsapp import build_service_message

        fila = pd.Series({
            "equipo": registro.get("equipo", "") or registro.get("serial", ""),
            "serie_equipo": "",
            "marca_equipo": "",
            "modelo_equipo": "",
            "fecha_estimada_proximo_service": registro.get("fecha_estimada", ""),
        })
        return build_service_message(fila, operario_whatsapp=self.settings.operario_whatsapp)

    def _confirmar_reenvio(self, cliente: str, equipo: str, tel: str,
                           mensaje: str, aviso_previo: str) -> bool:
        """Dialog de confirmacion que muestra el texto exacto a reenviar."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Reenviar aviso")
        dialog.geometry("560x470")
        dialog.configure(bg=C_BG)
        dialog.transient(self.window)
        dialog.grab_set()
        _apply_styles(dialog)

        hdr = tk.Frame(dialog, bg=C_PRIMARY, height=38)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Reenviar aviso", bg=C_PRIMARY, fg="white",
                 font=(FONT_FAMILY, 11, "bold")).pack(side=tk.LEFT, padx=14, pady=7)

        info = tk.Frame(dialog, bg=C_BG)
        info.pack(fill=tk.X, padx=14, pady=(10, 4))
        for etiqueta, valor in (("Cliente", cliente), ("Equipo", equipo), ("Teléfono", f"+{tel}")):
            fila = tk.Frame(info, bg=C_BG)
            fila.pack(fill=tk.X, pady=1)
            tk.Label(fila, text=f"{etiqueta}:", bg=C_BG, fg=C_TEXT_MUTED,
                     font=(FONT_FAMILY, 9, "bold"), width=10, anchor="w").pack(side=tk.LEFT)
            tk.Label(fila, text=valor, bg=C_BG, fg=C_TEXT,
                     font=(FONT_FAMILY, 10), anchor="w").pack(side=tk.LEFT)

        if aviso_previo.strip():
            tk.Label(dialog, text=aviso_previo.strip(), bg=C_BG, fg=C_WARNING,
                     font=(FONT_FAMILY, 9, "bold")).pack(anchor="w", padx=14, pady=(4, 0))

        tk.Label(dialog, text="Mensaje a enviar:", bg=C_BG, fg=C_TEXT_MUTED,
                 font=(FONT_FAMILY, 9, "bold")).pack(anchor="w", padx=14, pady=(10, 2))

        caja = tk.Text(dialog, font=(FONT_FAMILY, 9), bg=C_CARD, fg=C_TEXT,
                       relief="flat", wrap=tk.WORD, padx=10, pady=8, height=11,
                       highlightbackground=C_BORDER, highlightthickness=1)
        caja.pack(fill=tk.BOTH, expand=True, padx=14)
        caja.insert("1.0", mensaje)
        caja.configure(state=tk.DISABLED)

        resultado = {"ok": False}

        def _aceptar():
            resultado["ok"] = True
            dialog.destroy()

        botones = tk.Frame(dialog, bg=C_BG)
        botones.pack(fill=tk.X, padx=14, pady=12)
        ttk.Button(botones, text="Cancelar", style="Outline.TButton",
                   command=dialog.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(botones, text="↻  Reenviar ahora", style="Success.TButton",
                   command=_aceptar).pack(side=tk.RIGHT)

        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.bind("<Return>", lambda _e: _aceptar())
        dialog.wait_window()
        return resultado["ok"]

    def _confirmar_coordinado(self, seguimiento_id: int) -> None:
        """Abre un dialog para ingresar la fecha de asistencia antes de marcar como coordinado."""
        from datetime import date as _date
        dialog = tk.Toplevel(self.window)
        dialog.title("Coordinado")
        dialog.geometry("320x140")
        dialog.resizable(False, False)
        dialog.configure(bg=C_BG)
        dialog.grab_set()
        dialog.transient(self.window)
        _apply_styles(dialog)

        tk.Label(dialog, text="Fecha de asistencia coordinada:",
                 bg=C_BG, fg=C_TEXT, font=(FONT_FAMILY, 10)).pack(pady=(18, 4))

        fecha_var = tk.StringVar(value=_date.today().strftime("%d/%m/%Y"))
        ttk.Entry(dialog, textvariable=fecha_var, width=18,
                  font=(FONT_FAMILY, 11)).pack()

        def _confirmar():
            fecha = fecha_var.get().strip()
            if not fecha:
                messagebox.showwarning("Campo requerido", "Ingresá la fecha de asistencia.",
                                       parent=dialog)
                return
            try:
                update_seguimiento_estado(self.settings, seguimiento_id,
                                          "coordinado", fecha_coordinada=fecha)
                dialog.destroy()
                self._refresh()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dialog)

        btn_row = tk.Frame(dialog, bg=C_BG)
        btn_row.pack(pady=12)
        ttk.Button(btn_row, text="✓  Confirmar", style="Success.TButton",
                   command=_confirmar).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Cancelar", style="Outline.TButton",
                   command=dialog.destroy).pack(side=tk.LEFT, padx=6)

        dialog.bind("<Return>", lambda _: _confirmar())
        dialog.bind("<Escape>", lambda _: dialog.destroy())

    def _update_seguimiento(self, seguimiento_id: int, estado: str) -> None:
        try:
            update_seguimiento_estado(self.settings, seguimiento_id, estado)
            self._refresh()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self.window)

    def _build_historial_table(self, parent: ttk.Frame, df: pd.DataFrame) -> None:
        for w in parent.winfo_children():
            w.destroy()

        if df.empty:
            ttk.Label(parent, text="Sin envíos registrados.", style="Muted.TLabel").pack(pady=30)
            return

        # Cabecera
        hdr = tk.Frame(parent, bg="#ECEFF1")
        hdr.pack(fill=tk.X, padx=2, pady=(2, 0))
        for text, w in [
            ("Fecha envío", 17), ("Tipo", 9), ("Cliente", 22),
            ("Serial", 13), ("Teléfono", 13), ("Resultado", 14), ("Fecha service", 13), ("", 6),
        ]:
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

        _RES_LABEL = {
            "ENVIADO":       ("✓ Enviado",      C_SUCCESS),
            "coordinado":    ("✓ Coordinado",   C_SUCCESS),
            "sin_respuesta": ("✗ Sin respuesta","#C62828"),
            "pendiente":     ("· Pendiente",    C_TEXT_MUTED),
        }

        def _guardar_fecha(fuente: str, row_id: int, var: tk.StringVar) -> None:
            try:
                update_historial_fecha_coordinada(self.settings, fuente, row_id, var.get().strip())
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.window)

        for i, (_, row) in enumerate(df.iterrows()):
            resultado = str(row.get("resultado", ""))
            estado    = row.get("estado")
            tipo      = str(row.get("tipo", ""))
            fuente    = str(row.get("fuente", ""))
            row_id    = int(row.get("row_id", 0))

            # Clave de estado: para manuales usar estado de seguimiento
            if tipo == "Manual" and estado and str(estado) != "None":
                res_key = str(estado)
            else:
                res_key = resultado

            res_txt, res_fg = _RES_LABEL.get(res_key, (res_key, C_TEXT))

            if res_key == "sin_respuesta":
                bg = "#FFEBEE"
            elif res_key == "coordinado":
                bg = "#E8F5E9"
            else:
                bg = C_CARD if i % 2 == 0 else "#F5F7FA"

            fecha_raw = row.get("fecha_envio", "")
            try:
                fecha_str = pd.to_datetime(fecha_raw).strftime("%d/%m/%Y %H:%M")
            except Exception:
                fecha_str = str(fecha_raw or "")

            # Fecha coordinada existente
            fecha_coord_raw = str(row.get("fecha_coordinada", "") or "")

            f = tk.Frame(inner, bg=bg, pady=4)
            f.pack(fill=tk.X, padx=2, pady=1)

            tk.Label(f, text=fecha_str,                    bg=bg, fg=C_TEXT,      font=(FONT_FAMILY, 10), anchor="w", width=17).pack(side=tk.LEFT, padx=(8, 4))
            tk.Label(f, text=tipo,                         bg=bg, fg=C_TEXT_MUTED,font=(FONT_FAMILY, 9),  anchor="w", width=9).pack(side=tk.LEFT, padx=4)
            tk.Label(f, text=str(row.get("cliente", "")),  bg=bg, fg=C_TEXT,      font=(FONT_FAMILY, 10), anchor="w", width=22).pack(side=tk.LEFT, padx=4)
            tk.Label(f, text=str(row.get("serial", "")),   bg=bg, fg=C_TEXT,      font=(FONT_FAMILY, 10), anchor="w", width=13).pack(side=tk.LEFT, padx=4)
            tk.Label(f, text=str(row.get("telefono", "")), bg=bg, fg=C_TEXT,      font=(FONT_FAMILY, 10), anchor="w", width=13).pack(side=tk.LEFT, padx=4)
            tk.Label(f, text=res_txt,                      bg=bg, fg=res_fg,      font=(FONT_FAMILY, 10, "bold"), anchor="w", width=14).pack(side=tk.LEFT, padx=4)

            # Campo editable: fecha coordinada de asistencia
            fecha_coord_var = tk.StringVar(value=fecha_coord_raw)
            ttk.Entry(f, textvariable=fecha_coord_var, width=13,
                      font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=4)
            ttk.Button(
                f, text="💾", style="Outline.TButton", width=3,
                command=lambda fnt=fuente, rid=row_id, v=fecha_coord_var: _guardar_fecha(fnt, rid, v),
            ).pack(side=tk.LEFT, padx=(0, 8))

    def _desestimar(self, aviso_id: str, row: pd.Series) -> None:
        if not aviso_id:
            return
        if not messagebox.askyesno(
            "Desestimar service",
            "El service desaparecerá de Próximos/Vencidos.\n"
            "Podés restaurarlo desde la pestaña Desestimados.\n\n¿Continuar?",
            parent=self.window,
        ):
            return
        try:
            fecha = row.get("fecha_estimada_proximo_service", "")
            fecha_str = fecha.strftime("%Y-%m-%d") if hasattr(fecha, "strftime") else str(fecha or "")
            desestimar_service(
                self.settings, aviso_id,
                cliente=str(row.get("cliente", "") or ""),
                serial=str(row.get("serial", "") or ""),
                equipo=str(row.get("equipo", "") or ""),
                fecha_estimada=fecha_str,
            )
            self._refresh()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self.window)

    def _build_descartados_table(self, parent: ttk.Frame, df: pd.DataFrame) -> None:
        for w in parent.winfo_children():
            w.destroy()

        if df.empty:
            ttk.Label(parent, text="Sin services desestimados.", style="Muted.TLabel").pack(pady=30)
            return

        # Treeview
        tree_frame = tk.Frame(parent, bg=C_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("cliente", "serial", "fecha_service", "fecha_descarte")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        tree.heading("cliente",       text="Cliente",          anchor=tk.W)
        tree.heading("serial",        text="Serial / Equipo",  anchor=tk.W)
        tree.heading("fecha_service", text="Próximo service",  anchor=tk.W)
        tree.heading("fecha_descarte",text="Desestimado el",   anchor=tk.W)
        tree.column("cliente",        width=280, minwidth=120, stretch=True)
        tree.column("serial",         width=180, minwidth=80,  stretch=True)
        tree.column("fecha_service",  width=130, minwidth=100, stretch=False)
        tree.column("fecha_descarte", width=150, minwidth=100, stretch=False)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        _aviso_ids: dict[str, str] = {}
        for i, (_, row) in enumerate(df.iterrows()):
            aviso_id = str(row.get("aviso_id", "") or "")
            iid = aviso_id or str(i)
            fecha_s = str(row.get("fecha_estimada", "") or "")
            fecha_d = str(row.get("fecha_descarte", "") or "")
            try:
                fecha_s = pd.to_datetime(fecha_s).strftime("%d/%m/%Y")
            except Exception:
                pass
            try:
                fecha_d = pd.to_datetime(fecha_d).strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass
            serial_txt = str(row.get("serial", "") or row.get("equipo", "") or "")
            tree.insert("", tk.END, iid=iid, values=(
                str(row.get("cliente", "")),
                serial_txt,
                fecha_s, fecha_d,
            ), tags=("odd",) if i % 2 != 0 else ())
            _aviso_ids[iid] = aviso_id

        tree.tag_configure("odd", background="#F5F7FA")

        # Panel restaurar
        action = tk.Frame(parent, bg=C_CARD,
                          highlightbackground=C_BORDER, highlightthickness=1)
        action.pack(fill=tk.X, padx=2, pady=(4, 2))
        tk.Label(action, text="Seleccioná una fila para restaurar el service.",
                 bg=C_CARD, fg=C_TEXT_MUTED, font=(FONT_FAMILY, 9)).pack(
            side=tk.LEFT, padx=12, pady=7)
        rest_btn = ttk.Button(action, text="↺  Restaurar", style="Success.TButton",
                              state=tk.DISABLED)
        rest_btn.pack(side=tk.LEFT, padx=8, pady=7)

        def _on_select(event=None):
            sel = tree.selection()
            if not sel:
                return
            aid = _aviso_ids.get(sel[0], "")
            rest_btn.configure(
                state=tk.NORMAL,
                command=lambda a=aid: self._restaurar(a),
            )
        tree.bind("<<TreeviewSelect>>", _on_select)

    def _restaurar(self, aviso_id: str) -> None:
        try:
            restaurar_service(self.settings, aviso_id)
            self._refresh()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self.window)

    def _refresh(self) -> None:
        for tab in (self._tab_proximos, self._tab_vencidos, self._tab_enviados,
                    self._tab_historial, self._tab_descartados):
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
