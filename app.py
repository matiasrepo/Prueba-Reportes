import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="RMA Report", layout="wide", page_icon="🍏")

st.markdown("""
    <style>
        .stApp { background-color: #FFFFFF; color: #1D1D1F; font-family: -apple-system, sans-serif; }
        #MainMenu, footer, header {visibility: hidden;}

        .header-container { border-bottom: 1px solid #E5E5E5; padding-bottom: 20px; margin-bottom: 20px; }
        .main-title { font-size: 28px; font-weight: 700; }
        .sub-title { color: #86868b; font-size: 14px; }

        /* Métricas con comparación */
        div[data-testid="stMetric"] { background-color: #F5F5F7; border-radius: 12px; padding: 15px; border: none; }

        /* Tabla */
        div[data-testid="stDataFrame"] { border: 1px solid #E5E5E5; border-radius: 10px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)


# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    archivo = 'ReporteSemanalMovimientos.xlsx'
    hoja = 'Bruto Reportes Nuevo'
    try:
        df = pd.read_excel(archivo, sheet_name=hoja)

        cols_fecha = ['FECHA_COMPRA', 'FECHA_VENTA', 'FECHA_RMA']
        for col in cols_fecha:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

        df[['SEMANA', 'AGENTE', 'GESTOR']] = df[['SEMANA', 'AGENTE', 'GESTOR']].astype(str)
        df['COSTO_USD+'] = pd.to_numeric(df['COSTO_USD+'], errors='coerce').fillna(0)
        df['CANTIDAD_REGISTROS'] = pd.to_numeric(df['CANTIDAD_REGISTROS'], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()


df = cargar_datos()

# --- ENCABEZADO ---
st.markdown(f"""
    <div class="header-container">
        <div class="main-title">Control de RMA</div>
        <div class="sub-title">Comparativa Semanal • {datetime.now().strftime('%d/%m/%Y')}</div>
    </div>
""", unsafe_allow_html=True)

if df.empty:
    st.error("No se pudieron cargar los datos.")
    st.stop()

# --- 1. FILTROS PRINCIPALES ---
c1, c2 = st.columns([1, 3])
with c1:
    agente_sel = st.selectbox("Seleccionar Agente", sorted(df['AGENTE'].unique()))

# Filtrar datos del agente
df_agente = df[df['AGENTE'] == agente_sel]
semanas_disponibles = sorted(df_agente['SEMANA'].unique())

if not semanas_disponibles:
    st.warning("Este agente no tiene datos.")
    st.stop()

# --- 2. SELECTORES DE TIEMPO (COMPARATIVA) ---
with st.container():
    col_a, col_b, col_c = st.columns([1, 1, 2])

    with col_a:
        # Por defecto selecciona la última semana
        idx_act = len(semanas_disponibles) - 1
        semana_act = st.selectbox("Semana Actual", semanas_disponibles, index=idx_act)

    with col_b:
        # Por defecto selecciona la penúltima (para comparar)
        idx_ant = max(0, idx_act - 1)
        semana_ant = st.selectbox("Comparar contra", semanas_disponibles, index=idx_ant)

    with col_c:
        gestores = sorted(df_agente['GESTOR'].unique())
        gestor_sel = st.multiselect("Filtrar Gestores", gestores, placeholder="Todos")

# --- 3. CÁLCULO DE DIFERENCIAS (DELTAS) ---
# Datos Actuales
df_act = df_agente[df_agente['SEMANA'] == semana_act]
if gestor_sel: df_act = df_act[df_act['GESTOR'].isin(gestor_sel)]

# Datos Anteriores
df_ant = df_agente[df_agente['SEMANA'] == semana_ant]
if gestor_sel: df_ant = df_ant[df_ant['GESTOR'].isin(gestor_sel)]

# Totales Globales
monto_act = df_act['COSTO_USD+'].sum()
monto_ant = df_ant['COSTO_USD+'].sum()
delta_monto = monto_act - monto_ant

unds_act = df_act['CANTIDAD_REGISTROS'].sum()
unds_ant = df_ant['CANTIDAD_REGISTROS'].sum()
delta_unds = unds_act - unds_ant

# KPI Cards con Deltas
k1, k2, k3, k4 = st.columns(4)
k1.metric("Monto Pendiente", f"${monto_act:,.2f}", f"{delta_monto:+,.2f}", delta_color="inverse")
k2.metric("Unidades", f"{int(unds_act)}", f"{int(delta_unds):+}", delta_color="inverse")
k3.metric("Comparativa", f"{semana_ant} ➡ {semana_act}")
k4.metric("Registros", len(df_act))

st.markdown("###")

# --- 4. TABLA COMPARATIVA DETALLADA ---
tab1, tab2 = st.tabs(["📄 Detalle Comparativo", "📊 Gráficos"])

with tab1:
    if not df_act.empty:
        # Preparamos la tabla base con los datos actuales
        base = df_act[['GESTOR', 'COSTO_USD+', 'CANTIDAD_REGISTROS', 'FECHA_COMPRA', 'FECHA_RMA']].copy()

        # --- MAGIA: Calcular variación por fila ---
        # Agrupamos la semana anterior por gestor para poder cruzar datos
        ref_ant = df_ant.groupby('GESTOR')['COSTO_USD+'].sum().reset_index()

        # Cruzamos (Merge) para traer el monto anterior a la fila del gestor
        merged = pd.merge(base, ref_ant, on='GESTOR', how='left', suffixes=('', '_ANT')).fillna(0)
        merged['VAR_USD'] = merged['COSTO_USD+'] - merged['COSTO_USD+_ANT']

        # Ordenamos
        merged = merged.sort_values('COSTO_USD+', ascending=False)

        st.dataframe(
            merged,
            column_config={
                "GESTOR": st.column_config.TextColumn("Gestor", width="medium"),
                "COSTO_USD+": st.column_config.ProgressColumn(
                    "Monto Actual",
                    format="$%.2f",
                    min_value=0,
                    max_value=max(merged['COSTO_USD+'].max(), 100),
                    width="medium"
                ),
                "VAR_USD": st.column_config.NumberColumn(
                    "Var. $",
                    format="$%+.2f",  # Muestra el signo + o -
                    help="Diferencia de dinero respecto a la semana comparada"
                ),
                "CANTIDAD_REGISTROS": st.column_config.NumberColumn("Unds", format="%d"),
                "FECHA_COMPRA": st.column_config.DateColumn("F. Compra", format="DD/MM/YYYY"),
                "FECHA_RMA": st.column_config.DateColumn("F. RMA", format="DD/MM/YYYY"),
                "COSTO_USD+_ANT": None  # Ocultamos columna auxiliar
            },
            hide_index=True,
            use_container_width=True,
            height=600
        )
    else:
        st.info("No hay datos para esta selección.")

with tab2:
    if not df_act.empty:
        c_g1, c_g2 = st.columns([2, 1])
        g_data = df_act.groupby('GESTOR')[['COSTO_USD+']].sum().reset_index().sort_values('COSTO_USD+')

        with c_g1:
            fig = px.bar(g_data, x='COSTO_USD+', y='GESTOR', orientation='h', color='COSTO_USD+',
                         color_continuous_scale='Reds')
            fig.update_layout(template='plotly_white', xaxis_title=None, yaxis_title=None, showlegend=False, height=400)
            st.plotly_chart(fig, use_container_width=True)

        with c_g2:
            fig_p = px.pie(g_data, values='COSTO_USD+', names='GESTOR', hole=0.6,
                           color_discrete_sequence=px.colors.sequential.Greys_r)
            fig_p.update_layout(template='plotly_white', showlegend=False)
            st.plotly_chart(fig_p, use_container_width=True)