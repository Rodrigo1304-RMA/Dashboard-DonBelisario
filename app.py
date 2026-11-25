import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# 1. Configuración de la página
st.set_page_config(
    page_title="Dashboard BI - Don Belisario",
    page_icon="🍗",
    layout="wide"
)

# 2. Carga y transformación de datos (Replica Modelo Estrella y ETL)
@st.cache_data
def cargar_datos():
    # Lectura robusta (detecta separador ',' o ';' y codificación automáticamente)
    def leer_csv(ruta):
        try:
            return pd.read_csv(ruta, sep=None, engine="python", encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(ruta, sep=None, engine="python", encoding="latin-1")

    dim_mozo = leer_csv("Dim_Mozo.csv")
    dim_prod = leer_csv("Dim_Producto.csv")
    dim_rest = leer_csv("Dim_Restaurante.csv")
    fact = leer_csv("Fact_Atencion_Salon.csv")

    # Limpiar espacios en nombres de columnas por seguridad
    for df_temp in [dim_mozo, dim_prod, dim_rest, fact]:
        df_temp.columns = df_temp.columns.str.strip()

    # Transformaciones de fecha y tiempo (Dim_Tiempo virtual)
    fact = fact.dropna(how="all")
    fact["Fecha_dt"] = pd.to_datetime(fact["Fecha"], errors="coerce")
    fact["Anio"] = fact["Fecha_dt"].dt.year
    fact["MesNum"] = fact["Fecha_dt"].dt.month
    fact["Periodo"] = fact["Fecha_dt"].dt.to_period("M").astype(str)

    dias_es = {
        0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
        4: "Viernes", 5: "Sábado", 6: "Domingo"
    }
    fact["DiaSemana"] = fact["Fecha_dt"].dt.dayofweek.map(dias_es)

    # Franja horaria desde columna Hora
    hora_num = pd.to_datetime(fact["Hora"].astype(str), format="%H:%M", errors="coerce").dt.hour
    condiciones_franja = [
        (hora_num >= 11) & (hora_num < 16),
        (hora_num >= 16) & (hora_num < 19),
        (hora_num >= 19)
    ]
    etiquetas_franja = ["Almuerzo (11:00 - 15:59)", "Tarde (16:00 - 18:59)", "Cena / Punta (19:00 - 23:00)"]
    fact["FranjaHoraria"] = np.select(condiciones_franja, etiquetas_franja, default="Mañana / Apertura")

    # Métricas calculadas del negocio
    fact["MontoTotal"] = fact["Cantidad"] * fact["PrecioUnitario"]
    fact["TiempoTotalAtencionMin"] = (
        fact["TiempoTomaMin"] + fact["TiempoCocinaMin"] + fact["TiempoEntregaMin"]
    )
    fact["CicloTotalMesaMin"] = (
        fact["TiempoTotalAtencionMin"] + fact["TiempoPermanenciaMin"] + fact["TiempoCobroMin"]
    )
    # Estándar SLA objetivo: <= 17 minutos
    fact["CumpleSLA"] = np.where(fact["TiempoTotalAtencionMin"] <= 17, 1, 0)
    fact["FueraSLA"] = np.where(fact["TiempoTotalAtencionMin"] > 17, 1, 0)

    # Cruce Modelo Estrella (Joins con las 3 dimensiones)
    df_modelo = (
        fact.merge(dim_rest, on="CodSucursal", how="left")
            .merge(dim_mozo, on="CodMozo", how="left")
            .merge(dim_prod, on="CodProducto", how="left")
    )
    df_modelo["RolPuesto"] = "Mozo de Salón"

    return df_modelo

df = cargar_datos()

# Encabezado principal
st.title("📊 Don Belisario | Tablero de Control Operativo — Atención en Salón")
st.markdown("**Análisis de Tiempos Operativos, Congestión en Horas Punta y Cumplimiento de SLA (2025 vs. 2026)**")
st.markdown("---")

# 3. Sidebar de Filtros (Bloque CÓMO de la Matriz)
st.sidebar.header("🔎 Filtros de Análisis")

with st.sidebar.form(key="form_filtros_db"):
    anios_disp = sorted(df["Anio"].dropna().unique().tolist())
    anio_sel = st.multiselect("Año:", options=anios_disp, default=anios_disp)

    distritos_disp = sorted(df["Distrito"].dropna().unique().tolist())
    distrito_sel = st.multiselect("Distrito:", options=distritos_disp, default=distritos_disp)

    rest_disp = sorted(df["NombreSucursal"].dropna().unique().tolist())
    rest_sel = st.multiselect("Restaurante:", options=rest_disp, default=rest_disp)

    turnos_disp = sorted(df["Turno"].dropna().unique().tolist())
    turno_sel = st.multiselect("Turno:", options=turnos_disp, default=turnos_disp)

    franjas_disp = sorted(df["FranjaHoraria"].dropna().unique().tolist())
    franja_sel = st.multiselect("Franja Horaria:", options=franjas_disp, default=franjas_disp)

    cat_disp = sorted(df["CategoriaGeneral"].dropna().unique().tolist())
    cat_sel = st.multiselect("Categoría General:", options=cat_disp, default=cat_disp)

    aplicar = st.form_submit_button("Aplicar Filtros")

# Aplicar filtros
df_f = df[
    (df["Anio"].isin(anio_sel)) &
    (df["Distrito"].isin(distrito_sel)) &
    (df["NombreSucursal"].isin(rest_sel)) &
    (df["Turno"].isin(turno_sel)) &
    (df["FranjaHoraria"].isin(franja_sel)) &
    (df["CategoriaGeneral"].isin(cat_sel))
]

if df_f.empty:
    st.warning("⚠️ No hay registros para la combinación de filtros seleccionada. Marca al menos una opción en cada filtro.")
    st.stop()

# 4. KPIs Ejecutivos Principales (Bloque QUÉ de la Matriz)
st.subheader("📌 Indicadores Clave de Desempeño (KPIs)")
k1, k2, k3, k4, k5 = st.columns(5)

t_prom_actual = df_f["TiempoTotalAtencionMin"].mean()
t_2025 = df_f[df_f["Anio"] == 2025]["TiempoTotalAtencionMin"].mean()
t_2026 = df_f[df_f["Anio"] == 2026]["TiempoTotalAtencionMin"].mean()
delta_tiempo = f"{((t_2026 - t_2025) / t_2025) * 100:.1f}% vs 2025" if (pd.notna(t_2025) and pd.notna(t_2026) and t_2025 > 0) else None

sla_pct = df_f["CumpleSLA"].mean() * 100
fuera_sla = int(df_f["FueraSLA"].sum())
ciclo_mesa = df_f["CicloTotalMesaMin"].mean()
ventas_tot = df_f["MontoTotal"].sum()
total_pedidos = len(df_f)

with k1:
    st.metric("Tiempo Prom. Atención", f"{t_prom_actual:.1f} min", delta=delta_tiempo, delta_color="inverse")
with k2:
    st.metric("% Cumple SLA (≤17m)", f"{sla_pct:.1f}%")
with k3:
    st.metric("Pedidos Fuera de SLA", f"{fuera_sla:,}", help="Órdenes que superaron los 17 minutos de atención")
with k4:
    st.metric("Ciclo Total en Mesa", f"{ciclo_mesa:.1f} min", help="Atención + Permanencia + Cobro")
with k5:
    st.metric("Ventas Salón / Pedidos", f"S/ {ventas_tot:,.0f}", delta=f"{total_pedidos:,} órdenes", delta_color="off")

st.markdown("---")

# Fila 1 de gráficos: Desglose de tiempos y evolución SLA
c1, c2 = st.columns(2)

with c1:
    df_tiempos_rest = df_f.groupby("NombreSucursal")[
        ["TiempoTomaMin", "TiempoCocinaMin", "TiempoEntregaMin"]
    ].mean().reset_index()
    df_tiempos_melt = df_tiempos_rest.melt(
        id_vars="NombreSucursal",
        value_vars=["TiempoTomaMin", "TiempoCocinaMin", "TiempoEntregaMin"],
        var_name="Etapa",
        value_name="Minutos"
    )
    nombres_etapa = {
        "TiempoTomaMin": "1. Toma de Pedido",
        "TiempoCocinaMin": "2. Preparación Cocina",
        "TiempoEntregaMin": "3. Entrega en Mesa"
    }
    df_tiempos_melt["Etapa"] = df_tiempos_melt["Etapa"].map(nombres_etapa)

    fig_tiempos = px.bar(
        df_tiempos_melt,
        x="Minutos",
        y="NombreSucursal",
        color="Etapa",
        orientation="h",
        title="Desglose de Tiempos de Atención por Restaurante (min)",
        labels={"NombreSucursal": "Restaurante", "Minutos": "Promedio (min)"},
        color_discrete_sequence=["#F4A261", "#E76F51", "#2A9D8F"]
    )
    st.plotly_chart(fig_tiempos, width="stretch")

with c2:
    df_evol = df_f.groupby("Periodo").agg(
        TiempoAtencion=("TiempoTotalAtencionMin", "mean"),
        CumpleSLA=("CumpleSLA", lambda x: x.mean() * 100)
    ).reset_index()

    fig_evol = px.line(
        df_evol,
        x="Periodo",
        y="TiempoAtencion",
        markers=True,
        title="Evolución Mensual del Tiempo de Atención (2025 vs 2026)",
        labels={"Periodo": "Mes", "TiempoAtencion": "Tiempo Promedio (min)"}
    )
    fig_evol.add_hline(y=17, line_dash="dash", line_color="green", annotation_text="Meta SLA (17 min)")
    fig_evol.update_traces(line=dict(width=3, color="#D62828"))
    st.plotly_chart(fig_evol, width="stretch")

# Fila 2 de gráficos: Congestión Horas Punta y Productividad Mozos/Cuadrantes
c3, c4 = st.columns(2)

with c3:
    orden_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    df_heat = df_f.groupby(["DiaSemana", "FranjaHoraria"]).agg(
        Pedidos=("IdOrden", "count"),
        MesasUnicas=("NumeroMesa", "nunique")
    ).reset_index()

    fig_heat = px.density_heatmap(
        df_heat,
        x="FranjaHoraria",
        y="DiaSemana",
        z="Pedidos",
        category_orders={"DiaSemana": orden_dias},
        color_continuous_scale="YlOrRd",
        text_auto=True,
        title="Mapa de Calor: Congestión de Pedidos por Día y Franja Horaria",
        labels={"FranjaHoraria": "Franja Horaria", "DiaSemana": "Día", "Pedidos": "Cantidad Pedidos"}
    )
    st.plotly_chart(fig_heat, width="stretch")

with c4:
    df_mozo = df_f.groupby(["NombreCompleto", "Cuadrante"]).agg(
        TiempoPromedio=("TiempoTotalAtencionMin", "mean"),
        PorcSLA=("CumpleSLA", lambda x: x.mean() * 100),
        Pedidos=("IdOrden", "count")
    ).reset_index().sort_values("TiempoPromedio", ascending=True)

    fig_mozo = px.bar(
        df_mozo.head(12),
        x="TiempoPromedio",
        y="NombreCompleto",
        color="Cuadrante",
        orientation="h",
        title="Productividad por Mozo y Cuadrante (Top 12 más rápidos)",
        labels={"NombreCompleto": "Mozo", "TiempoPromedio": "Tiempo Atención (min)"}
    )
    fig_mozo.add_vline(x=17, line_dash="dash", line_color="green")
    st.plotly_chart(fig_mozo, width="stretch")

# Fila 3: Ventas y Tiempos por Categoría y Producto
c5, c6 = st.columns(2)

with c5:
    df_cat = df_f.groupby("CategoriaPlato").agg(
        Ventas=("MontoTotal", "sum"),
        TiempoCocina=("TiempoCocinaMin", "mean")
    ).reset_index().sort_values("Ventas", ascending=False)

    fig_cat = px.bar(
        df_cat,
        x="CategoriaPlato",
        y="Ventas",
        color="TiempoCocina",
        title="Ventas (S/) y Tiempo Promedio de Cocina por Categoría de Plato",
        labels={"CategoriaPlato": "Categoría", "Ventas": "Monto Total (S/)", "TiempoCocina": "Cocina (min)"},
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_cat, width="stretch")

with c6:
    df_permanencia = df_f.groupby("NombreSucursal").agg(
        Permanencia=("TiempoPermanenciaMin", "mean"),
        Cobro=("TiempoCobroMin", "mean"),
        MesasOcupadas=("NumeroMesa", "nunique")
    ).reset_index()

    fig_perm = px.bar(
        df_permanencia,
        x="NombreSucursal",
        y=["Permanencia", "Cobro"],
        barmode="group",
        title="Rotación de Salón: Tiempo Permanencia y Cobro por Local (min)",
        labels={"NombreSucursal": "Restaurante", "value": "Minutos Promedio", "variable": "Indicador"}
    )
    st.plotly_chart(fig_perm, width="stretch")