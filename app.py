"""
app.py — Interfaz Streamlit · Florida Bebidas CVRP Guanacaste
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
    CANTON_NAME,
    resolver_cvrp,
)

# ─── PÁGINA ───────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Florida Bebidas · CVRP Guanacaste",
    page_icon="🚛",
    layout="wide",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Sora', sans-serif; }

.kpi-card {
    background: linear-gradient(135deg,#0d1b2a,#1b2a3b);
    border:1px solid #2a3f55; border-radius:12px;
    padding:.9rem 1.2rem; text-align:center; margin-bottom:.4rem;
}
.kpi-val { font-size:1.75rem; font-weight:700; color:#f4a261;
           font-family:'JetBrains Mono',monospace; }
.kpi-lbl { font-size:.72rem; color:#8ba7bf; text-transform:uppercase;
           letter-spacing:.08em; margin-top:.2rem; }

.viaje-header {
    background:linear-gradient(90deg,#1d3557,#457b9d);
    color:#fff; padding:.55rem 1rem; border-radius:8px 8px 0 0;
    font-weight:600; font-size:.9rem; margin-top:.8rem;
}
.parada-row {
    display:grid; grid-template-columns:2fr 1fr 1fr 1fr 3fr 1fr;
    gap:.4rem; padding:.35rem .8rem; font-size:.82rem;
    border-bottom:1px solid #e8edf2;
}
.parada-row.salida  { background:#f0f7ff; font-weight:600; }
.parada-row.entrega { background:#ffffff; }
.parada-row.regreso { background:#f9f9f9; color:#666; font-style:italic; }
.bar-wrap { width:100%; background:#e0e0e0; border-radius:4px; height:10px; margin-top:3px; }
.bar-fill  { height:10px; border-radius:4px; }

.ok-box  { background:#d1fae5; border-left:4px solid #059669;
           padding:.6rem .9rem; border-radius:6px; font-size:.86rem; }
.warn-box { background:#fff3cd; border-left:4px solid #f4a261;
            padding:.6rem .9rem; border-radius:6px; font-size:.86rem; }
</style>
""", unsafe_allow_html=True)

COLORES_RUTA = [
    "#e63946","#2a9d8f","#e9c46a","#264653","#f4a261",
    "#a8dadc","#457b9d","#6d2b9f","#ff6b6b","#06d6a0",
    "#118ab2","#ffd166","#ef476f","#073b4c","#8338ec","#fb5607",
]

def color_barra(pct):
    if pct >= 90: return "#059669"
    if pct >= 70: return "#f4a261"
    if pct >= 50: return "#fbbf24"
    return "#ef4444"

# ─── ENCABEZADO ───────────────────────────────────────────────────────────────
st.markdown("## 🚛 Florida Bebidas — Distribución Guanacaste")
st.markdown(
    "**CVRP · CD Liberia (depósito)** · "
    "Clarke-Wright + 2-opt + Consolidación de carga · Detalle por parada"
)
st.divider()

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Parámetros del modelo")
    capacidad      = st.number_input("Capacidad por camión (pallets)", 10, 48, CAPACIDAD_CAMION, step=1)
    velocidad      = st.number_input("Velocidad promedio (km/h)", 30, 120, 60, step=5)
    recarga_min    = st.number_input("Tiempo recarga en CD (min)", 5, 60, 20, step=5)
    jornada_h      = st.number_input("Jornada laboral (horas)", 6, 12, 8, step=1)
    detour_pct     = st.slider("Tolerancia desvío consolidación (%)", 0, 80, 30, step=5,
                               help="Cuánto puede alargarse un viaje al absorber otro")

    st.divider()
    st.markdown("### 📦 Demanda por cantón (pallets/sem)")
    demandas_ui = {}
    for c in CANTONES[1:]:
        demandas_ui[c["id"]] = st.number_input(
            c["name"], min_value=0, max_value=500,
            value=c["demand"], step=1, key=f"dem_{c['id']}"
        )

    st.divider()
    optimizar = st.button("🔄 Optimizar rutas", type="primary", use_container_width=True)

# ─── RESOLVER ─────────────────────────────────────────────────────────────────
if "resultado" not in st.session_state or optimizar:
    with st.spinner("Optimizando rutas…"):
        st.session_state["resultado"] = resolver_cvrp(
            demandas_custom=demandas_ui,
            capacidad=capacidad,
            velocidad=velocidad,
            recarga_min=recarga_min,
            jornada_h=jornada_h,
            tolerancia_detour=detour_pct / 100,
        )
        st.session_state["params"] = dict(
            capacidad=capacidad, velocidad=velocidad,
            recarga_min=recarga_min, jornada_h=jornada_h,
        )

res    = st.session_state["resultado"]
params = st.session_state["params"]
viajes = res["viajes"]
cams   = res["camiones"]
kpis   = res["kpis"]

# ─── KPIs ─────────────────────────────────────────────────────────────────────
cols = st.columns(6)
items = [
    (f"{kpis['demanda_total']}", "Pallets / semana"),
    (f"{kpis['n_viajes']}",      "Viajes totales"),
    (f"{kpis['n_camiones']}",    "Camiones físicos"),
    (f"{kpis['dist_total_km']:,.0f} km", "Distancia total"),
    (f"{kpis['utilizacion_prom_pct']}%", "Utilización prom."),
    (f"{kpis['viajes_llenos']} / {kpis['n_viajes']}", "Viajes al 100%"),
]
for col, (val, lbl) in zip(cols, items):
    with col:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-val">{val}</div>'
            f'<div class="kpi-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )
st.markdown("")

# ─── TABS PRINCIPALES ─────────────────────────────────────────────────────────
tab_mapa, tab_viajes, tab_camiones, tab_cantones = st.tabs([
    "🗺️ Mapa de rutas",
    "📋 Detalle de viajes",
    "🚚 Camiones físicos",
    "📊 Resumen por cantón",
])

# ── TAB MAPA ──────────────────────────────────────────────────────────────────
with tab_mapa:
    col_m, col_leg = st.columns([3, 1])
    with col_m:
        m = folium.Map(location=[10.35, -85.25], zoom_start=8,
                       tiles="CartoDB Positron")

        folium.Marker(
            [CANTONES[0]["lat"], CANTONES[0]["lon"]],
            tooltip="⭐ CD Liberia (Depósito)",
            popup="<b>CD Liberia — Depósito Florida Bebidas</b>",
            icon=folium.Icon(color="black", icon="industry", prefix="fa"),
        ).add_to(m)

        for c in CANTONES[1:]:
            d = demandas_ui.get(c["id"], c["demand"])
            folium.CircleMarker(
                [c["lat"], c["lon"]], radius=8,
                color="#ffffff", fill=True, fill_color="#1d3557", fill_opacity=.9,
                tooltip=f"<b>{c['name']}</b><br>{d} pallets/sem",
            ).add_to(m)
            folium.Marker(
                [c["lat"], c["lon"]],
                icon=folium.DivIcon(
                    html=f'<div style="font-size:9px;font-weight:700;'
                         f'color:#1d3557;margin-left:10px;white-space:nowrap">'
                         f'{c["name"]}</div>',
                    icon_size=(120, 20),
                ),
            ).add_to(m)

        for idx, viaje in enumerate(viajes):
            color = COLORES_RUTA[idx % len(COLORES_RUTA)]
            coords = [[CANTONES[n]["lat"], CANTONES[n]["lon"]]
                      for n in viaje["nodos"]]
            paradas_str = " → ".join(
                CANTON_NAME.get(n, "").replace(" (Depósito)", "")
                for n in viaje["nodos"]
            )
            folium.PolyLine(
                coords, color=color, weight=3.5, opacity=.85,
                tooltip=(f"<b>Viaje {idx+1}</b><br>"
                         f"{viaje['load']} pallets · {viaje['dist']:.0f} km<br>"
                         f"{paradas_str}"),
            ).add_to(m)

        st_folium(m, height=560, use_container_width=True)

    with col_leg:
        st.markdown("**Leyenda de viajes**")
        for idx, viaje in enumerate(viajes):
            color = COLORES_RUTA[idx % len(COLORES_RUTA)]
            pct = round(viaje["load"] / params["capacidad"] * 100)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;'
                f'margin-bottom:4px;font-size:.8rem">'
                f'<div style="width:16px;height:16px;border-radius:3px;'
                f'background:{color};flex-shrink:0"></div>'
                f'<span><b>Viaje {idx+1}</b><br>'
                f'{viaje["load"]} p · {viaje["dist"]:.0f} km · {pct}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── TAB VIAJES DETALLADOS ────────────────────────────────────────────────────
with tab_viajes:
    st.markdown("Cada viaje muestra el estado de la carga en cada parada — "
                "cuántos pallets lleva el camión, cuántos descarga y con cuántos sigue.")

    viaje_sel = st.selectbox(
        "Ver viaje específico (o deja 'Todos')",
        options=["Todos"] + [f"Viaje {i+1}" for i in range(len(viajes))],
    )
    indices = (
        range(len(viajes))
        if viaje_sel == "Todos"
        else [int(viaje_sel.split()[1]) - 1]
    )

    for idx in indices:
        v = viajes[idx]
        color = COLORES_RUTA[idx % len(COLORES_RUTA)]
        pct_util = round(v["load"] / params["capacidad"] * 100)
        cant_entregas = [
            f"{CANTON_NAME.get(cid,'?')} ({pal}p)"
            for cid, pal in v["carga"].items()
        ]

        # Header del viaje
        st.markdown(
            f'<div class="viaje-header" style="border-left:5px solid {color}">'
            f'🚛 Viaje {idx+1} &nbsp;·&nbsp; '
            f'{v["load"]}/{params["capacidad"]} pallets ({pct_util}%) &nbsp;·&nbsp; '
            f'{v["dist"]:.0f} km &nbsp;·&nbsp; '
            f'Entregas: {", ".join(cant_entregas)}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Tabla de paradas
        rows = []
        for p in v["paradas"]:
            bar_w  = int(p["pct_lleno"])
            bar_col = color_barra(p["pct_lleno"])
            barra = (
                f'<div class="bar-wrap"><div class="bar-fill" '
                f'style="width:{bar_w}%;background:{bar_col}"></div></div>'
            )
            rows.append({
                "Orden":     p["orden"],
                "Tipo":      p["tipo"],
                "Cantón":    p["canton"].replace(" (Depósito)", " ⭐"),
                "Llega con": f"{p['llega_con']} p",
                "Descarga":  f"{p['descarga']} p" if p["descarga"] > 0 else "—",
                "Sale con":  f"{p['sale_con']} p",
                "Llenado":   f"{p['pct_lleno']:.0f}%",
            })

        df_p = pd.DataFrame(rows)

        # Color por tipo en la tabla
        def color_tipo(val):
            c_map = {"SALIDA": "background-color:#dbeafe",
                     "REGRESO": "background-color:#f3f4f6",
                     "ENTREGA": "background-color:#ffffff"}
            return c_map.get(val, "")

        styled = df_p.style.applymap(color_tipo, subset=["Tipo"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Barra visual de llenado a lo largo del viaje
        puntos = [p for p in v["paradas"]]
        bar_data = pd.DataFrame({
            "Parada": [p["canton"].replace(" (Depósito)","⭐") for p in puntos],
            "Pallets a bordo": [p["llega_con"] for p in puntos],
        })
        st.bar_chart(bar_data.set_index("Parada"), color=color, height=140)
        st.markdown("")

# ── TAB CAMIONES FÍSICOS ──────────────────────────────────────────────────────
with tab_camiones:
    st.markdown(
        f"Cada camión físico hace varios viajes en su jornada de **{params['jornada_h']}h**. "
        f"Sale al CD, descarga, recarga (**{params['recarga_min']} min**) y vuelve a salir."
    )
    st.markdown("")

    # Resumen tabla
    rows_cam = []
    for cam in cams:
        nums = [f"#{viajes.index(v)+1}" for v in cam["viajes"]]
        pallets_seq = " + ".join(str(v["load"]) for v in cam["viajes"])
        rows_cam.append({
            "Camión":             cam["camion_id"],
            "Viajes asignados":   ", ".join(nums),
            "Detalle pallets":    pallets_seq,
            "Total pallets":      cam["pallets_totales"],
            "Distancia (km)":     cam["dist_total_km"],
            "Tiempo total":       f"{cam['tiempo_h']:.1f} h",
            "Uso jornada":        f"{cam['uso_jornada_pct']:.0f}%",
        })
    df_cam = pd.DataFrame(rows_cam)
    st.dataframe(df_cam, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Detalle jornada por camión")

    for cam in cams:
        st.markdown(f"#### 🚛 {cam['camion_id']} — {cam['n_viajes']} viaje(s) · "
                    f"{cam['pallets_totales']} pallets · {cam['tiempo_h']:.1f}h / "
                    f"{params['jornada_h']}h ({cam['uso_jornada_pct']:.0f}%)")

        for vi, viaje in enumerate(cam["viajes"]):
            vnum = viajes.index(viaje) + 1
            color = COLORES_RUTA[(vnum - 1) % len(COLORES_RUTA)]
            pct = round(viaje["load"] / params["capacidad"] * 100)
            paradas_str = " → ".join(
                CANTON_NAME.get(n, "").replace(" (Depósito)", "⭐")
                for n in viaje["nodos"]
            )
            cant_str = "  |  ".join(
                f"{CANTON_NAME.get(cid,'?')}: {pal}p"
                for cid, pal in viaje["carga"].items()
            )
            st.markdown(
                f'<div style="border-left:4px solid {color};padding:.5rem .9rem;'
                f'margin:.3rem 0;background:#f8fafc;border-radius:0 6px 6px 0;">'
                f'<b style="color:{color}">Viaje #{vnum}</b> &nbsp;'
                f'<span style="font-size:.82rem">'
                f'{viaje["load"]}p ({pct}%) · {viaje["dist"]:.0f} km<br>'
                f'<span style="color:#555">Ruta: {paradas_str}</span><br>'
                f'<span style="color:#777">Entregas: {cant_str}</span>'
                f'</span></div>',
                unsafe_allow_html=True,
            )

        # Timeline visual de tiempo
        t_total = cam["tiempo_h"]
        pct_uso = cam["uso_jornada_pct"]
        bar_c = color_barra(pct_uso)
        st.markdown(
            f'<div style="margin:.4rem 0 .8rem 0">'
            f'<div style="font-size:.75rem;color:#666;margin-bottom:3px">'
            f'Uso de jornada: {t_total:.1f}h / {params["jornada_h"]}h</div>'
            f'<div class="bar-wrap" style="height:14px">'
            f'<div class="bar-fill" style="width:{min(pct_uso,100):.0f}%;'
            f'background:{bar_c};height:14px"></div></div></div>',
            unsafe_allow_html=True,
        )

# ── TAB RESUMEN POR CANTÓN ────────────────────────────────────────────────────
with tab_cantones:
    rows_cant = []
    for c in CANTONES[1:]:
        d = demandas_ui.get(c["id"], c["demand"])
        viajes_canton = [
            (i + 1, v["carga"].get(c["id"], 0))
            for i, v in enumerate(viajes)
            if c["id"] in v["carga"]
        ]
        pallets_recibidos = sum(p for _, p in viajes_canton)
        viajes_str = ", ".join(f"#{n}({p}p)" for n, p in viajes_canton)
        rows_cant.append({
            "Cantón":              c["name"],
            "Demanda (p)":         d,
            "Pallets entregados":  pallets_recibidos,
            "Diferencia":          pallets_recibidos - d,
            "Nº viajes":           len(viajes_canton),
            "Viajes (pallets)":    viajes_str,
            "Entrega dividida":    "Sí" if len(viajes_canton) > 1 else "No",
        })
    df_cant = pd.DataFrame(rows_cant)

    # Verificación
    total_entregado = df_cant["Pallets entregados"].sum()
    total_demanda   = df_cant["Demanda (p)"].sum()
    if total_entregado == total_demanda:
        st.markdown(
            f'<div class="ok-box">✅ Verificación OK — '
            f'{total_entregado} pallets entregados = {total_demanda} demandados</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="warn-box">⚠️ Discrepancia: '
            f'{total_entregado} entregados vs {total_demanda} demandados</div>',
            unsafe_allow_html=True,
        )
    st.markdown("")
    st.dataframe(df_cant, use_container_width=True, hide_index=True)

# ─── ANÁLISIS DE EFICIENCIA ───────────────────────────────────────────────────
st.divider()
st.markdown("### ⚠️ Análisis de eficiencia de carga")

bajos = [v for v in viajes if v["load"] / params["capacidad"] < 0.60]
if bajos:
    st.markdown(
        f'<div class="warn-box">⚠️ <b>{len(bajos)} viaje(s)</b> con utilización &lt;60%. '
        f'Aumenta la tolerancia de desvío en el sidebar para intentar consolidarlos más.</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="ok-box">✅ Todos los viajes tienen utilización ≥ 60%.</div>',
        unsafe_allow_html=True,
    )

st.markdown("")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Util. promedio",        f"{kpis['utilizacion_prom_pct']}%")
c2.metric("Viajes al 100%",        f"{kpis['viajes_llenos']}")
c3.metric("Viajes ≥ 80%",          f"{kpis['viajes_casi_llenos']}")
c4.metric("Viajes mín. teórico",   kpis["viajes_min_teoricos"])
c5.metric("Viajes generados",      kpis["n_viajes"])

st.divider()
st.caption(
    "Modelo: Clarke-Wright Savings + 2-opt + Consolidación de carga (mejor inserción) + FFD · "
    "Datos: INEC 2022 · Distancias por carretera (km) del Excel base · UCR II-1122 I-2026"
)
