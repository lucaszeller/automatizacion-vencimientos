"""Optimizacion de recorrido para las hojas de ruta.

Dado el taller como punto de partida y N paradas de clientes, calcula el
orden de visita que minimiza el tiempo total de manejo.

Proveedor: OpenRouteService (gratis, sin tarjeta - openrouteservice.org)
    - /v2/matrix/driving-car  -> matriz de tiempos y distancias entre puntos
    - /v2/directions          -> geometria del recorrido (opcional)

Si no hay ORS_API_KEY configurada, cae en un modo offline que usa distancia
geodesica (haversine) en lugar de tiempo real de manejo. El orden resultante
sigue siendo razonable, solo que no considera las rutas reales.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt

from app.config import Settings
from app.geocoder import Ubicacion


ORS_MATRIX_URL = "https://api.openrouteservice.org/v2/matrix/driving-car"
ORS_MAX_PUNTOS = 50          # limite del plan gratuito de ORS para matrix
VELOCIDAD_ESTIMADA_KMH = 65  # usada solo en modo offline


@dataclass
class Parada:
    """Una visita dentro de la ruta."""
    referencia: str          # numero de soporte u otro identificador
    cliente: str
    lugar: str
    ubicacion: Ubicacion
    detalle: str = ""        # tipo de servicio / tareas
    contacto: str = ""
    equipo: str = ""
    extras: str = ""
    # completados por el optimizador:
    orden: int = 0
    km_desde_anterior: float = 0.0
    min_desde_anterior: float = 0.0


@dataclass
class Ruta:
    origen: Ubicacion
    paradas: list[Parada] = field(default_factory=list)
    km_total: float = 0.0
    min_conduccion: float = 0.0
    km_regreso: float = 0.0
    min_regreso: float = 0.0
    modo: str = "offline"    # "ors" | "offline"
    aviso: str = ""

    @property
    def cantidad(self) -> int:
        return len(self.paradas)


class RuteoError(RuntimeError):
    """Fallo el calculo de la ruta."""


# ------------------------------------------------------------ distancias


def haversine_km(a: Ubicacion, b: Ubicacion) -> float:
    """Distancia en linea recta entre dos puntos, en km."""
    radio = 6371.0
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    h = (
        sin(dlat / 2) ** 2
        + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    )
    return 2 * radio * asin(sqrt(h))


def _matriz_offline(puntos: list[Ubicacion]) -> tuple[list[list[float]], list[list[float]]]:
    """Matriz de distancias (km) y tiempos (min) estimados sin llamar a la API.

    Aplica un factor 1.3 sobre la distancia en linea recta para aproximar
    el recorrido real por ruta.
    """
    n = len(puntos)
    distancias = [[0.0] * n for _ in range(n)]
    tiempos = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            km = haversine_km(puntos[i], puntos[j]) * 1.3
            distancias[i][j] = km
            tiempos[i][j] = km / VELOCIDAD_ESTIMADA_KMH * 60
    return distancias, tiempos


def _matriz_ors(puntos: list[Ubicacion], api_key: str) -> tuple[list[list[float]], list[list[float]]]:
    """Matriz real de distancias y tiempos usando OpenRouteService."""
    import requests

    # ORS espera [lon, lat]
    coordenadas = [[p.lon, p.lat] for p in puntos]

    respuesta = requests.post(
        ORS_MATRIX_URL,
        json={
            "locations": coordenadas,
            "metrics": ["distance", "duration"],
            "units": "km",
        },
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        timeout=45,
    )

    if respuesta.status_code == 403:
        raise RuteoError("ORS rechazo la API key (403). Verifica ORS_API_KEY en el .env")
    if respuesta.status_code == 429:
        raise RuteoError("ORS: se supero el limite diario de requests (429). Reintenta manana.")
    if respuesta.status_code != 200:
        raise RuteoError(f"ORS respondio {respuesta.status_code}: {respuesta.text[:200]}")

    datos = respuesta.json()
    distancias = datos.get("distances")
    duraciones = datos.get("durations")
    if not distancias or not duraciones:
        raise RuteoError("ORS no devolvio matriz de distancias")

    # duraciones vienen en segundos -> minutos
    tiempos = [[(v or 0) / 60 for v in fila] for fila in duraciones]
    distancias = [[(v or 0) for v in fila] for fila in distancias]
    return distancias, tiempos


# ------------------------------------------------------------- heuristica


def _vecino_mas_cercano(costos: list[list[float]]) -> list[int]:
    """Orden inicial: desde el punto 0, ir siempre al no visitado mas cercano."""
    n = len(costos)
    pendientes = set(range(1, n))
    orden = [0]
    actual = 0
    while pendientes:
        siguiente = min(pendientes, key=lambda j: costos[actual][j])
        orden.append(siguiente)
        pendientes.remove(siguiente)
        actual = siguiente
    return orden


def _costo_total(orden: list[int], costos: list[list[float]], volver_al_origen: bool) -> float:
    total = sum(costos[orden[i]][orden[i + 1]] for i in range(len(orden) - 1))
    if volver_al_origen and len(orden) > 1:
        total += costos[orden[-1]][orden[0]]
    return total


def _dos_opt(orden: list[int], costos: list[list[float]], volver_al_origen: bool) -> list[int]:
    """Mejora el orden intercambiando tramos (2-opt) hasta que no haya mejora.

    El punto 0 (taller) queda siempre fijo al inicio.
    """
    mejor = orden[:]
    mejor_costo = _costo_total(mejor, costos, volver_al_origen)
    hubo_mejora = True
    while hubo_mejora:
        hubo_mejora = False
        for i in range(1, len(mejor) - 1):
            for j in range(i + 1, len(mejor)):
                candidato = mejor[:i] + mejor[i : j + 1][::-1] + mejor[j + 1 :]
                costo = _costo_total(candidato, costos, volver_al_origen)
                if costo < mejor_costo - 1e-9:
                    mejor, mejor_costo = candidato, costo
                    hubo_mejora = True
    return mejor


# --------------------------------------------------------------- publico


def optimizar_ruta(
    settings: Settings,
    origen: Ubicacion,
    paradas: list[Parada],
    volver_al_taller: bool = True,
) -> Ruta:
    """Calcula el mejor orden de visita para las paradas dadas.

    El origen (taller) es siempre la primera posicion. Si volver_al_taller
    es True, el costo del tramo de regreso se incluye en la optimizacion.
    """
    if not paradas:
        return Ruta(origen=origen, paradas=[], modo="offline", aviso="Sin paradas")

    if len(paradas) + 1 > ORS_MAX_PUNTOS:
        raise RuteoError(
            f"Demasiadas paradas ({len(paradas)}). El maximo por ruta es {ORS_MAX_PUNTOS - 1}. "
            "Divide el trabajo en mas de un dia o mecanico."
        )

    puntos = [origen] + [p.ubicacion for p in paradas]

    modo = "offline"
    aviso = ""
    api_key = (settings.ors_api_key or "").strip()
    if api_key:
        try:
            distancias, tiempos = _matriz_ors(puntos, api_key)
            modo = "ors"
        except RuteoError as exc:
            distancias, tiempos = _matriz_offline(puntos)
            aviso = f"Se uso estimacion offline: {exc}"
        except Exception as exc:  # noqa: BLE001
            distancias, tiempos = _matriz_offline(puntos)
            aviso = f"Se uso estimacion offline: {type(exc).__name__}: {exc}"
    else:
        distancias, tiempos = _matriz_offline(puntos)
        aviso = "Sin ORS_API_KEY: tiempos y distancias son estimados en linea recta."

    orden = _vecino_mas_cercano(tiempos)
    orden = _dos_opt(orden, tiempos, volver_al_taller)

    ordenadas: list[Parada] = []
    km_total = 0.0
    min_total = 0.0
    for posicion, indice in enumerate(orden[1:], start=1):
        anterior = orden[posicion - 1]
        parada = paradas[indice - 1]
        parada.orden = posicion
        parada.km_desde_anterior = round(distancias[anterior][indice], 1)
        parada.min_desde_anterior = round(tiempos[anterior][indice])
        km_total += parada.km_desde_anterior
        min_total += parada.min_desde_anterior
        ordenadas.append(parada)

    ruta = Ruta(
        origen=origen,
        paradas=ordenadas,
        km_total=round(km_total, 1),
        min_conduccion=round(min_total),
        modo=modo,
        aviso=aviso,
    )

    if volver_al_taller and orden:
        ultimo = orden[-1]
        ruta.km_regreso = round(distancias[ultimo][0], 1)
        ruta.min_regreso = round(tiempos[ultimo][0])
        ruta.km_total = round(ruta.km_total + ruta.km_regreso, 1)
        ruta.min_conduccion = round(ruta.min_conduccion + ruta.min_regreso)

    return ruta


def formato_duracion(minutos: float) -> str:
    """120 -> '2 h 00 min' ; 45 -> '45 min'"""
    minutos = int(round(minutos))
    if minutos < 60:
        return f"{minutos} min"
    horas, resto = divmod(minutos, 60)
    return f"{horas} h {resto:02d} min"


def link_google_maps(ruta: Ruta) -> str:
    """Genera un link de Google Maps con el recorrido completo.

    Sirve para que el mecanico abra la ruta en el celular desde el PDF.
    """
    if not ruta.paradas:
        return ""
    origen = f"{ruta.origen.lat},{ruta.origen.lon}"
    intermedias = [f"{p.ubicacion.lat},{p.ubicacion.lon}" for p in ruta.paradas]
    destino = intermedias[-1]
    waypoints = "|".join(intermedias[:-1])
    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origen}&destination={destino}&travelmode=driving"
    )
    if waypoints:
        url += f"&waypoints={waypoints}"
    return url
