import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

# ----------------------------------
# CONFIG
# ----------------------------------
st.set_page_config(
    page_title="Depósitos sin Notificación - Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stMetric:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        transform: translateY(-2px);
        transition: all 0.3s ease;
    }
    h1 {
        color: #1f77b4;
        font-weight: 700;
    }
    h2 {
        color: #2c3e50;
        font-weight: 600;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 10px;
    }
    h3 {
        color: #34495e;
        font-weight: 500;
    }
    .highlight-box {
        background-color: #e8f4f8;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------
# LOAD DATA
# ----------------------------------
@st.cache_data(ttl=300)  # Cache por 5 minutos (300 segundos)
def load_data():
    # Lectura excel de DSN principal
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    #DATA_PATH = os.path.join(BASE_DIR, "data", "01 ENERO.xlsx")
    DATA_PATH = os.path.join(BASE_DIR, "data", "DSN REC ONLINE.xlsx")
    #path_excel = r'C:\Users\Dussand\OneDrive\Desktop\BPA\KASHIO\Business Process Analyst\Payins\AUT.Conciliacion-Gmoney\conciliacion-Gmoney\01 ENERO.xlsx'
    excel_dsn = pd.read_excel(DATA_PATH)
    
    # Eliminar columnas nan
    columnas_drop = {
        'PSP_TIN',
        'PSP_TIN concatenado',
        'Public ID',
        'inv_id concatenado',
        'RONDA',
        'Sustento',
        'Unnamed: 21',
        'Unnamed: 22',
        'Unnamed: 23',
        'Unnamed: 24',
        'Unnamed: 25',
        'Nro OP'
    }
    
    # Eliminar solo las columnas que existen
    columnas_existentes = [col for col in columnas_drop if col in excel_dsn.columns]
    excel_dsn = excel_dsn.drop(columns=columnas_existentes)
    
    # Procesamiento de fechas y columnas adicionales
    excel_dsn["fecha_revision"] = pd.to_datetime(excel_dsn["fecha_revision"], dayfirst=True, errors='coerce')
    excel_dsn = excel_dsn.dropna(subset=["fecha_revision"])
    excel_dsn["Año"] = excel_dsn["fecha_revision"].dt.year
    excel_dsn["Mes_Num"] = excel_dsn["fecha_revision"].dt.month
    excel_dsn["Dia_Semana"] = excel_dsn["fecha_revision"].dt.day_name()
    excel_dsn["Semana"] = excel_dsn["fecha_revision"].dt.isocalendar().week
    
    # Agregar columna Mes con nombre en español
    meses_nombres = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    excel_dsn["Mes"] = excel_dsn["Mes_Num"].map(meses_nombres)
    
    # Lectura excel de Rec. Diaria (DSN EN LINEA)
    BASE_DIR_DIARIA= os.path.dirname(os.path.abspath(__file__))
    DATA_PATH_DIARIA= os.path.join(BASE_DIR_DIARIA, "data", "DSN EN LINEA Y CONCILIACIÓN.xlsx")
    #path_rec_diaria = r'C:\Users\Dussand\OneDrive\Desktop\BPA\KASHIO\Business Process Analyst\Payins\AUT.Conciliacion-Gmoney\conciliacion-Gmoney\DSN EN LINEA Y CONCILIACIÓN.xlsx'
    excel_rec_diaria = pd.read_excel(DATA_PATH_DIARIA, sheet_name='Reconciliación DSN')
    
    # Filtrar solo filas con PSP_TIN no vacío y contar
    rec_diaria_count = excel_rec_diaria['PSP_TIN'].notna().sum()
    
    # Extraer fechas si existen (sin modificar VOUCHER_FECHA)
    if 'VOUCHER_FECHA' in excel_rec_diaria.columns:
        excel_rec_diaria_filtrado = excel_rec_diaria[excel_rec_diaria['PSP_TIN'].notna()].copy()
        # Intentar convertir fechas de manera segura
        try:
            excel_rec_diaria_filtrado['VOUCHER_FECHA'] = pd.to_datetime(
                excel_rec_diaria_filtrado['VOUCHER_FECHA'], 
                errors='coerce',
                dayfirst=True
            )
            excel_rec_diaria_filtrado = excel_rec_diaria_filtrado[excel_rec_diaria_filtrado['VOUCHER_FECHA'].notna()]
            excel_rec_diaria_filtrado["Año"] = excel_rec_diaria_filtrado["VOUCHER_FECHA"].dt.year
            excel_rec_diaria_filtrado["Mes_Num"] = excel_rec_diaria_filtrado["VOUCHER_FECHA"].dt.month
            
            # Agregar columna Mes con nombre en español
            meses_nombres = {
                1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
            }
            excel_rec_diaria_filtrado["Mes"] = excel_rec_diaria_filtrado["Mes_Num"].map(meses_nombres)
        except:
            # Si falla, crear estructura básica solo con conteo
            excel_rec_diaria_filtrado = pd.DataFrame()
    else:
        excel_rec_diaria_filtrado = pd.DataFrame()
    
    return excel_dsn, rec_diaria_count, excel_rec_diaria_filtrado

try:
    excel_dsn, rec_diaria_count, rec_diaria_extra = load_data()
    data_loaded = True
    
    # Mostrar última actualización
    st.sidebar.markdown("---")
    st.sidebar.success(f"✅ Datos cargados")
    st.sidebar.caption(f"📊 DSN Principal: {len(excel_dsn):,} registros")
    st.sidebar.caption(f"📋 Rec. Diaria Extra: {rec_diaria_count:,} registros")
    st.sidebar.caption(f"🕐 Última actualización: {pd.Timestamp.now().strftime('%H:%M:%S')}")
    
    # Botón para refrescar manualmente
    if st.sidebar.button("🔄 Refrescar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
except Exception as e:
    st.error(f"⚠️ Error al cargar los datos: {str(e)}")
    data_loaded = False

# ----------------------------------
# HEADER
# ----------------------------------
st.title("📊 Dashboard de Depósitos sin Notificación")
st.markdown("### Análisis y monitoreo de conciliaciones GMoney")

if not data_loaded:
    st.stop()

# ----------------------------------
# SIDEBAR FILTERS
# ----------------------------------
st.sidebar.image("https://via.placeholder.com/300x100/1f77b4/ffffff?text=DSN+Dashboard")
st.sidebar.header("🔍 Filtros de Análisis")

# Filtro de año
anio = st.sidebar.selectbox(
    "📅 Año",
    sorted(excel_dsn["Año"].unique(), reverse=True),
    help="Selecciona el año a analizar"
)

# CORRECCIÓN: Ajustar rango de fechas según el año seleccionado
df_temp_anio = excel_dsn[excel_dsn["Año"] == anio]

if not df_temp_anio.empty:
    fecha_min = df_temp_anio["fecha_revision"].min().date()
    fecha_max = df_temp_anio["fecha_revision"].max().date()
else:
    # Fallback a todo el dataset si no hay datos para ese año
    fecha_min = excel_dsn["fecha_revision"].min().date()
    fecha_max = excel_dsn["fecha_revision"].max().date()

if pd.isna(fecha_min) or pd.isna(fecha_max):
    st.warning("No hay fechas válidas para construir el rango.")
    st.stop()

# Rango de fechas
fecha_range = st.sidebar.date_input(
    "📅 Rango de fechas",
    [fecha_min, fecha_max],
    min_value=fecha_min,
    max_value=fecha_max,
    help="Define el período de análisis (dentro del año seleccionado)"
)

# Filtro de mes
mes_options = ["Todos"] + sorted(excel_dsn[excel_dsn["Año"] == anio]["Mes"].dropna().unique())
mes = st.sidebar.selectbox(
    "📆 Mes",
    mes_options,
    help="Filtra por mes específico"
)

# Filtro de empresa
empresa_options = ["Todas"] + sorted(excel_dsn["Empresa"].dropna().unique())
empresa = st.sidebar.selectbox(
    "🏢 Empresa",
    empresa_options,
    help="Filtra por empresa"
)

# Filtro de banco
banco_options = ["Todos"] + sorted(excel_dsn["Banco"].dropna().unique())
banco = st.sidebar.selectbox(
    "🏦 Banco",
    banco_options,
    help="Filtra por banco"
)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip**: Usa los filtros para analizar períodos y segmentos específicos")

# ----------------------------------
# APPLY FILTERS - CORRECCIÓN PRINCIPAL
# ----------------------------------
df_f = excel_dsn.copy()

# Filtrar por año
df_f = df_f[df_f["Año"] == anio]

# Aplicar filtro de rango de fechas
if len(fecha_range) == 2:
    fecha_inicio = pd.to_datetime(fecha_range[0])
    fecha_fin = pd.to_datetime(fecha_range[1])
    
    df_f = df_f[
        (df_f["fecha_revision"] >= fecha_inicio) &
        (df_f["fecha_revision"] <= fecha_fin)
    ]

# Aplicar resto de filtros
if mes != "Todos":
    df_f = df_f[df_f["Mes"] == mes]

if empresa != "Todas":
    df_f = df_f[df_f["Empresa"] == empresa]

if banco != "Todos":
    df_f = df_f[df_f["Banco"] == banco]

# Filtrar Rec. Diaria Extra si hay datos con fechas válidas
if not rec_diaria_extra.empty and 'Año' in rec_diaria_extra.columns:
    # Iniciar con todos los datos
    rec_diaria_filtrada = rec_diaria_extra.copy()
    
    # Filtrar por año
    rec_diaria_filtrada = rec_diaria_filtrada[rec_diaria_filtrada["Año"] == anio]
    
    # Aplicar filtro de rango de fechas
    if len(fecha_range) == 2 and 'VOUCHER_FECHA' in rec_diaria_filtrada.columns:
        fecha_inicio = pd.to_datetime(fecha_range[0])
        fecha_fin = pd.to_datetime(fecha_range[1])
        
        rec_diaria_filtrada = rec_diaria_filtrada[
            (rec_diaria_filtrada["VOUCHER_FECHA"] >= fecha_inicio) &
            (rec_diaria_filtrada["VOUCHER_FECHA"] <= fecha_fin)
        ]
    
    # Filtrar por mes si aplica
    if mes != "Todos" and 'Mes' in rec_diaria_filtrada.columns:
        rec_diaria_filtrada = rec_diaria_filtrada[rec_diaria_filtrada["Mes"] == mes]
    
    rec_diaria_extra_count = len(rec_diaria_filtrada)
else:
    rec_diaria_filtrada = pd.DataFrame()
    rec_diaria_extra_count = 0

# ----------------------------------
# KPI CALCULATIONS
# ----------------------------------
total_dsn = len(df_f)

rec_online = df_f[df_f["Tipo2"] == "EECC"]
rec_diaria = df_f[df_f["Tipo2"] == "Reg.interna"]
tickets = df_f[df_f["Tipo2"] == "Ticket"]

# Sumar Rec. Diaria del segundo Excel
total_rec_diaria = len(rec_diaria) + rec_diaria_extra_count

# Total incluyendo rec. diaria extra
total_dsn_completo = total_dsn + rec_diaria_extra_count

def pct(x, total):
    return f"{(x/total*100):.1f}%" if total > 0 else "0%"

# Calcular promedios
promedio_diario = total_dsn_completo / df_f["fecha_revision"].nunique() if df_f["fecha_revision"].nunique() > 0 else 0

# ----------------------------------
# MAIN KPIs
# ----------------------------------
st.markdown("## 📈 Indicadores Principales")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="📦 Total DSN",
        value=f"{total_dsn_completo:,}",
        delta=None,
        help="Total de depósitos sin notificación"
    )

with col2:
    st.metric(
        label="🌐 Rec. Online",
        value=f"{len(rec_online):,}",
        #delta=pct(len(rec_online), total_dsn_completo),
        help="Reconciliaciones mediante EECC"
    )

with col3:
    st.metric(
        label="📋 Rec. Diaria",
        value=f"{total_rec_diaria:,}",
        #delta=pct(total_rec_diaria, total_dsn_completo),
        help="Reconciliaciones internas diarias (incluye DSN en línea)"
    )

with col4:
    st.metric(
        label="🎫 Tickets",
        value=f"{len(tickets):,}",
        #delta=pct(len(tickets), total_dsn_completo),
        help="Casos escalados a tickets"
    )

with col5:
    st.metric(
        label="📊 Promedio/día",
        value=f"{promedio_diario:.1f}",
        help="Promedio de DSN por día"
    )

st.markdown("---")

# ----------------------------------
# GRÁFICOS PRINCIPALES
# ----------------------------------
st.markdown("## 📉 Análisis de Tendencias")

col_left, col_right = st.columns([2, 1])

with col_left:
    # Tendencia temporal con los 3 tipos
    trend_rec_online = (
        df_f[df_f["Tipo2"] == "EECC"]
        .groupby("fecha_revision")
        .size()
        .reset_index(name="Rec_Online")
    )
    
    # Rec. Diaria del primer Excel
    trend_rec_diaria_1 = (
        df_f[df_f["Tipo2"] == "Reg.interna"]
        .groupby("fecha_revision")
        .size()
        .reset_index(name="Rec_Diaria_1")
    )
    
    # Rec. Diaria del segundo Excel (DSN en línea) - solo si hay datos
    if not rec_diaria_filtrada.empty and 'VOUCHER_FECHA' in rec_diaria_filtrada.columns:
        trend_rec_diaria_2 = (
            rec_diaria_filtrada
            .groupby("VOUCHER_FECHA")
            .size()
            .reset_index(name="Rec_Diaria_2")
        )
        trend_rec_diaria_2 = trend_rec_diaria_2.rename(columns={"VOUCHER_FECHA": "fecha_revision"})
    else:
        trend_rec_diaria_2 = pd.DataFrame(columns=["fecha_revision", "Rec_Diaria_2"])
    
    trend_tickets = (
        df_f[df_f["Tipo2"] == "Ticket"]
        .groupby("fecha_revision")
        .size()
        .reset_index(name="Tickets")
    )
    
    if df_f.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        # Usar el rango de fechas filtrado, no todo el dataset
        if len(fecha_range) == 2:
            fecha_range_completo = pd.date_range(
                start=pd.to_datetime(fecha_range[0]),
                end=pd.to_datetime(fecha_range[1]),
                freq="D"
            )
        else:
            fecha_range_completo = pd.date_range(
                start=df_f["fecha_revision"].min(),
                end=df_f["fecha_revision"].max(),
                freq="D"
            )
        
        # Merge de todas las tendencias
        trend_combined = pd.DataFrame({'fecha_revision': fecha_range_completo})
        trend_combined = trend_combined.merge(trend_rec_online, on='fecha_revision', how='left')
        trend_combined = trend_combined.merge(trend_rec_diaria_1, on='fecha_revision', how='left')
        trend_combined = trend_combined.merge(trend_rec_diaria_2, on='fecha_revision', how='left')
        trend_combined = trend_combined.merge(trend_tickets, on='fecha_revision', how='left')
        trend_combined = trend_combined.fillna(0)
        
        # Sumar ambas rec. diarias
        trend_combined['Rec_Diaria'] = trend_combined['Rec_Diaria_1'] + trend_combined['Rec_Diaria_2']
        
        # Crear gráfico con las 3 líneas
        fig_trend = go.Figure()
        
        fig_trend.add_trace(go.Scatter(
            x=trend_combined["fecha_revision"],
            y=trend_combined["Rec_Online"],
            mode='lines+markers',
            name='Rec. Online (EECC)',
            line=dict(color='#1f77b4', width=2.5),
            marker=dict(size=5),
            fill='tonexty',
            fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        fig_trend.add_trace(go.Scatter(
            x=trend_combined["fecha_revision"],
            y=trend_combined["Rec_Diaria"],
            mode='lines+markers',
            name='Rec. Diaria (Reg.interna + En Línea)',
            line=dict(color='#2ca02c', width=2.5),
            marker=dict(size=5),
            fill='tonexty',
            fillcolor='rgba(44, 160, 44, 0.1)'
        ))
        
        fig_trend.add_trace(go.Scatter(
            x=trend_combined["fecha_revision"],
            y=trend_combined["Tickets"],
            mode='lines+markers',
            name='Tickets',
            line=dict(color='#ff7f0e', width=2.5),
            marker=dict(size=5),
            fill='tonexty',
            fillcolor='rgba(255, 127, 14, 0.1)'
        ))
        
        fig_trend.update_layout(
            title="Tendencia de Depósitos sin Notificación por Tipo",
            xaxis_title="Fecha",
            yaxis_title="Cantidad de DSN",
            hovermode='x unified',
            template='plotly_white',
            height=400,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig_trend, use_container_width=True)

with col_right:
    # Distribución por tipo - Donut chart (con rec. diaria extra)
    dist_data = pd.DataFrame({
        "Tipo": ["Rec. Online", "Rec. Diaria", "Tickets"],
        "Cantidad": [len(rec_online), total_rec_diaria, len(tickets)],
        "Color": ["#1f77b4", "#2ca02c", "#ff7f0e"]
    })
    
    fig_donut = go.Figure(data=[go.Pie(
        labels=dist_data["Tipo"],
        values=dist_data["Cantidad"],
        hole=0.5,
        marker=dict(colors=dist_data["Color"]),
        textposition='auto',
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>Cantidad: %{value}<br>Porcentaje: %{percent}<extra></extra>'
    )])
    
    fig_donut.update_layout(
        title="Distribución por Tipo de Flujo",
        height=400,
        showlegend=True,
        template='plotly_white'
    )
    
    st.plotly_chart(fig_donut, use_container_width=True)

st.markdown("---")

# ----------------------------------
# ANÁLISIS POR EMPRESA Y BANCO
# ----------------------------------
st.markdown("## 🏢 Análisis por Empresa y Banco")

col1, col2 = st.columns(2)

with col1:
    # Top 10 empresas
    top_emp = (
        df_f
        .groupby("Empresa")
        .size()
        .reset_index(name="DSN")
        .sort_values("DSN", ascending=False)
        .head(10)
    )
    
    fig_top_emp = px.bar(
        top_emp,
        y="Empresa",
        x="DSN",
        orientation='h',
        title="Top 10 Empresas con más DSN",
        color="DSN",
        color_continuous_scale="Blues",
        text="DSN"
    )
    
    fig_top_emp.update_traces(textposition='outside')
    fig_top_emp.update_layout(
        height=450,
        template='plotly_white',
        yaxis={'categoryorder':'total ascending'}
    )
    
    st.plotly_chart(fig_top_emp, use_container_width=True)

with col2:
    # Top bancos
    top_banco = (
        df_f
        .groupby("Banco")
        .size()
        .reset_index(name="DSN")
        .sort_values("DSN", ascending=False)
        .head(10)
    )
    
    fig_top_banco = px.bar(
        top_banco,
        y="Banco",
        x="DSN",
        orientation='h',
        title="Top 10 Bancos con más DSN",
        color="DSN",
        color_continuous_scale="Greens",
        text="DSN"
    )
    
    fig_top_banco.update_traces(textposition='outside')
    fig_top_banco.update_layout(
        height=450,
        template='plotly_white',
        yaxis={'categoryorder':'total ascending'}
    )
    
    st.plotly_chart(fig_top_banco, use_container_width=True)

st.markdown("---")

# ----------------------------------
# ANÁLISIS TEMPORAL DETALLADO
# ----------------------------------
st.markdown("## 📅 Análisis Temporal Detallado")

tab1, tab2, tab3 = st.tabs(["📊 Por Día de Semana", "📈 Por Semana", "🔍 Heatmap Mensual"])

with tab1:
    # Análisis por día de semana
    dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    dias_esp = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    dia_semana = (
        df_f
        .groupby("Dia_Semana")
        .size()
        .reindex(dias_orden, fill_value=0)
        .reset_index(name="DSN")
    )
    dia_semana["Dia_ESP"] = dias_esp
    
    fig_dias = px.bar(
        dia_semana,
        x="Dia_ESP",
        y="DSN",
        title="Distribución de DSN por Día de la Semana",
        color="DSN",
        color_continuous_scale="Viridis",
        text="DSN"
    )
    
    fig_dias.update_traces(textposition='outside')
    fig_dias.update_layout(
        height=400,
        template='plotly_white',
        xaxis_title="Día de la Semana",
        yaxis_title="Cantidad de DSN"
    )
    
    st.plotly_chart(fig_dias, use_container_width=True)

with tab2:
    # Análisis por semana
    semana = (
        df_f
        .groupby("Semana")
        .size()
        .reset_index(name="DSN")
    )
    
    fig_semana = px.line(
        semana,
        x="Semana",
        y="DSN",
        title="Evolución de DSN por Semana del Año",
        markers=True
    )
    
    fig_semana.update_traces(
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8, color='#ff7f0e')
    )
    
    fig_semana.update_layout(
        height=400,
        template='plotly_white',
        xaxis_title="Semana del Año",
        yaxis_title="Cantidad de DSN"
    )
    
    st.plotly_chart(fig_semana, use_container_width=True)

with tab3:
    # Heatmap mensual
    df_f["Dia_Mes"] = df_f["fecha_revision"].dt.day
    
    heatmap_data = (
        df_f
        .groupby(["Mes_Num", "Dia_Mes"])
        .size()
        .reset_index(name="DSN")
    )
    
    pivot_heat = heatmap_data.pivot(index="Mes_Num", columns="Dia_Mes", values="DSN").fillna(0)
    
    fig_heat = px.imshow(
        pivot_heat,
        labels=dict(x="Día del Mes", y="Mes", color="DSN"),
        title="Mapa de Calor - DSN por Mes y Día",
        color_continuous_scale="RdYlGn_r",
        aspect="auto"
    )
    
    fig_heat.update_layout(
        height=400,
        template='plotly_white'
    )
    
    st.plotly_chart(fig_heat, use_container_width=True)

st.markdown("---")

# ----------------------------------
# TABLA DETALLADA POR BANCO
# ----------------------------------
st.markdown("## 🏦 Resumen Detallado por Banco")

tabla_banco = (
    df_f
    .groupby("Banco")
    .agg(
        Total_DSN=("Tipo2", "count"),
        Rec_Diaria=("Tipo2", lambda x: (x == "Reg.interna").sum()),
        Rec_Online=("Tipo2", lambda x: (x == "EECC").sum()),
        Tickets=("Tipo2", lambda x: (x == "Ticket").sum())
    )
    .reset_index()
)

# Calcular porcentajes
tabla_banco["% Rec_Diaria"] = (tabla_banco["Rec_Diaria"] / tabla_banco["Total_DSN"] * 100).round(1)
tabla_banco["% Rec_Online"] = (tabla_banco["Rec_Online"] / tabla_banco["Total_DSN"] * 100).round(1)
tabla_banco["% Tickets"] = (tabla_banco["Tickets"] / tabla_banco["Total_DSN"] * 100).round(1)

# Ordenar por total
tabla_banco = tabla_banco.sort_values("Total_DSN", ascending=False)

st.dataframe(
    tabla_banco,
    use_container_width=True,
    height=400,
    column_config={
        "Banco": st.column_config.TextColumn("🏦 Banco", width="medium"),
        "Total_DSN": st.column_config.NumberColumn("📦 Total DSN", format="%d"),
        "Rec_Diaria": st.column_config.NumberColumn("📋 Rec. Diaria", format="%d"),
        "Rec_Online": st.column_config.NumberColumn("🌐 Rec. Online", format="%d"),
        "Tickets": st.column_config.NumberColumn("🎫 Tickets", format="%d"),
        "% Rec_Diaria": st.column_config.NumberColumn("% Rec. Diaria", format="%.1f%%"),
        "% Rec_Online": st.column_config.NumberColumn("% Rec. Online", format="%.1f%%"),
        "% Tickets": st.column_config.NumberColumn("% Tickets", format="%.1f%%"),
    }
)

# ----------------------------------
# ESTADÍSTICAS ADICIONALES
# ----------------------------------
st.markdown("---")
st.markdown("## 📊 Estadísticas Adicionales")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="highlight-box">', unsafe_allow_html=True)
    st.markdown("### 🏢 Empresas Únicas")
    st.metric("Total", df_f["Empresa"].nunique())
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="highlight-box">', unsafe_allow_html=True)
    st.markdown("### 🏦 Bancos Activos")
    st.metric("Total", df_f["Banco"].nunique())
    st.markdown("</div>", unsafe_allow_html=True)

with col3:
    st.markdown('<div class="highlight-box">', unsafe_allow_html=True)
    st.markdown("### 📅 Días Analizados")
    st.metric("Total", df_f["fecha_revision"].nunique())
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------
# FOOTER
# ----------------------------------
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #7f8c8d; padding: 20px;'>
    <p>📊 Dashboard de Depósitos sin Notificación | Última actualización: {}</p>
    <p>💼 Business Process Analyst | Payins - GMoney</p>
</div>
""".format(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")), unsafe_allow_html=True)