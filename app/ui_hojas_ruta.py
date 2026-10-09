"""Ventana de generacion de Hojas de Ruta.

Flujo:
  1. Lee los pedidos del Google Sheet
  2. Se filtra por mecanico y fecha programada
  3. Se marcan los pedidos a incluir (solo los aprobados)
  4. Se geocodifican los lugares y se optimiza el recorrido
  5. Se genera el PDF y se marca en el Sheet
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import pandas as pd

from app.config import load_settings


# Colores (mismos que ui.py, importados de forma perezosa para evitar ciclo)
def _paleta():
    from app import ui as _ui
    return _ui


class HojasRutaWindow:
    """Ventana para armar y generar hojas de ruta."""

    def __init__(self, parent: tk.Tk) -> None:
        U = _paleta()
        self.U = U
        self.parent = parent
        self.settings = load_settings()

        self.window = tk.Toplevel(parent)
        self.window.title("Hojas de Ruta")
        self.window.geometry("1240x680")
        self.window.minsize(980, 560)
        self.window.configure(bg=U.C_BG)
        U._apply_styles(self.window)

        self._status_var = tk.StringVar(value="Cargando pedidos del Sheet...")
        self._pedidos: pd.DataFrame = pd.DataFrame()
        self._filtrados: pd.DataFrame = pd.DataFrame()
        self._seleccion: set[int] = set()
        self._ultimo_pdf: Path | None = None

        self.mecanico_var = tk.StringVar(value="(todos)")
        self.fecha_var = tk.StringVar(value="(todas)")
        self.solo_aprobados_var = tk.BooleanVar(value=True)
        self.volver_taller_var = tk.BooleanVar(value=True)
        self.calendario_var = tk.BooleanVar(
            value=bool(self.settings.calendar_id_defecto or self.settings.calendar_mecanicos)
        )
        self.calendar_id_var = tk.StringVar(value="")

        self._build()
        self._recargar()

    # ------------------------------------------------------------- interfaz

    def _build(self) -> None:
        U = self.U

        hdr = tk.Frame(self.window, bg=U.C_PRIMARY, height=44)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Hojas de Ruta", bg=U.C_PRIMARY, fg="white",
                 font=(U.FONT_FAMILY, 12, "bold")).pack(side=tk.LEFT, padx=16, pady=8)

        # ── Barra de filtros ──────────────────────────────────────────────
        filtros = tk.Frame(self.window, bg=U.C_CARD,
                           highlightbackground=U.C_BORDER, highlightthickness=1)
        filtros.pack(fill=tk.X, padx=14, pady=(10, 0))

        fila = tk.Frame(filtros, bg=U.C_CARD)
        fila.pack(fill=tk.X, padx=12, pady=9)

        tk.Label(fila, text="MECÁNICO", bg=U.C_CARD, fg=U.C_TEXT_MUTED,
                 font=(U.FONT_FAMILY, 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.mecanico_combo = ttk.Combobox(
            fila, width=18, state="readonly", textvariable=self.mecanico_var,
            values=["(todos)"],
        )
        self.mecanico_combo.pack(side=tk.LEFT, padx=(0, 14))
        self.mecanico_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_mecanico())

        tk.Label(fila, text="FECHA", bg=U.C_CARD, fg=U.C_TEXT_MUTED,
                 font=(U.FONT_FAMILY, 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.fecha_combo = ttk.Combobox(
            fila, width=14, textvariable=self.fecha_var, values=["(todas)"],
        )
        self.fecha_combo.pack(side=tk.LEFT, padx=(0, 14))
        self.fecha_combo.bind("<<ComboboxSelected>>", lambda _e: self._aplicar_filtros())
        self.fecha_combo.bind("<Return>", lambda _e: self._aplicar_filtros())

        ttk.Checkbutton(fila, text="Solo aprobados", variable=self.solo_aprobados_var,
                        command=self._aplicar_filtros).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(fila, text="Volver al taller", variable=self.volver_taller_var,
                        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(fila, text="Subir a Calendar", variable=self.calendario_var,
                        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(fila, text="↺  Recargar Sheet", style="Outline.TButton",
                   command=self._recargar).pack(side=tk.RIGHT)

        # ── Fila 2: calendario destino ────────────────────────────────────
        tk.Frame(filtros, bg=U.C_BORDER, height=1).pack(fill=tk.X, padx=12)

        fila2 = tk.Frame(filtros, bg=U.C_CARD)
        fila2.pack(fill=tk.X, padx=12, pady=9)

        tk.Label(fila2, text="CALENDARIO", bg=U.C_CARD, fg=U.C_TEXT_MUTED,
                 font=(U.FONT_FAMILY, 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))

        self.calendar_entry = ttk.Entry(fila2, textvariable=self.calendar_id_var, width=52)
        self.calendar_entry.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(fila2, text="💾  Recordar", style="Outline.TButton",
                   command=self._guardar_calendario).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(fila2, text="Probar acceso", style="Outline.TButton",
                   command=self._probar_calendario).pack(side=tk.LEFT, padx=(0, 10))

        self.calendar_hint = tk.Label(
            fila2, text="", bg=U.C_CARD, fg=U.C_TEXT_MUTED,
            font=(U.FONT_FAMILY, 8),
        )
        self.calendar_hint.pack(side=tk.LEFT)

        # ── Estado ────────────────────────────────────────────────────────
        estado = ttk.Frame(self.window, style="TFrame")
        estado.pack(fill=tk.X, padx=14, pady=(8, 4))
        ttk.Label(estado, textvariable=self._status_var,
                  style="Status.TLabel").pack(side=tk.LEFT)

        # ── Tabla ─────────────────────────────────────────────────────────
        cont = ttk.Frame(self.window, style="TFrame")
        cont.pack(fill=tk.BOTH, expand=True, padx=14)

        columnas = ("sel", "soporte", "cliente", "lugar", "equipo", "tarea", "mecanico", "fecha")
        self.tree = ttk.Treeview(cont, columns=columnas, show="headings", selectmode="browse")

        encabezados = {
            "sel": ("", 34),
            "soporte": ("Soporte", 70),
            "cliente": ("Cliente", 190),
            "lugar": ("Lugar", 130),
            "equipo": ("Equipo", 150),
            "tarea": ("Tarea", 320),
            "mecanico": ("Mecánico", 100),
            "fecha": ("Fecha progr.", 90),
        }
        for col, (titulo, ancho) in encabezados.items():
            self.tree.heading(col, text=titulo)
            self.tree.column(col, width=ancho, minwidth=30,
                             anchor="center" if col in ("sel", "soporte", "fecha") else "w",
                             stretch=(col == "tarea"))

        vsb = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("taller", background="#FFF3E0")
        self.tree.tag_configure("odd", background="#F5F7FA")
        self.tree.tag_configure("sinaprobar", foreground="#90A4AE")

        self.tree.bind("<ButtonRelease-1>", self._on_click)
        self.tree.bind("<space>", lambda _e: self._toggle_actual())

        # ── Acciones ──────────────────────────────────────────────────────
        acciones = tk.Frame(self.window, bg=U.C_CARD,
                            highlightbackground=U.C_BORDER, highlightthickness=1)
        acciones.pack(fill=tk.X, padx=14, pady=10)

        barra = tk.Frame(acciones, bg=U.C_CARD)
        barra.pack(fill=tk.X, padx=12, pady=9)

        ttk.Button(barra, text="Marcar todos", style="Outline.TButton",
                   command=lambda: self._marcar_todos(True)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(barra, text="Desmarcar", style="Outline.TButton",
                   command=lambda: self._marcar_todos(False)).pack(side=tk.LEFT, padx=4)

        ttk.Separator(barra, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=2)

        self.resumen_var = tk.StringVar(value="0 seleccionados")
        tk.Label(barra, textvariable=self.resumen_var, bg=U.C_CARD, fg=U.C_TEXT,
                 font=(U.FONT_FAMILY, 9, "bold")).pack(side=tk.LEFT)

        self.abrir_btn = ttk.Button(barra, text="📂  Abrir carpeta", style="Outline.TButton",
                                    command=self._abrir_carpeta)
        self.abrir_btn.pack(side=tk.RIGHT, padx=(4, 0))

        self.generar_btn = ttk.Button(barra, text="🗺  Generar hoja de ruta",
                                      style="Success.TButton", command=self._generar)
        self.generar_btn.pack(side=tk.RIGHT, padx=4)

        self.previsualizar_btn = ttk.Button(barra, text="Previsualizar recorrido",
                                            style="Primary.TButton", command=self._previsualizar)
        self.previsualizar_btn.pack(side=tk.RIGHT, padx=4)

    # ------------------------------------------------------------- datos

    def _recargar(self) -> None:
        self._status_var.set("Leyendo Google Sheet...")
        self._set_botones(False)
        threading.Thread(target=self._cargar_worker, daemon=True).start()

    def _cargar_worker(self) -> None:
        try:
            from app.lector_pedidos import leer_pedidos
            df = leer_pedidos(self.settings)
            self.window.after(0, lambda: self._cargado(df))
        except Exception as exc:  # noqa: BLE001
            mensaje = f"{type(exc).__name__}: {exc}"
            self.window.after(0, lambda: self._error_carga(mensaje))

    def _error_carga(self, mensaje: str) -> None:
        self._status_var.set(f"Error leyendo el Sheet: {mensaje[:160]}")
        self._set_botones(True)
        messagebox.showerror(
            "No se pudo leer el Sheet",
            f"{mensaje}\n\nRevisá que:\n"
            "• El JSON de credenciales esté en credenciales/\n"
            "• El Sheet esté compartido con el service account\n"
            "• SHEET_PEDIDOS_ID esté cargado en el .env",
            parent=self.window,
        )

    def _cargado(self, df: pd.DataFrame) -> None:
        self._pedidos = df
        self._seleccion.clear()

        mecanicos = ["(todos)"]
        fechas = ["(todas)"]
        if not df.empty:
            mecanicos += sorted({m for m in df["mecanico"] if str(m).strip()})
            fechas += sorted({f for f in df["fecha_programada"] if str(f).strip()},
                             reverse=True)
        self.mecanico_combo.configure(values=mecanicos)
        self.fecha_combo.configure(values=fechas)
        if self.mecanico_var.get() not in mecanicos:
            self.mecanico_var.set("(todos)")

        self._set_botones(True)
        self._cargar_calendario_de_mecanico()
        self._aplicar_filtros()

    # ------------------------------------------------------- calendario

    def _on_mecanico(self) -> None:
        """Al cambiar de mecanico: recargar su calendario recordado."""
        self._cargar_calendario_de_mecanico()
        self._aplicar_filtros()

    def _mecanico_actual(self) -> str:
        """Mecanico efectivo: el del filtro, o el unico de la selección."""
        elegido = self.mecanico_var.get().strip()
        if elegido and elegido != "(todos)":
            return elegido
        df = self._seleccionados()
        if df.empty:
            return ""
        mecanicos = {m.strip() for m in df["mecanico"] if str(m).strip()}
        return mecanicos.pop() if len(mecanicos) == 1 else ""

    def _cargar_calendario_de_mecanico(self) -> None:
        mecanico = self.mecanico_var.get().strip()
        por_defecto = not mecanico or mecanico == "(todos)"

        try:
            from app.calendario import leer_calendario_defecto, leer_calendario_mecanico
            propio = "" if por_defecto else leer_calendario_mecanico(self.settings, mecanico)
            general = leer_calendario_defecto(self.settings)
        except Exception:  # noqa: BLE001
            propio = general = ""

        if propio:
            self.calendar_id_var.set(propio)
            self._hint(f"Calendario propio de {mecanico}")
        elif general:
            self.calendar_id_var.set(general)
            self._hint("Calendario por defecto" if por_defecto
                       else f"{mecanico} usa el calendario por defecto")
        else:
            self.calendar_id_var.set(self.settings.calendar_id_defecto or "")
            self._hint("Pegá el ID del calendario y dale Recordar")

    def _hint(self, texto: str, error: bool = False) -> None:
        U = self.U
        self.calendar_hint.configure(
            text=texto, fg=(U.C_DOT_ERROR if error else U.C_TEXT_MUTED)
        )

    def _guardar_calendario(self) -> None:
        mecanico = self.mecanico_var.get().strip()
        por_defecto = not mecanico or mecanico == "(todos)"
        calendar_id = self.calendar_id_var.get().strip()

        if por_defecto and calendar_id:
            if not messagebox.askyesno(
                "Calendario por defecto",
                "No hay ningún mecánico seleccionado.\n\n"
                "¿Guardarlo como calendario por defecto?\n"
                "Se va a usar para todos los mecánicos que no tengan uno propio.",
                parent=self.window,
            ):
                return

        try:
            from app.calendario import guardar_calendario_mecanico
            guardar_calendario_mecanico(
                self.settings, "" if por_defecto else mecanico, calendar_id
            )
        except Exception as exc:  # noqa: BLE001
            self._hint(f"No se pudo guardar: {exc}", error=True)
            return

        quien = "por defecto" if por_defecto else mecanico
        if calendar_id:
            self._hint(f"Guardado como calendario {quien}")
        else:
            self._hint(f"Se borró el calendario {quien}")

    def _probar_calendario(self) -> None:
        calendar_id = self.calendar_id_var.get().strip()
        if not calendar_id:
            self._hint("Escribí el mail o ID del calendario", error=True)
            return
        self._hint("Verificando acceso...")
        threading.Thread(
            target=lambda: self._probar_calendario_worker(calendar_id), daemon=True
        ).start()

    def _probar_calendario_worker(self, calendar_id: str) -> None:
        try:
            from app.calendario import API_BASE, _sesion
            sesion, email_sa = _sesion(self.settings)
            respuesta = sesion.get(f"{API_BASE}/calendars/{calendar_id}", timeout=30)
            if respuesta.status_code == 200:
                nombre = respuesta.json().get("summary", calendar_id)
                self.window.after(0, lambda: self._hint(f"✓ Acceso OK — {nombre}"))
            elif respuesta.status_code in (403, 404):
                self.window.after(0, lambda: self._sin_acceso(calendar_id, email_sa))
            else:
                codigo = respuesta.status_code
                self.window.after(
                    0, lambda: self._hint(f"Respuesta {codigo}", error=True)
                )
        except Exception as exc:  # noqa: BLE001
            texto = f"{type(exc).__name__}: {exc}"
            self.window.after(0, lambda: self._hint(texto[:90], error=True))

    def _sin_acceso(self, calendar_id: str, email_sa: str) -> None:
        self._hint("Sin acceso a ese calendario", error=True)
        messagebox.showwarning(
            "Sin acceso al calendario",
            f"No se puede escribir en:\n{calendar_id}\n\n"
            "En Google Calendar, en ese calendario:\n"
            "  ⋮ → Configuración y uso compartido\n"
            "  → Compartir con determinadas personas → Añadir\n\n"
            f"{email_sa}\n\n"
            "Permiso: 'Realizar cambios en los eventos'",
            parent=self.window,
        )

    def _aplicar_filtros(self) -> None:
        df = self._pedidos
        if df.empty:
            self._filtrados = df
            self._pintar()
            return

        filtrado = df.copy()
        self._descartes: list[str] = []

        def aplicar(mascara, etiqueta: str):
            nonlocal filtrado
            antes = len(filtrado)
            filtrado = filtrado[mascara]
            quitados = antes - len(filtrado)
            if quitados:
                self._descartes.append(f"{etiqueta}: −{quitados}")

        mecanico = self.mecanico_var.get().strip()
        if mecanico and mecanico != "(todos)":
            aplicar(filtrado["mecanico"].str.strip() == mecanico, f"mecánico «{mecanico}»")

        fecha = self.fecha_var.get().strip()
        if fecha and fecha != "(todas)":
            aplicar(filtrado["fecha_programada"].str.strip() == fecha, f"fecha «{fecha}»")

        if self.solo_aprobados_var.get() and "esta_aprobado" in filtrado.columns:
            aplicar(filtrado["esta_aprobado"], "solo aprobados")

        self._filtrados = filtrado.reset_index(drop=True)
        # Al filtrar, preseleccionar todo lo visible
        self._seleccion = set(self._filtrados["fila"].tolist())
        self._pintar()

    def _columnas_faltantes(self) -> list[str]:
        """Columnas que el Sheet no tiene (o tiene totalmente vacias)."""
        df = self._pedidos
        if df.empty:
            return []
        etiquetas = {
            "fecha_programada": "«Fecha programada»",
            "aprobado": "«Aprobado»",
            "estado_hr": "«Estado HR»",
        }
        return [
            texto for campo, texto in etiquetas.items()
            if campo in df.columns and df[campo].astype(str).str.strip().eq("").all()
        ]

    def _pintar(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        df = self._filtrados
        if df.empty:
            detalle = ""
            descartes = getattr(self, "_descartes", [])
            if descartes:
                detalle = "  ·  descartados por → " + ", ".join(descartes)
            faltantes = self._columnas_faltantes()
            if faltantes:
                detalle += (
                    "  ·  el Sheet no tiene la columna "
                    + ", ".join(faltantes)
                )
            self._status_var.set(
                f"{len(self._pedidos)} pedidos en el Sheet  ·  ninguno pasa el filtro{detalle}"
            )
            self._actualizar_resumen()
            return

        for pos, fila in df.iterrows():
            numero = int(fila["fila"])
            marcado = "☑" if numero in self._seleccion else "☐"
            tags = []
            if fila.get("es_taller"):
                tags.append("taller")
            elif pos % 2:
                tags.append("odd")
            if not fila.get("esta_aprobado"):
                tags.append("sinaprobar")

            self.tree.insert(
                "", "end", iid=str(numero),
                values=(
                    marcado,
                    fila["numero_soporte"],
                    fila["cliente"],
                    fila["lugar"],
                    fila["equipo"],
                    (fila["tipo_servicio"] or "")[:200],
                    fila["mecanico"],
                    fila["fecha_programada"],
                ),
                tags=tuple(tags),
            )

        aprobados = int(df["esta_aprobado"].sum()) if "esta_aprobado" in df else 0
        taller = int(df["es_taller"].sum()) if "es_taller" in df else 0
        self._status_var.set(
            f"{len(self._pedidos)} pedidos en el Sheet  ·  {len(df)} en el filtro  ·  "
            f"{aprobados} aprobados  ·  {taller} en taller"
        )
        self._actualizar_resumen()

    # ---------------------------------------------------------- seleccion

    def _on_click(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        item = self.tree.identify_row(event.y)
        if item:
            self._toggle(int(item))

    def _toggle_actual(self) -> None:
        sel = self.tree.selection()
        if sel:
            self._toggle(int(sel[0]))

    def _toggle(self, numero_fila: int) -> None:
        if numero_fila in self._seleccion:
            self._seleccion.discard(numero_fila)
        else:
            self._seleccion.add(numero_fila)
        marcado = "☑" if numero_fila in self._seleccion else "☐"
        self.tree.set(str(numero_fila), "sel", marcado)
        self._actualizar_resumen()

    def _marcar_todos(self, valor: bool) -> None:
        if self._filtrados.empty:
            return
        filas = set(self._filtrados["fila"].tolist())
        self._seleccion = filas if valor else set()
        for item in self.tree.get_children():
            self.tree.set(item, "sel", "☑" if valor else "☐")
        self._actualizar_resumen()

    def _actualizar_resumen(self) -> None:
        n = len(self._seleccionados())
        self.resumen_var.set(f"{n} seleccionado{'s' if n != 1 else ''}")

    def _seleccionados(self) -> pd.DataFrame:
        if self._filtrados.empty:
            return self._filtrados
        return self._filtrados[self._filtrados["fila"].isin(self._seleccion)]

    # ------------------------------------------------------------ generar

    def _construir_ruta(self):
        """Geocodifica y optimiza. Devuelve (ruta, trabajos_taller, fallidos)."""
        from app.geocoder import GeocodeError, geocodificar, ubicacion_taller
        from app.ruteador import Parada, optimizar_ruta

        df = self._seleccionados()
        if df.empty:
            raise ValueError("No hay pedidos seleccionados.")

        origen = ubicacion_taller(self.settings)

        paradas: list[Parada] = []
        taller: list[Parada] = []
        fallidos: list[tuple[str, str]] = []
        sospechosos: list[str] = []
        self._sospechosos = sospechosos

        for _, fila in df.iterrows():
            base = dict(
                referencia=str(fila["numero_soporte"]),
                cliente=str(fila["cliente"]),
                lugar=str(fila["lugar"]),
                detalle=str(fila["tipo_servicio"]),
                contacto=str(fila["contacto"]),
                equipo=str(fila["equipo"]),
                extras=str(fila["extras"]),
            )
            if fila.get("es_taller"):
                taller.append(Parada(ubicacion=origen, **base))
                continue
            try:
                ubi = geocodificar(
                    self.settings,
                    str(fila["lugar"]),
                    str(fila.get("coordenadas", "")),
                    referencia=origen,
                )
                if ubi.sospechosa(self.settings.radio_alerta_km):
                    sospechosos.append(
                        f"{fila['numero_soporte']} · {fila['lugar']} "
                        f"→ a {ubi.km_referencia:.0f} km del taller"
                    )
            except GeocodeError as exc:
                fallidos.append((f"{fila['numero_soporte']} - {fila['lugar']}", str(exc)))
                continue
            except Exception as exc:  # noqa: BLE001
                fallidos.append((f"{fila['numero_soporte']} - {fila['lugar']}",
                                 f"{type(exc).__name__}: {exc}"))
                continue
            paradas.append(Parada(ubicacion=ubi, **base))

        ruta = optimizar_ruta(
            self.settings, origen, paradas,
            volver_al_taller=self.volver_taller_var.get(),
        )
        return ruta, taller, fallidos

    def _previsualizar(self) -> None:
        self._ejecutar_en_hilo(self._previsualizar_worker, "Calculando recorrido...")

    def _previsualizar_worker(self) -> None:
        from app.ruteador import formato_duracion
        ruta, taller, fallidos = self._construir_ruta()

        lineas = [f"TALLER  ({ruta.origen.etiqueta[:60]})"]
        for p in ruta.paradas:
            lineas.append(
                f"  {p.orden}.  {p.cliente[:32]:32s}  {p.lugar[:18]:18s}"
                f"  +{p.km_desde_anterior:6.0f} km   {formato_duracion(p.min_desde_anterior)}"
            )
        if self.volver_taller_var.get() and ruta.paradas:
            lineas.append(
                f"      regreso al taller{'':34s}+{ruta.km_regreso:6.0f} km"
                f"   {formato_duracion(ruta.min_regreso)}"
            )
        lineas.append("")
        lineas.append(
            f"TOTAL: {ruta.km_total:.0f} km  ·  {formato_duracion(ruta.min_conduccion)} de manejo"
        )
        if taller:
            lineas.append(f"Trabajos en taller (sin viaje): {len(taller)}")
        if ruta.aviso:
            lineas.append("")
            lineas.append(f"⚠ {ruta.aviso}")
        if fallidos:
            lineas.append("")
            lineas.append("No se pudo ubicar en el mapa:")
            for referencia, motivo in fallidos:
                lineas.append(f"  • {referencia}  →  {motivo[:70]}")

        sospechosos = getattr(self, "_sospechosos", [])
        if sospechosos:
            lineas.append("")
            lineas.append(f"!! Ubicaciones dudosas (a más de "
                          f"{self.settings.radio_alerta_km:.0f} km del taller):")
            for texto in sospechosos:
                lineas.append(f"  • {texto}")
            lineas.append("   Puede que el geocodificador haya agarrado otra localidad")
            lineas.append("   con el mismo nombre. Verificá y, si hace falta, cargá las")
            lineas.append("   coordenadas exactas en la columna 'Coordenadas' del Sheet.")

        if fallidos or sospechosos:
            lineas.append("")
            lineas.append("Para cargar coordenadas: click derecho en Google Maps sobre")
            lineas.append("el lugar → se copian los números → pegalos en 'Coordenadas'.")

        # Agenda estimada (mismos horarios que se subirian a Calendar)
        try:
            from app.calendario import construir_agenda, resumen_texto
            df = self._seleccionados()
            dia = _parsear_fecha(self.fecha_var.get()) or date.today()
            agenda = construir_agenda(self.settings, ruta, dia, taller)
            if agenda:
                lineas.append("")
                lineas.append("─" * 62)
                lineas.append("AGENDA ESTIMADA")
                lineas.append("─" * 62)
                lineas.append(resumen_texto(agenda, self.settings))
        except Exception as exc:  # noqa: BLE001
            lineas.append("")
            lineas.append(f"(No se pudo estimar la agenda: {exc})")

        texto = "\n".join(lineas)
        self.window.after(0, lambda: self._mostrar_preview(texto))

    def _mostrar_preview(self, texto: str) -> None:
        U = self.U
        dlg = tk.Toplevel(self.window)
        dlg.title("Recorrido optimizado")
        dlg.configure(bg=U.C_BG)
        dlg.geometry("820x460")
        dlg.transient(self.window)
        U._apply_styles(dlg)

        caja = tk.Text(dlg, font=("Consolas", 9), bg="#1E2A38", fg="#CFD8DC",
                       relief="flat", wrap=tk.NONE, padx=12, pady=10)
        caja.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        caja.insert("1.0", texto)
        caja.configure(state=tk.DISABLED)

        ttk.Button(dlg, text="Cerrar", style="Outline.TButton",
                   command=dlg.destroy).pack(pady=(0, 12))
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

    def _generar(self) -> None:
        df = self._seleccionados()
        if df.empty:
            messagebox.showinfo("Sin selección",
                                "Marcá al menos un pedido.", parent=self.window)
            return

        mecanico = self.mecanico_var.get().strip()
        if mecanico == "(todos)":
            mecanicos = {m.strip() for m in df["mecanico"] if str(m).strip()}
            if len(mecanicos) == 1:
                mecanico = mecanicos.pop()
            elif not mecanicos:
                mecanico = "Sin asignar"
            else:
                if not messagebox.askyesno(
                    "Varios mecánicos",
                    "La selección mezcla pedidos de: "
                    f"{', '.join(sorted(mecanicos))}.\n\n"
                    "Una hoja de ruta es el recorrido de UNA persona en un día.\n\n"
                    "¿Generarla igual, con todas las paradas juntas?",
                    parent=self.window,
                ):
                    return
                mecanico = " / ".join(sorted(mecanicos))

        dia = self._fecha_elegida(df)
        if dia is None:
            return

        self._ejecutar_en_hilo(
            lambda: self._generar_worker(mecanico, dia),
            "Generando hoja de ruta...",
        )

    def _fecha_elegida(self, df: pd.DataFrame) -> date | None:
        """Determina la fecha de la hoja de ruta a partir del filtro o del Sheet."""
        texto = self.fecha_var.get().strip()
        if texto and texto != "(todas)":
            parseada = _parsear_fecha(texto)
            if parseada:
                return parseada
        fechas = {f.strip() for f in df["fecha_programada"] if str(f).strip()}
        if len(fechas) == 1:
            parseada = _parsear_fecha(fechas.pop())
            if parseada:
                return parseada
        if messagebox.askyesno(
            "Fecha no definida",
            "Los pedidos no tienen una única fecha programada.\n\n"
            "¿Generar la hoja de ruta con la fecha de hoy?",
            parent=self.window,
        ):
            return date.today()
        return None

    def _generar_worker(self, mecanico: str, dia: date) -> None:
        from app.hoja_ruta import generar_pdf
        from app.lector_pedidos import marcar_hoja_generada

        ruta, taller, fallidos = self._construir_ruta()
        if not ruta.paradas and not taller:
            raise ValueError(
                "Ninguno de los pedidos seleccionados se pudo ubicar en el mapa."
            )

        destino = generar_pdf(self.settings, ruta, mecanico, dia, trabajos_taller=taller)
        self._ultimo_pdf = destino

        # Publicar en Google Calendar
        aviso_calendar = ""
        if self.calendario_var.get():
            self.window.after(0, lambda: self._status_var.set("Subiendo a Google Calendar..."))
            try:
                from app.calendario import publicar_agenda
                resultado = publicar_agenda(
                    self.settings, ruta, mecanico, dia,
                    trabajos_taller=taller,
                    calendar_id=self.calendar_id_var.get().strip(),
                )
                aviso_calendar = (
                    f"\n\nCalendar ({resultado.calendario}):"
                    f"\n  {resultado.creados} eventos creados"
                    + (f", {resultado.borrados} reemplazados" if resultado.borrados else "")
                )
            except Exception as exc:  # noqa: BLE001
                aviso_calendar = f"\n\nNo se pudo subir a Calendar:\n{str(exc)[:300]}"

        # Marcar en el Sheet los pedidos incluidos
        incluidos = [
            int(f) for f in self._seleccionados()["fila"].tolist()
        ]
        marca = f"HR {datetime.now():%d/%m/%Y %H:%M}"
        aviso_sheet = ""
        try:
            marcar_hoja_generada(self.settings, incluidos, marca)
        except Exception as exc:  # noqa: BLE001
            aviso_sheet = f"\n\nNo se pudo marcar el Sheet: {exc}"

        self.window.after(
            0, lambda: self._generado(destino, fallidos, aviso_sheet + aviso_calendar)
        )

    def _generado(self, destino: Path, fallidos: list, avisos: str) -> None:
        self._status_var.set(f"Hoja de ruta generada: {destino.name}")

        mensaje = f"Se generó:\n{destino.name}\n\nEn: {destino.parent}"
        if fallidos:
            mensaje += f"\n\nQuedaron afuera {len(fallidos)} pedidos sin ubicación:\n"
            mensaje += "\n".join(f"  • {r}" for r, _ in fallidos[:6])
        mensaje += avisos
        mensaje += "\n\n¿Abrir el PDF?"

        if messagebox.askyesno("Hoja de ruta lista", mensaje, parent=self.window):
            _abrir(destino)
        self._recargar()

    # ----------------------------------------------------------- utilidad

    def _ejecutar_en_hilo(self, funcion, mensaje: str) -> None:
        self._status_var.set(mensaje)
        self._set_botones(False)

        def correr() -> None:
            try:
                funcion()
            except Exception as exc:  # noqa: BLE001
                texto = f"{type(exc).__name__}: {exc}"
                self.window.after(0, lambda: self._fallo(texto))
            finally:
                self.window.after(0, lambda: self._set_botones(True))

        threading.Thread(target=correr, daemon=True).start()

    def _fallo(self, mensaje: str) -> None:
        self._status_var.set(f"Error: {mensaje[:150]}")
        messagebox.showerror("Error", mensaje, parent=self.window)

    def _set_botones(self, activos: bool) -> None:
        estado = "normal" if activos else "disabled"
        for boton in (self.generar_btn, self.previsualizar_btn):
            try:
                boton.configure(state=estado)
            except tk.TclError:
                pass

    def _abrir_carpeta(self) -> None:
        self.settings.hojas_ruta_dir.mkdir(parents=True, exist_ok=True)
        _abrir(self.settings.hojas_ruta_dir)


# ------------------------------------------------------------------ helpers


def _parsear_fecha(texto: str) -> date | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    for formato in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _abrir(ruta: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(ruta))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(ruta)])
        else:
            subprocess.Popen(["xdg-open", str(ruta)])
    except Exception:  # noqa: BLE001
        pass
