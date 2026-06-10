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
from app.service_store import list_service_contacts, update_service_phone


class AppUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Alertas de services")
        self.root.geometry("820x600")
        self.root.minsize(720, 520)
        self.running = False

        today = date.today()
        self.month_var = tk.StringVar(value=str(today.month))
        self.year_var = tk.StringVar(value=str(today.year))
        self.status_var = tk.StringVar(value="Listo")

        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # --- Fila 1: proceso mensual ---
        monthly_frame = ttk.LabelFrame(frame, text="Proceso mensual", padding=(10, 6))
        monthly_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(monthly_frame, text="Mes").grid(row=0, column=0, sticky="w")
        month_combo = ttk.Combobox(
            monthly_frame,
            width=10,
            state="readonly",
            textvariable=self.month_var,
            values=[f"{month:02d} - {_month_name(month)}" for month in range(1, 13)],
        )
        month_combo.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
        month_combo.set(f"{int(self.month_var.get()):02d} - {_month_name(int(self.month_var.get()))}")

        ttk.Label(monthly_frame, text="Año").grid(row=0, column=1, sticky="w")
        current_year = date.today().year
        year_values = [str(year) for year in range(current_year - 5, current_year + 3)]
        year_combo = ttk.Combobox(
            monthly_frame,
            width=8,
            state="readonly",
            textvariable=self.year_var,
            values=year_values,
        )
        year_combo.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(4, 0))
        year_combo.set(self.year_var.get())

        self.generate_button = ttk.Button(
            monthly_frame,
            text="Generar Excel",
            command=lambda: self._start_task("generate_excel"),
        )
        self.generate_button.grid(row=1, column=2, padx=4, pady=(4, 0))

        self.test_button = ttk.Button(
            monthly_frame,
            text="Ejecutar prueba",
            command=lambda: self._start_task("test"),
        )
        self.test_button.grid(row=1, column=3, padx=4, pady=(4, 0))

        self.run_button = ttk.Button(
            monthly_frame,
            text="Ejecutar completo",
            command=lambda: self._start_task("run"),
        )
        self.run_button.grid(row=1, column=4, padx=4, pady=(4, 0))

        ttk.Button(monthly_frame, text="Abrir reportes", command=self._open_reports).grid(
            row=1, column=5, padx=(18, 4), pady=(4, 0)
        )
        ttk.Button(monthly_frame, text="Abrir logs", command=self._open_logs).grid(
            row=1, column=6, padx=4, pady=(4, 0)
        )
        ttk.Button(monthly_frame, text="Telefonos", command=self._open_contacts).grid(
            row=1, column=7, padx=4, pady=(4, 0)
        )

        # --- Fila 2: tarea diaria ---
        daily_frame = ttk.LabelFrame(frame, text="Tarea diaria", padding=(10, 6))
        daily_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            daily_frame,
            text="Revisa la base local y envia WhatsApp a clientes con services proximos a vencer (segun DIAS_ANTES_AVISO).",
            foreground="#555555",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        self.daily_button = ttk.Button(
            daily_frame,
            text="Enviar avisos",
            command=self._start_daily_task,
        )
        self.daily_button.grid(row=1, column=0, padx=(0, 8))

        self.daily_test_button = ttk.Button(
            daily_frame,
            text="Simular avisos (prueba)",
            command=self._start_daily_test_task,
        )
        self.daily_test_button.grid(row=1, column=1, padx=4)

        self.my_number_button = ttk.Button(
            daily_frame,
            text="Probar con mi numero",
            command=self._start_test_my_number,
        )
        self.my_number_button.grid(row=1, column=2, padx=(12, 0))

        # --- Status y log ---
        ttk.Label(
            frame,
            textvariable=self.status_var,
            foreground="#444444",
        ).pack(fill=tk.X, pady=(4, 6))

        self.output = scrolledtext.ScrolledText(frame, height=18, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True)
        self.output.configure(state=tk.DISABLED)

        self._write(
            "Proceso mensual: seleccione el periodo y ejecute una accion.\n"
            "  · Generar Excel no envia avisos.\n"
            "  · Ejecutar prueba simula WhatsApp sin enviar mensajes reales.\n"
            "  · Ejecutar completo usa la configuracion del .env.\n\n"
            "Tarea diaria: envia avisos a clientes con vencimientos proximos segun la base local.\n"
            "  · Probar con mi numero: envia el primer vencimiento a WHATSAPP_TEST_NUMBER (configurar en .env).\n"
        )

    def _start_task(self, action: str) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecucion activa.")
            return

        period = _build_period(self.year_var.get(), self.month_var.get())
        if period is None:
            messagebox.showerror("Periodo invalido", "Use formato YYYY-MM, por ejemplo 2025-12.")
            return

        if action == "run":
            settings = load_settings()
            if not settings.modo_prueba:
                confirm = messagebox.askyesno(
                    "Confirmar envio",
                    "MODO_PRUEBA=false. Esta accion puede enviar WhatsApp reales. Desea continuar?",
                )
                if not confirm:
                    return

        self.running = True
        self._set_buttons(False)
        self.status_var.set("Ejecutando...")
        self._write(f"\nIniciando accion: {action} | periodo: {period}\n")
        thread = threading.Thread(target=self._run_task, args=(action, period), daemon=True)
        thread.start()

    def _start_daily_task(self) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecucion activa.")
            return
        settings = load_settings()
        if not settings.modo_prueba:
            confirm = messagebox.askyesno(
                "Confirmar envio",
                "Esta accion enviara WhatsApp reales a los clientes con vencimientos proximos. Desea continuar?",
            )
            if not confirm:
                return
        self._launch_daily(force_test=False)

    def _start_daily_test_task(self) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecucion activa.")
            return
        self._launch_daily(force_test=True)

    def _start_test_my_number(self) -> None:
        if self.running:
            messagebox.showinfo("Proceso en curso", "Ya hay una ejecucion activa.")
            return
        settings = load_settings()
        if not settings.whatsapp_test_number:
            messagebox.showerror(
                "Numero no configurado",
                "Configure WHATSAPP_TEST_NUMBER en el archivo .env con su numero personal.\n"
                "Ejemplo: WHATSAPP_TEST_NUMBER=5491112345678",
            )
            return
        confirm = messagebox.askyesno(
            "Probar con mi numero",
            f"Se enviara el primer vencimiento pendiente a:\n{settings.whatsapp_test_number}\n\n"
            "Es un mensaje real. Desea continuar?",
        )
        if not confirm:
            return
        self.running = True
        self._set_buttons(False)
        self.status_var.set("Enviando prueba...")
        self._write(f"\nEnviando prueba a {settings.whatsapp_test_number}...\n")
        thread = threading.Thread(target=self._run_test_my_number, daemon=True)
        thread.start()

    def _launch_daily(self, force_test: bool) -> None:
        self.running = True
        self._set_buttons(False)
        label = "simulacion de tarea diaria" if force_test else "tarea diaria"
        self.status_var.set("Ejecutando...")
        self._write(f"\nIniciando {label}...\n")
        thread = threading.Thread(target=self._run_daily_task, args=(force_test,), daemon=True)
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
        for button in (
            self.generate_button, self.test_button, self.run_button,
            self.daily_button, self.daily_test_button, self.my_number_button,
        ):
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

    def _open_contacts(self) -> None:
        ContactsWindow(self.root)


class ContactsWindow:
    def __init__(self, parent: tk.Tk) -> None:
        self.settings = load_settings()
        self.window = tk.Toplevel(parent)
        self.window.title("Telefonos de clientes")
        self.window.geometry("960x520")
        self.window.minsize(820, 420)
        self.search_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.selected_aviso_id = ""
        self._build()
        self._load_contacts()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frame)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Buscar").pack(side=tk.LEFT)
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=34)
        search_entry.pack(side=tk.LEFT, padx=(8, 6))
        search_entry.bind("<Return>", lambda _event: self._load_contacts())
        ttk.Button(top, text="Buscar", command=self._load_contacts).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Actualizar", command=self._load_contacts).pack(side=tk.LEFT, padx=4)

        columns = (
            "cliente",
            "equipo",
            "serial",
            "lugar",
            "telefono",
            "vencimiento",
            "actualizado",
        )
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        headings = {
            "cliente": "Cliente",
            "equipo": "Equipo",
            "serial": "Serial",
            "lugar": "Lugar",
            "telefono": "Telefono",
            "vencimiento": "Proximo service",
            "actualizado": "Actualizado",
        }
        widths = {
            "cliente": 210,
            "equipo": 150,
            "serial": 130,
            "lugar": 70,
            "telefono": 130,
            "vencimiento": 115,
            "actualizado": 135,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=(12, 10))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        bottom = ttk.Frame(frame)
        bottom.pack(fill=tk.X)
        ttk.Label(bottom, text="Telefono").pack(side=tk.LEFT)
        ttk.Entry(bottom, textvariable=self.phone_var, width=24).pack(side=tk.LEFT, padx=(8, 6))
        ttk.Button(bottom, text="Guardar telefono", command=self._save_phone).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="Enviar aviso ahora", command=self._send_now).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Label(
            bottom,
            text="Formato recomendado: pais + area + numero, sin espacios.",
            foreground="#555555",
        ).pack(side=tk.LEFT, padx=(12, 0))

    def _load_contacts(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        contacts = list_service_contacts(self.settings, self.search_var.get())
        for _, row in contacts.iterrows():
            aviso_id = str(row.get("aviso_id", ""))
            self.tree.insert(
                "",
                tk.END,
                iid=aviso_id,
                values=(
                    row.get("cliente", ""),
                    row.get("equipo", ""),
                    row.get("serial", ""),
                    row.get("lugar", ""),
                    row.get("telefono_cliente", ""),
                    row.get("fecha_estimada_proximo_service", ""),
                    row.get("updated_at", ""),
                ),
            )

    def _on_select(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        self.selected_aviso_id = selected[0]
        values = self.tree.item(selected[0], "values")
        self.phone_var.set(values[4] if len(values) > 4 else "")

    def _save_phone(self) -> None:
        if not self.selected_aviso_id:
            messagebox.showinfo("Seleccion requerida", "Seleccione un registro de la lista.")
            return
        phone = self.phone_var.get().strip()
        try:
            update_service_phone(self.settings, self.selected_aviso_id, phone)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        self._load_contacts()
        messagebox.showinfo("Telefono guardado", "El telefono quedo guardado en la base local.")

    def _send_now(self) -> None:
        if not self.selected_aviso_id:
            messagebox.showinfo("Seleccion requerida", "Seleccione un registro de la lista.")
            return
        phone = self.phone_var.get().strip()
        if not phone:
            messagebox.showwarning("Sin telefono", "El cliente seleccionado no tiene telefono cargado.")
            return

        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        cliente = values[0] if len(values) > 0 else ""
        equipo  = values[1] if len(values) > 1 else ""
        serial  = values[2] if len(values) > 2 else ""
        venc    = values[5] if len(values) > 5 else ""

        confirm = messagebox.askyesno(
            "Confirmar envio",
            f"Enviar aviso de service a:\n\nCliente: {cliente}\nEquipo: {equipo}\nSerial: {serial}\nVencimiento: {venc}\nTelefono: {phone}",
        )
        if not confirm:
            return

        def _run():
            try:
                from app.notifier_whatsapp import build_service_message, normalize_phone, send_whatsapp_text
                import pandas as pd
                row = pd.Series({
                    "equipo": equipo,
                    "serial": serial,
                    "horas_actuales": "",
                    "fecha_estimada_proximo_service": venc,
                })
                message = build_service_message(row)
                dest = normalize_phone(phone, self.settings.whatsapp_country_prefix)
                send_whatsapp_text(dest, message, self.settings)
                self.window.after(0, lambda: messagebox.showinfo(
                    "Aviso enviado", f"Mensaje enviado correctamente a {dest}."
                ))
            except Exception as exc:
                self.window.after(0, lambda: messagebox.showerror("Error al enviar", str(exc)))

        threading.Thread(target=_run, daemon=True).start()


def _build_period(year_value: str, month_value: str) -> str | None:
    try:
        year = int(year_value.strip())
        month_text = month_value.split("-", 1)[0].strip()
        month = int(month_text)
    except Exception:
        return None
    if year < 1900 or year > 3000:
        return None
    if month < 1 or month > 12:
        return None
    return f"{year:04d}-{month:02d}"


def _month_name(month: int) -> str:
    names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }
    return names[month]


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
