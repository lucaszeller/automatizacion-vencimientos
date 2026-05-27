"""Interfaz grafica simple para ejecutar el control mensual."""

from __future__ import annotations

from datetime import date
from contextlib import redirect_stderr, redirect_stdout
import os
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from app.config import load_settings


class AppUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Alertas de services")
        self.root.geometry("820x560")
        self.root.minsize(720, 480)
        self.running = False

        self.period_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        self.status_var = tk.StringVar(value="Listo")

        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Periodo").grid(row=0, column=0, sticky="w")
        period_entry = ttk.Entry(controls, textvariable=self.period_var, width=12)
        period_entry.grid(row=1, column=0, sticky="w", padx=(0, 12), pady=(4, 0))

        self.generate_button = ttk.Button(
            controls,
            text="Generar Excel",
            command=lambda: self._start_task("generate_excel"),
        )
        self.generate_button.grid(row=1, column=1, padx=4, pady=(4, 0))

        self.test_button = ttk.Button(
            controls,
            text="Ejecutar prueba",
            command=lambda: self._start_task("test"),
        )
        self.test_button.grid(row=1, column=2, padx=4, pady=(4, 0))

        self.run_button = ttk.Button(
            controls,
            text="Ejecutar completo",
            command=lambda: self._start_task("run"),
        )
        self.run_button.grid(row=1, column=3, padx=4, pady=(4, 0))

        ttk.Button(controls, text="Abrir reportes", command=self._open_reports).grid(
            row=1, column=4, padx=(18, 4), pady=(4, 0)
        )
        ttk.Button(controls, text="Abrir logs", command=self._open_logs).grid(
            row=1, column=5, padx=4, pady=(4, 0)
        )

        ttk.Label(
            frame,
            textvariable=self.status_var,
            foreground="#444444",
        ).pack(fill=tk.X, pady=(14, 6))

        self.output = scrolledtext.ScrolledText(frame, height=20, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True)
        self.output.configure(state=tk.DISABLED)

        self._write(
            "Seleccione el periodo en formato YYYY-MM y ejecute una accion.\n"
            "Generar Excel no envia mails. Ejecutar prueba simula mails. Ejecutar completo usa la configuracion del .env.\n"
        )

    def _start_task(self, action: str) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecucion activa.")
            return

        period = self.period_var.get().strip()
        if not _valid_period(period):
            messagebox.showerror("Periodo invalido", "Use formato YYYY-MM, por ejemplo 2025-12.")
            return

        if action == "run":
            settings = load_settings()
            if not settings.modo_prueba:
                confirm = messagebox.askyesno(
                    "Confirmar envio",
                    "MODO_PRUEBA=false. Esta accion puede enviar mails reales. Desea continuar?",
                )
                if not confirm:
                    return

        self.running = True
        self._set_buttons(False)
        self.status_var.set("Ejecutando...")
        self._write(f"\nIniciando accion: {action} | periodo: {period}\n")
        thread = threading.Thread(target=self._run_task, args=(action, period), daemon=True)
        thread.start()

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

    def _task_done(self, exit_code: int) -> None:
        self.running = False
        self._set_buttons(True)
        if exit_code == 0:
            self.status_var.set("Proceso finalizado")
            self._write("Proceso finalizado correctamente.\n")
        else:
            self.status_var.set("Proceso finalizado con errores")
            self._write(f"Proceso finalizado con codigo {exit_code}.\n")

    def _task_failed(self, exc: Exception) -> None:
        self.running = False
        self._set_buttons(True)
        self.status_var.set("Error")
        self._write(f"ERROR: {exc}\n")
        messagebox.showerror("Error", str(exc))

    def _set_buttons(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in (self.generate_button, self.test_button, self.run_button):
            button.configure(state=state)

    def _write(self, text: str) -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def _open_reports(self) -> None:
        settings = load_settings()
        _open_folder(settings.output_dir)

    def _open_logs(self) -> None:
        settings = load_settings()
        _open_folder(settings.log_dir)


def _valid_period(value: str) -> bool:
    if len(value) != 7 or value[4] != "-":
        return False
    year, month = value.split("-", 1)
    if not (year.isdigit() and month.isdigit()):
        return False
    return 1 <= int(month) <= 12


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
