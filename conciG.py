import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from io import BytesIO
import numpy as np



# -----------------------
# LOGIN BÁSICO (MVP)
# -----------------------

#WEBHOOK PARA LOG LOGING
N8N_WEBHOOK_LOG_LOGIN_PRODUCTION = 'https://operationskashio.app.n8n.cloud/webhook/log-login'
N8N_WEBHOOK_LOG_LOGIN_TEST = 'https://operationskashio.app.n8n.cloud/webhook-test/log-login'

USERS = {
    "operaciones_gmoney": "gmoney123",
    "analista_ops": "ops123"
}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None


@st.dialog("Login - Conciliación GMoney")
def login_dialog():

    with st.form("login_form"):
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")

        if submitted:
            if user in USERS and USERS[user] == password:
                #log login n8n
                payload = {
                    'usuario': user,
                    'rol': user,
                    'timestamp': datetime.now().isoformat()
                }

                try:
                    requests.post(N8N_WEBHOOK_LOG_LOGIN_PRODUCTION, json=payload, timeout=3)
                except Exception as e:
                    pass
                
                st.session_state.authenticated = True
                st.session_state.user = user
                st.success("Acceso correcto")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")


def logout():
    st.session_state.clear()
    st.rerun()


# -----------------------
# BLOQUEO TOTAL SIN LOGIN
# -----------------------
if not st.session_state.authenticated:
    login_dialog()
    st.stop()


st.set_page_config(page_title="Conciliacion Operaciones GMoney",  page_icon="📄")
st.title("📄 Conciliacion Operaciones GMoney") 

# Inicializar session_state
if 'opePendientes' not in st.session_state:
    st.session_state.opePendientes = None
if 'opeConciliar' not in st.session_state:
    st.session_state.opeConciliar = None
if 'operaciones_completas' not in st.session_state:
    st.session_state.operaciones_completas = None
if 'operaciones_gmoney' not in st.session_state:
    st.session_state.operaciones_gmoney = None
if 'totales_gmoney' not in st.session_state:
    st.session_state.totales_gmoney = None
if 'excel_content' not in st.session_state:
    st.session_state.excel_content = None


# Columnas innecesarias que seran eliminadas
columns_drop = [
    'cus_public_id',
    'category',
    'po_public_id',
    'po_referencia',
    'referencia',
    'debtor_public_id',
    'cuenta',
    'tipo_de_cuenta'
]

# SUBIDA DE ARCHIVOS
archivoDia = st.file_uploader('Archivo operaciones día anterior', type=['xlsx'])

# st.subheader("Archivo Metabase")
# col1, col2 = st.columns(2)

# with col1:
#     archivosPendientes = st.file_uploader("Archivo operaciones pendientes: ", type=["xlsx"])

# with col2:
#     archivoDia = st.file_uploader("Archivo operaciones día anterior: ", type=["xlsx"])


# # Procesamiento archivo pendientes
# if archivosPendientes:
#     df_temp_pend = pd.read_excel(archivosPendientes)
#     df_temp_pend = df_temp_pend[df_temp_pend['estado'] == "Pagado"]
#     df_temp_pend.drop(columns=columns_drop, inplace=True)
#     df_temp_pend['fecha'] = pd.to_datetime(df_temp_pend['creacion_deuda_fecha_peru']).dt.strftime('%Y-%m-%d')
#     df_temp_pend['hora'] = df_temp_pend['creacion_deuda_fecha_peru'].dt.hour
#     st.session_state.opePendientes = df_temp_pend


# Procesamiento archivo del día
if archivoDia:
    def calcular_ventana_conciliacion_auto():
        """
        Calcula automáticamente la ventana de conciliación según el día actual.

        Reglas:
        - Corte siempre a las 16:00.
        - Martes a Viernes:
            Inicio = día anterior 16:00
            Fin    = hoy 16:00
        - Lunes:
            Inicio = viernes anterior 16:00
            Fin    = lunes 16:00

        Retorna:
        - inicio (Timestamp)
        - fin    (Timestamp)
        """

        hoy = pd.Timestamp.now().normalize()
        corte = pd.Timedelta(hours=16)

        # weekday(): lunes=0 ... domingo=6
        if hoy.weekday() == 0:  # lunes
            inicio = hoy - pd.Timedelta(days=11) + corte  # viernes 16:00 (days=3) cuando se ttermine
        else:
            inicio = hoy - pd.Timedelta(days=9) + corte  # día anterior 16:00 (days=1) cuando se ttermine

        fin = hoy - pd.Timedelta(days=8) + corte

        return inicio, fin
    
    inicio, fin = calcular_ventana_conciliacion_auto()
    
    df_temp_dia = pd.read_excel(archivoDia)
    df_temp_dia.drop(columns=columns_drop, inplace=True)
    df_temp_dia = df_temp_dia[df_temp_dia['estado'] == "Pagado"]
    df_temp_dia['fecha'] = pd.to_datetime(df_temp_dia['creacion_deuda_fecha_peru']).dt.strftime('%Y-%m-%d')
    df_temp_dia['hora'] = df_temp_dia['creacion_deuda_fecha_peru'].dt.hour
    df_temp_dia['numero_documento'] = df_temp_dia['numero_documento'].astype(str)
    df_temp_dia = df_temp_dia[(df_temp_dia['creacion_deuda_fecha_peru'] >= inicio) &  (df_temp_dia['creacion_deuda_fecha_peru'] < fin)]

    st.session_state.opeConciliar = df_temp_dia

# Mostrar operaciones completas si existen ambos archivos
if st.session_state.opeConciliar is not None:
    # # Operaciones hasta las 4 pm
    # ope_after4 = st.session_state.opeConciliar[st.session_state.opeConciliar['hora'] < 16]
    # # Operaciones despues de las 4pm para proxima conciliacion
    # ope_before4 = st.session_state.opeConciliar[st.session_state.opeConciliar['hora'] > 16]

    # st.session_state.operaciones_completas = pd.concat(
    #     [st.session_state.opePendientes, ope_after4],
    #     ignore_index=True
    # )

    # Mostrar totales por fecha
    totales_por_fecha_metabase = pd.pivot_table(
        st.session_state.opeConciliar,
        values='total',
        index='fecha',
        aggfunc='sum'
    )

    new_cols = {
        'total':'total_metabase'
    }

    totales_por_fecha_metabase.rename(columns=new_cols, inplace=True)

    st.dataframe(totales_por_fecha_metabase, use_container_width=True)


# CONVERSION TXT A EXCEL

st.subheader("Archivo Gmoney")
# URL webhook conexion n8n
N8N_WEBHOOK_CONVERSION_POST = "https://operationskashio.app.n8n.cloud/webhook/e0766639-be53-4bf5-9bfb-c1b34bafac6e"
N8N_WEBHOOK_CONVERSION__TEST = "https://operationskashio.app.n8n.cloud/webhook-test/e0766639-be53-4bf5-9bfb-c1b34bafac6e"

gmoney_txt = st.file_uploader("Archivo txt Gmoney", type=["txt"])

if gmoney_txt:
    file = {
        "gmoney_txt": (
            gmoney_txt.name,
            gmoney_txt.getvalue(),
            "text/plain"
        )
    }

    response = requests.post(N8N_WEBHOOK_CONVERSION_POST, files=file)

    if response.status_code == 200:
        st.success("Archivo convertido correctamente")

        excel_bytes = BytesIO(response.content)
        df_gmoney = pd.read_excel(excel_bytes)
        
        # Filtrar por las operaciones aprobadas ANTES de guardar
        df_gmoney_filtrado = df_gmoney[df_gmoney['estado'] == "A"]

        st.session_state.operaciones_gmoney = df_gmoney_filtrado
        
        # Totales por fecha del archivo de gmoney
        totales_por_fecha_gmoney = pd.pivot_table(
            df_gmoney_filtrado,
            values='monto_gmoney',
            index='fecha',
            aggfunc='sum'
        )
        
        st.session_state.totales_gmoney = totales_por_fecha_gmoney
        st.session_state.excel_content = response.content
        
        #st.dataframe(st.session_state.operaciones_gmoney, use_container_width=True)
        st.dataframe(totales_por_fecha_gmoney, use_container_width=True)

        # fecha_descarga = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        # nombre_archivo = f"gmoney_movimientos_{fecha_descarga}.xlsx"

        # st.download_button(
        #     label="Descargar movimientos GMoney",
        #     data=response.content,
        #     file_name=nombre_archivo,
        #     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        #     use_container_width=True
        # )

    st.subheader("Conciliación de montos diarios")
    st.write(
        "Resultado de la conciliación de los montos totales agregados por día, "
        "comparando la suma de las operaciones entre las distintas fuentes de información."
    )


    N8N_DISCREPANCIAS_IMPORTES_P = 'https://operationskashio.app.n8n.cloud/webhook/discrepancias-impotes'
    N8N_DISCREPANCIAS_IMPORTES_T = 'https://operationskashio.app.n8n.cloud/webhook-test/discrepancias-impotes'

    #realizamos el cuadre
    conciliacion_operaciones = pd.merge(
        totales_por_fecha_metabase,
        st.session_state.totales_gmoney,
        how='inner',
        on='fecha'
    )

    conciliacion_operaciones['diferencias'] = conciliacion_operaciones['total_metabase'] - conciliacion_operaciones['monto_gmoney']


    conciliacion_operaciones['estado'] = np.where(
        conciliacion_operaciones['diferencias'] == 0,
        'Conciliado',
        'Diferencias'
    )
    st.dataframe(conciliacion_operaciones, use_container_width=True)

    usuario = st.session_state.user
    timestamp_ejecucion = datetime.now().isoformat()

    for _, row in conciliacion_operaciones.iterrows():
        payload = {
            'fecha':str(row['fecha']),
            'total_metabase': float(row['total_metabase']),
            'total_gmoney': float(row['total_gmoney']),
            'diferencias': float(row['diferencias']),
            'estado': row['estado'],
            'usuario': usuario,
            'timestamp_ejecucion': timestamp_ejecucion
        }

        try:
            requests.post(
                N8N_DISCREPANCIAS_IMPORTES_P,
                json=payload,
                timeout=5
            )
        except Exception:
            pass

    st.subheader("Conciliación por detalle de operaciones")
    st.write(
        "Resultado de la conciliación a nivel de operación individual, "
        "comparando los montos registrados por día entre las fuentes de información."
    )

    st.session_state.opeConciliar.rename(columns={'numero_operacion': 'id_operacion'}, inplace=True)
    st.session_state.operaciones_gmoney.rename(columns={'id_transaccion_cce': 'id_operacion'}, inplace=True)

    conciliacion_merge =   st.session_state.opeConciliar.merge(
            st.session_state.operaciones_gmoney,
            on='id_operacion',
            how='outer',
            suffixes=('_meta', '_gmoney'),
            indicator=True
        )
 
    def clasificar_resultado(row):
        if row['_merge'] == 'left_only':
            return 'Diferencia Estructural - Gmoney'
        if row['_merge'] == 'right_only':
            return 'Diferencia Estructural - Metabase'
        if row['total'] != row['monto_gmoney']:
            return 'Diferencia Importe'
        return '✅ OK'

    conciliacion_merge['resultado'] = conciliacion_merge.apply(
    clasificar_resultado, axis=1
)

    conciliacion_merge['diferencias_importe'] = conciliacion_merge['total'] - conciliacion_merge['monto_gmoney']

    #conciliacion_merge
    reporte_diferencias = conciliacion_merge[conciliacion_merge['diferencias_importe'] != 0]

    cols_to_drop = [
        "operador_dispersion",
        "estado",
        "fecha_pagado_rechazado_peru",
        "itf",
        "comision_destino",
        "comision_origen",
        'cci',
        "yape_id",
        "bbva_id",
        "fecha",
        "hora",
        'Unnamed: 21',
        'diferencias',
        'tipo_de_documento',
        'numero_documento',
        'cliente',
        'identificativo_mv',
        'cci_origen',
        'cci_destino_tarjeta',
        'importe',
        'importe_comision',
        'signo_comision',
        'tipo_transferencia',
        'fecha_hora',
        'canal',
        'referencia',
        'codigo_proceso',
        'estado_gmoney',
        'entidad_destino',
        'filler',
        'dni',
        '_merge'
    ]

    reporte_diferencias = reporte_diferencias.drop(columns=cols_to_drop, errors="ignore")
    cantidad_diferencias = len(reporte_diferencias)

    if cantidad_diferencias > 0:
        st.dataframe(reporte_diferencias, use_container_width=True)
        st.warning(f"Se identificaron {cantidad_diferencias} diferencias.")
    else:
        st.success(f'No se encontraron diferencias en la conciliacion.')

    