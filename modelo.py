"""
modelo.py — Lógica CVRP para Florida Bebidas · Provincia Guanacaste
Algoritmo: Clarke-Wright Savings + 2-opt local search
Asignación de viajes a camiones: First-Fit Decreasing (FFD) por tiempo
"""

import itertools
import math
import numpy as np

# ─── DATOS BASE ───────────────────────────────────────────────────────────────

CAPACIDAD_CAMION = 24  # pallets

CANTONES = [
    {"id": 0,  "name": "CD Liberia (Depósito)", "demand": 0,  "lat": 10.6333, "lon": -85.4333},
    {"id": 1,  "name": "Liberia",               "demand": 60, "lat": 10.6333, "lon": -85.4393},
    {"id": 2,  "name": "Nicoya",                "demand": 49, "lat": 10.1500, "lon": -85.4500},
    {"id": 3,  "name": "Santa Cruz",            "demand": 55, "lat": 10.2667, "lon": -85.5833},
    {"id": 4,  "name": "Bagaces",               "demand": 17, "lat": 10.5167, "lon": -85.2500},
    {"id": 5,  "name": "Carrillo",              "demand": 36, "lat": 10.4333, "lon": -85.7000},
    {"id": 6,  "name": "Cañas",                 "demand": 24, "lat": 10.4000, "lon": -85.1167},
    {"id": 7,  "name": "Abangares",             "demand": 16, "lat": 10.2000, "lon": -84.9833},
    {"id": 8,  "name": "Tilarán",               "demand": 16, "lat": 10.4667, "lon": -84.9667},
    {"id": 9,  "name": "Nandayure",             "demand": 8,  "lat": 9.9833,  "lon": -85.2167},
    {"id": 10, "name": "La Cruz",               "demand": 20, "lat": 11.0667, "lon": -85.6167},
    {"id": 11, "name": "Hojancha",              "demand": 7,  "lat": 10.0833, "lon": -85.3000},
]

# Matriz de distancias por carretera (km) — fuente: Excel base UCR II-1122
# Fila/columna 0 = CD Liberia (depósito)
DIST_RAW = [
    [  0,  0, 70, 57, 30, 33, 57, 82, 71, 98,  69, 84],
    [  0,  0, 70, 57, 30, 33, 57, 82, 71, 98,  69, 84],
    [ 70, 70,  0, 25, 62, 39, 65, 58, 83, 37, 135, 15],
    [ 57, 57, 25,  0, 60, 25, 74, 76, 93, 62, 116, 39],
    [ 30, 30, 62, 60,  0, 38, 27, 54, 42, 79,  95, 73],
    [ 33, 33, 39, 25, 38,  0, 58, 70, 76, 72,  96, 54],
    [ 57, 57, 65, 74, 27, 58,  0, 31, 19, 68, 120, 71],
    [ 82, 82, 58, 76, 54, 70, 31,  0, 38, 44, 148, 57],
    [ 71, 71, 83, 93, 42, 76, 19, 38,  0, 81, 128, 88],
    [ 98, 98, 37, 62, 79, 72, 68, 44, 81,  0, 166, 26],
    [ 69, 69,135,116, 95, 96,120,148,128,166,   0,150],
    [ 84, 84, 15, 39, 73, 54, 71, 57, 88, 26, 150,  0],
]
DIST = np.array(DIST_RAW, dtype=float)

# ─── FUNCIONES DE DISTANCIA ───────────────────────────────────────────────────

def distancia_ruta(ruta, dist=DIST):
    """Calcula la distancia total de una ruta [0, c1, c2, ..., 0]."""
    return sum(dist[ruta[i]][ruta[i + 1]] for i in range(len(ruta) - 1))


def dos_opt(ruta, dist=DIST):
    """Mejora una ruta con 2-opt hasta convergencia local."""
    mejor = ruta[:]
    mejoro = True
    while mejoro:
        mejoro = False
        for i in range(1, len(mejor) - 2):
            for j in range(i + 1, len(mejor) - 1):
                nueva = mejor[:i] + mejor[i:j + 1][::-1] + mejor[j + 1:]
                if distancia_ruta(nueva, dist) < distancia_ruta(mejor, dist) - 1e-6:
                    mejor = nueva
                    mejoro = True
    return mejor


# ─── CLARKE-WRIGHT SAVINGS ────────────────────────────────────────────────────

def clarke_wright(nodos, demandas, dist, capacidad, deposito=0):
    """
    Heurística Clarke-Wright para CVRP con entregas divididas.

    Parámetros
    ----------
    nodos     : lista de IDs de nodo (incluye el depósito)
    demandas  : dict {nodo_id: demanda_pallets}
    dist      : matriz de distancias numpy (n x n)
    capacidad : capacidad máxima por viaje (pallets)
    deposito  : ID del nodo depósito (default 0)

    Retorna
    -------
    Lista de dicts con claves 'route', 'load', 'dist'
    Cada route es [deposito, ..., deposito]
    """
    clientes = [n for n in nodos if n != deposito]

    # Entregas divididas: cantones con demanda > capacidad generan varios viajes
    clientes_expandidos = []
    for c in clientes:
        d = demandas[c]
        idx = 0
        while d > 0:
            chunk = min(d, capacidad)
            clientes_expandidos.append((c, idx, chunk))
            d -= chunk
            idx += 1

    # Iniciar cada cliente expandido como ruta individual
    # Nodos internos usan clave (c, idx) de 2 elementos para consistencia
    rutas = [
        {"nodes": [deposito, (c, idx), deposito], "load": chunk}
        for c, idx, chunk in clientes_expandidos
    ]

    # Mapa de clave -> carga para lookup rápido
    clave_a_carga = {(c, idx): chunk for c, idx, chunk in clientes_expandidos}

    # Calcular ahorros s(i,j) = d(0,i) + d(0,j) - d(i,j)
    # Usando claves (c, idx) para identificar nodos en rutas
    claves = [(c, idx) for c, idx, _ in clientes_expandidos]
    ahorros = []
    for ka, kb in itertools.combinations(claves, 2):
        i, j = ka[0], kb[0]
        s = dist[deposito][i] + dist[deposito][j] - dist[i][j]
        ahorros.append((s, ka, kb))
    ahorros.sort(key=lambda x: -x[0])

    def buscar_ruta(clave):
        for r in rutas:
            if clave in r["nodes"][1:-1]:
                return r
        return None

    def es_extremo(ruta, clave):
        interior = ruta["nodes"][1:-1]
        return interior[0] == clave or interior[-1] == clave

    for s, ka, kb in ahorros:
        if s <= 0:
            break
        ra = buscar_ruta(ka)
        rb = buscar_ruta(kb)
        if ra is None or rb is None or ra is rb:
            continue
        if ra["load"] + rb["load"] > capacidad:
            continue
        if not es_extremo(ra, ka) or not es_extremo(rb, kb):
            continue

        ia = ra["nodes"][1:-1]
        ib = rb["nodes"][1:-1]
        ia_part = ia if ia[-1] == ka else ia[::-1]
        ib_part = ib if ib[0] == kb else ib[::-1]

        nueva_ruta = {
            "nodes": [deposito] + ia_part + ib_part + [deposito],
            "load": ra["load"] + rb["load"],
        }
        rutas.remove(ra)
        rutas.remove(rb)
        rutas.append(nueva_ruta)

    # Convertir nodos-tupla a enteros y aplicar 2-opt
    rutas_finales = []
    for r in rutas:
        plain = (
            [deposito]
            + [n[0] if isinstance(n, tuple) else n for n in r["nodes"][1:-1]]
            + [deposito]
        )
        plain = dos_opt(plain, dist)
        rutas_finales.append({
            "route": plain,
            "load": r["load"],
            "dist": distancia_ruta(plain, dist),
        })

    # Ordenar por distancia descendente para facilitar la asignación FFD
    rutas_finales.sort(key=lambda x: -x["dist"])
    return rutas_finales


# ─── ASIGNACIÓN DE VIAJES A CAMIONES FÍSICOS (FFD) ────────────────────────────

def asignar_camiones(viajes, velocidad_kmh=60, recarga_min=20, jornada_h=8):
    """
    Asigna viajes a camiones físicos usando First-Fit Decreasing sobre tiempo.

    Un camión puede hacer varios viajes en su jornada:
    tiempo_total = Σ(dist_viaje / velocidad) + (n_viajes - 1) * recarga

    Parámetros
    ----------
    viajes       : lista de dicts con 'dist', 'load', 'route'
    velocidad_kmh: velocidad promedio de conducción
    recarga_min  : minutos para recargar el camión en el CD entre viajes
    jornada_h    : horas disponibles por turno

    Retorna
    -------
    Lista de dicts {'camion_id', 'viajes': [...], 'tiempo_h', 'pallets_totales'}
    """
    recarga_h = recarga_min / 60.0
    camiones = []

    for viaje in viajes:
        t_viaje = viaje["dist"] / velocidad_kmh
        colocado = False

        for cam in camiones:
            t_acum = sum(v["dist"] / velocidad_kmh for v in cam["viajes"])
            t_acum += recarga_h * len(cam["viajes"])  # recarga antes de este viaje
            if t_acum + t_viaje <= jornada_h:
                cam["viajes"].append(viaje)
                colocado = True
                break

        if not colocado:
            camiones.append({"viajes": [viaje]})

    # Calcular métricas por camión
    resultado = []
    for i, cam in enumerate(camiones):
        t_conduccion = sum(v["dist"] / velocidad_kmh for v in cam["viajes"])
        t_recargas = recarga_h * (len(cam["viajes"]) - 1)
        resultado.append({
            "camion_id": f"C-{i + 1:02d}",
            "viajes": cam["viajes"],
            "n_viajes": len(cam["viajes"]),
            "tiempo_h": round(t_conduccion + t_recargas, 2),
            "uso_jornada_pct": round((t_conduccion + t_recargas) / jornada_h * 100, 1),
            "pallets_totales": sum(v["load"] for v in cam["viajes"]),
        })

    return resultado


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────

def resolver_cvrp(demandas_custom=None, capacidad=CAPACIDAD_CAMION,
                  velocidad=60, recarga_min=20, jornada_h=8):
    """
    Punto de entrada principal.

    Parámetros
    ----------
    demandas_custom : dict {canton_id: pallets} o None (usa defaults)
    capacidad       : pallets por viaje
    velocidad       : km/h
    recarga_min     : minutos de recarga en CD
    jornada_h       : horas por turno

    Retorna
    -------
    dict con 'viajes', 'camiones', 'kpis'
    """
    if demandas_custom is None:
        demandas = {c["id"]: c["demand"] for c in CANTONES}
    else:
        demandas = {c["id"]: demandas_custom.get(c["id"], c["demand"]) for c in CANTONES}
    demandas[0] = 0  # depósito no tiene demanda

    nodos = [c["id"] for c in CANTONES]
    viajes = clarke_wright(nodos, demandas, DIST, capacidad, deposito=0)
    camiones = asignar_camiones(viajes, velocidad_kmh=velocidad,
                                recarga_min=recarga_min, jornada_h=jornada_h)

    demanda_total = sum(demandas[i] for i in demandas if i != 0)
    dist_total = sum(v["dist"] for v in viajes)
    util_prom = sum(v["load"] for v in viajes) / (len(viajes) * capacidad) * 100

    kpis = {
        "demanda_total": demanda_total,
        "n_viajes": len(viajes),
        "n_camiones": len(camiones),
        "dist_total_km": round(dist_total, 1),
        "dist_media_km": round(dist_total / len(viajes), 1),
        "viajes_llenos": sum(1 for v in viajes if v["load"] == capacidad),
        "utilizacion_prom_pct": round(util_prom, 1),
        "viajes_min_teoricos": math.ceil(demanda_total / capacidad),
    }

    return {"viajes": viajes, "camiones": camiones, "kpis": kpis}
