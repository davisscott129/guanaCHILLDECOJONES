"""
app.py — Interfaz Streamlit para el CVRP de Florida Bebidas · Guanacaste
Corre con: streamlit run app.py
"""

import math
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from modelo import (
    CANTONES,
    CAPACIDAD_CAMION,
    resolver_cvrp,
)

# ─── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Florida Bebidas · CVRP Guanacaste",
    page_icon="🚛",
    layout="wide",
)

# ─── ESTILOS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Sora', sans-serif; }

.metric-card {
    background: linear-gradient(135deg, #0d1b2a 0%, #1b2a3b 100%);
    border: 1px solid #2a3f55;
    border-radius: 12px;
    padding: 1rem 1.4rem;
    text-align: center;
    margin-bottom: 0.5rem;
}
.metric-card .val {
    font-size: 1.9rem;
    font-weight: 700;
    color: #f4a261;
    font-family: 'JetBrains Mono', monospace;
}
.metric-card .lbl {
    font-size: 0.75rem;
    color: #8ba7bf;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.25rem;
}
.warn-box {
    background: #fff3cd;
    border-left: 4px solid #f4a261;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    font-size: 0.88rem;
}
.ok-box {
    background: #d1fae5;
    border-left: 4px solid #059669;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)

# ─── COLORES DE RUTAS ─────────────────────────────────────────────────────────
COLORES = [
    "#e63946", "#2a9d8f", "#e9c46a", "#264653", "#f4a261",
    "#a8dadc", "#457b9d", "#6d2b9f", "#ff6b6b", "#06d6a0",
    "#118ab2", "#ffd166", "#ef476f", "#073b4c", "#8338ec",
    "#fb5607", "#3a86ff", "#ffbe0b",
]

# ─── ENCABEZADO ───────────────────────────────────────────────────────────────
st.markdown("## 🚛 Florida Bebidas — Distribución Guanacaste")
st.markdown(
    "**CVRP · CD Liberia (depósito)** · "
    "Clarke-Wright Savings + 2-opt · Asignación FFD por jornada"
)
st.divider()

# ─── SIDEBAR: PARÁMETROS ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Parámetros del modelo")
    capacidad    = st.number_input("Capacidad por camión (pallets)", 10, 48, CAPACIDAD_CAMION, step=1)
    velocidad    = st.number_input("Velocidad promedio (km/h)", 30, 120, 60, step=5)
    recarga_min  = st.number_input("Tiempo recarga en CD (min)", 5, 60, 20, step=5)
    jornada_h    = st.number_input("Jornada laboral (horas)", 6, 12, 8, step=1)

    st.divider()
    st.markdown("### 📦 Demanda por cantón (pallets/sem)")
    demandas_ui = {}
    for c in CANTONES[1:]:
        demandas_ui[c["id"]] = st.number_input(
            c["name"],
            min_value=0, max_value=500,
            value=c["demand"], step=1,
            key=f"dem_{c['id']}",
        )

    st.divider()
    optimizar_btn = st.button("🔄 Optimizar rutas", type="primary", use_container_width=True)

# ─── RESOLVER MODELO ──────────────────────────────────────────────────────────
if "resultado" not in st.session_state or optimizar_btn:
    with st.spinner("Calculando rutas óptimas…"):
        st.session_state["resultado"] = resolver_cvrp(
            demandas_custom=demandas_ui,
            capacidad=capacidad,
            velocidad=velocidad,
            recarga_min=recarga_min,
            jornada_h=jornada_h,
        )
        st.session_state["params"] = {
            "capacidad": capacidad,
            "velocidad": velocidad,
            "recarga_min": recarga_min,
            "jornada_h": jornada_h,
        }

resultado = st.session_state["resultado"]
params    = st.session_state["params"]
viajes    = resultado["viajes"]
camiones  = resultado["camiones"]
kpis      = resultado["kpis"]

# ─── KPIs ─────────────────────────────────────────────────────────────────────
cols = st.columns(5)
kpi_items = [
    (f"{kpis['demanda_total']}", "Pallets / semana"),
    (f"{kpis['n_viajes']}",      "Viajes (salidas)"),
    (f"{kpis['n_camiones']}",    "Camiones físicos"),
    (f"{kpis['dist_total_km']:,.0f} km", "Distancia total"),
    (f"{kpis['utilizacion_prom_pct']}%", "Utilización prom."),
]
for col, (val, lbl) in zip(cols, kpi_items):
    with col:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="val">{val}</div>'
            f'<div class="lbl">{lbl}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("")

# ─── MAPA + TABLA DE VIAJES ───────────────────────────────────────────────────
col_mapa, col_tabla = st.columns([3, 2])

with col_mapa:
    st.markdown("### 🗺️ Mapa de rutas")
    m = folium.Map(location=[10.35, -85.25], zoom_start=8, tiles="CartoDB Positron")

    # Depósito
    deposito = CANTONES[0]
    folium.Marker(
        [deposito["lat"], deposito["lon"]],
        tooltip="⭐ CD Liberia (Depósito)",
        popup="<b>CD Liberia — Depósito Florida Bebidas</b>",
        icon=folium.Icon(color="black", icon="industry", prefix="fa"),
    ).add_to(m)

    # Cantones
    for c in CANTONES[1:]:
        d = demandas_ui.get(c["id"], c["demand"])
        folium.CircleMarker(
            [c["lat"], c["lon"]],
            radius=8,
            color="#ffffff",
            fill=True,
            fill_color="#1d3557",
            fill_opacity=0.9,
            tooltip=f"<b>{c['name']}</b><br>{d} pallets/sem",
        ).add_to(m)
        folium.Marker(
            [c["lat"], c["lon"]],
            icon=folium.DivIcon(
                html=f'<div style="font-size:9px;font-weight:700;'
                     f'color:#1d3557;margin-left:10px;white-space:nowrap">'
                     f'{c["name"]}</div>',
                icon_size=(100, 20),
            ),
        ).add_to(m)

    # Rutas
    for idx, viaje in enumerate(viajes):
        color = COLORES[idx % len(COLORES)]
        coords = [[CANTONES[n]["lat"], CANTONES[n]["lon"]] for n in viaje["route"]]
        paradas = " → ".join(
            CANTONES[n]["name"].replace(" (Depósito)", "") for n in viaje["route"]
        )
        folium.PolyLine(
            coords,
            color=color,
            weight=3,
            opacity=0.85,
            tooltip=f"Viaje {idx+1} · {viaje['load']} pallets · {viaje['dist']:.0f} km<br>{paradas}",
        ).add_to(m)

    st_folium(m, height=530, use_container_width=True)

with col_tabla:
    st.markdown("### 📋 Detalle de viajes")
    filas = []
    for idx, v in enumerate(viajes):
        util = v["load"] / params["capacidad"]
        barra = "█" * int(util * 10) + "░" * (10 - int(util * 10))
        paradas = " → ".join(
            CANTONES[n]["name"].replace(" (Depósito)", "") for n in v["route"]
        )
        filas.append({
            "#": idx + 1,
            "Ruta": paradas,
            "Pallets": v["load"],
            "Cap": f"{util*100:.0f}%",
            "Uso":  barra,
            "km":   f"{v['dist']:.0f}",
        })
    df_viajes = pd.DataFrame(filas)
    st.dataframe(df_viajes, use_container_width=True, hide_index=True, height=490)

# ─── ASIGNACIÓN A CAMIONES FÍSICOS ────────────────────────────────────────────
st.divider()
st.markdown("### 🚚 Asignación de viajes a camiones físicos")
st.caption(
    f"Jornada {params['jornada_h']}h · "
    f"velocidad {params['velocidad']} km/h · "
    f"recarga {params['recarga_min']} min entre viajes"
)

filas_cam = []
for cam in camiones:
    nums = [f"#{viajes.index(v)+1}" for v in cam["viajes"]]
    filas_cam.append({
        "Camión":           cam["camion_id"],
        "Viajes":           ", ".join(nums),
        "Nº viajes":        cam["n_viajes"],
        "Pallets totales":  cam["pallets_totales"],
        "Tiempo (h)":       f"{cam['tiempo_h']:.1f}h",
        "Uso jornada":      f"{cam['uso_jornada_pct']:.0f}%",
    })
df_camiones = pd.DataFrame(filas_cam)
st.dataframe(df_camiones, use_container_width=True, hide_index=True)

# ─── RESUMEN POR CANTÓN ───────────────────────────────────────────────────────
st.divider()
st.markdown("### 📊 Resumen por cantón")

filas_cant = []
for c in CANTONES[1:]:
    d = demandas_ui.get(c["id"], c["demand"])
    viajes_canton = [v for v in viajes if c["id"] in v["route"]]
    filas_cant.append({
        "Cantón":                c["name"],
        "Demanda (pallets)":     d,
        "Viajes que lo sirven":  len(viajes_canton),
        "Entrega dividida":      "Sí" if len(viajes_canton) > 1 else "No",
    })
df_cantones = pd.DataFrame(filas_cant)
st.dataframe(df_cantones, use_container_width=True, hide_index=True)

# ─── ANÁLISIS DE EFICIENCIA ───────────────────────────────────────────────────
st.divider()
st.markdown("### ⚠️ Análisis de eficiencia")

viajes_bajos = [v for v in viajes if v["load"] / params["capacidad"] < 0.60]
if viajes_bajos:
    st.markdown(
        f'<div class="warn-box">⚠️ <b>{len(viajes_bajos)} viaje(s)</b> con utilización &lt; 60 %. '
        f'Considera consolidar rutas o ajustar la demanda.</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="ok-box">✅ Todos los viajes tienen utilización ≥ 60 %. Flota bien aprovechada.</div>',
        unsafe_allow_html=True,
    )

st.markdown("")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Utilización promedio",      f"{kpis['utilizacion_prom_pct']}%")
c2.metric("Viajes llenos (100%)",      f"{kpis['viajes_llenos']} / {kpis['n_viajes']}")
c3.metric("Viajes mínimos teóricos",   kpis["viajes_min_teoricos"])
c4.metric("Viajes generados",          kpis["n_viajes"])

st.divider()
st.caption(
    "Modelo: Clarke-Wright Savings + 2-opt + FFD · "
    "Datos: INEC 2022 · Distancias por carretera (km) del Excel base UCR II-1122 · I-2026"
)
