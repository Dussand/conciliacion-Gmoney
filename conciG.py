import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from io import BytesIO
import time


# Configuración de la página
st.set_page_config(
    page_title="Conciliación G-Money",
    page_icon="💰",
    layout="wide"
)

# Configuración
N8N_LOGIN_PRODUCTION = 'https://operationskashio.app.n8n.cloud/webhook/login-conciliacion-gmoney'
N8N_LOGIN_TEST = 'https://operationskashio.app.n8n.cloud/webhook-test/login-conciliacion-gmoney'

SESSION_TIMEOUT_MINUTES = 30
TIMEZONE = pytz.timezone('America/Lima')

USERS = {
    "operador_payments": {
        "password": "gmoney123",
        "tipo": "operador"
    },
    "admin_gmoney": {
        "password": "admin123",
        "tipo": "admin"
    },
    "supervisor_gmoney": {
        "password": "supervisor123",
        "tipo": "supervisor"
    },
        "operador_support": {
        "password": "Soporte2026$",
        "tipo": "soporte"
    }
}

# Inicializar session_state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.login_time = None
    st.session_state.session_id = None

def send_to_n8n(endpoint, data):
    """Envía datos al webhook de n8n"""
    try:
        response = requests.post(
            endpoint,
            json=data,
            timeout=5,
            headers={'Content-Type': 'application/json'}
        )
        return response.status_code == 200
    except Exception as e:
        st.warning(f"Error 008")
        return False

def get_session_info():
    """Obtiene información básica de la sesión"""
    now = datetime.now(TIMEZONE)
    
    return {
        "usuario": st.session_state.user,
        "session_id": st.session_state.session_id,
        "tiempo_sesion_minutos": get_session_duration()
    }

def get_session_duration():
    """Calcula la duración de la sesión en minutos"""
    if st.session_state.login_time:
        now = datetime.now(TIMEZONE)
        duration = (now - st.session_state.login_time).total_seconds() / 60
        return round(duration, 2)
    return 0

def generate_session_id():
    """Genera un ID único para la sesión"""
    from datetime import datetime
    import random
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{timestamp}_{random_part}"

@st.dialog("Login – Conciliación GMoney")
def login_dialog():
    st.markdown("### Inicio de Sesión")
    
    # Crear un formulario para permitir Enter
    with st.form("login_form"):
        user = st.text_input("Usuario", key="login_user")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            submitted = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
        
        with col2:
            st.caption(f"⏱️ Sesión: {SESSION_TIMEOUT_MINUTES} min")
        
        if submitted:
            now = datetime.now(TIMEZONE)
            
            if user in USERS and USERS[user]['password'] == password:
                # Configurar sesión
                st.session_state.authenticated = True
                st.session_state.user = user
                st.session_state.user_type = USERS[user]["tipo"]
                st.session_state.login_time = now
                st.session_state.session_id = generate_session_id()
                
                # Preparar datos para n8n
                login_data = {
                    "evento": "login",
                    "usuario": user,
                    "session_id": st.session_state.session_id,
                    "timestamp": now.isoformat(),
                    "fecha": now.strftime("%Y-%m-%d"),
                    "hora": now.strftime("%H:%M:%S"),
                    "dia_semana": now.strftime("%A"),
                    'tipo_usuario': st.session_state.user_type
                }
                
                # Enviar a n8n ANTES de recargar
                success = send_to_n8n(N8N_LOGIN_PRODUCTION, login_data)
                
                if success:
                    st.success("Acceso concedido")
                else:
                    st.success("Acceso concedido")
                    st.warning("Erro 008")
                
                # Pequeña pausa para que el usuario vea el mensaje
                import time
                time.sleep(1)
                st.rerun()
            else:
                # Registrar intento fallido en n8n
                failed_data = {
                    "evento": "login_failed",
                    "usuario_intento": user,
                    "timestamp": now.isoformat(),
                    "fecha": now.strftime("%Y-%m-%d"),
                    "hora": now.strftime("%H:%M:%S")
                }
                send_to_n8n(N8N_LOGIN_PRODUCTION, failed_data)
                
                st.error("❌ Usuario o contraseña incorrectos")

def logout():
    """Cierra la sesión del usuario"""
    st.session_state.clear()
    st.rerun()

def show_session_info():
    """Muestra información de conciliación y botón de cerrar sesión en el sidebar"""
    with st.sidebar:
        st.markdown("### 📋 Pasos para Conciliar")
        st.markdown("""
        1. **Subir archivo Metabase  ayer - ayer**  
           _(en calendario metabase)_
        
        2. **Subir TXT GMoney**
        
        3. **Click Conciliar**
        """)
        
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="primary"):
            logout()

# -----------------------
# VERIFICACIÓN DE SESIÓN
# -----------------------
# Bloquear si no está autenticado
if not st.session_state.authenticated:
    login_dialog()
    st.stop()

# Mostrar información de sesión en sidebar
# show_session_info()

# URLs de webhooks
N8N_CONCILIACION_TEST = 'https://infraestructura.app.n8n.cloud/webhook-test/conciliacion-gmoney-test'
N8N_CONCILIACION_PRODUCTON = 'https://operationskashio.app.n8n.cloud/webhook/conciliacion-gmoney'
N8N_PAYINS_ONLINE_V2 = 'https://infraestructura.app.n8n.cloud/webhook/pruebas-payin-online'

# Inicializar session_state
if 'resultado_conciliacion' not in st.session_state:
    st.session_state.resultado_conciliacion = None
if 'archivos_subidos' not in st.session_state:
    st.session_state.archivos_subidos = False
if 'conciliacion_hora' not in st.session_state:
    st.session_state.conciliacion_hora = None
if 'met_online_key' not in st.session_state:
    st.session_state.met_online_key = None
    st.session_state.df_met_online_cache = None
if 'panda_online_key' not in st.session_state:
    st.session_state.panda_online_key = None
    st.session_state.df_panda_cashin_cache = None

st.divider()
st.subheader('Tipo de Conciliacion')

#Seleccionamos el tipo de conciliacion que usaremos para validar operaciones
tipo_conciliacion = st.selectbox(
        'Selecciona el tipo de conciliacion',
            [
                "Conciliacion PayOuts - Diaria",
                "Conciliacion PayIns - Online",
                "Conciliacion PayIns - Diaria"
            ]
    )

if tipo_conciliacion == "Conciliacion PayOuts - Diaria":
        st.title(f"📄 {tipo_conciliacion} - GMoney")
        conciliacion_code = "conciliacion_diaria"

        # ========================
        # SUBIDA DE ARCHIVOS
        # ========================
        st.header("Subir archivos")

        col1, col2 = st.columns(2)


        with col1:
            st.subheader("Metabase")
            archivo_metabase = st.file_uploader(
                'Archivo operaciones día anterior', 
                type=['xlsx'], 
                accept_multiple_files=True,
                key='uploader_metabase'
            )

        with col2:
            st.subheader("GMoney")
            archivo_gmoney = st.file_uploader(
                "Archivo txt GMoney", 
                type=["txt"], 
                key='uploader_gmoney'
            )

        # ========================
        # BOTÓN DE CONCILIACIÓN
        # ========================
        st.divider()

        df_metabase = None
        archivo_metabase_consolidado = None

        if archivo_metabase:
            dfs = []

            for archivo in archivo_metabase:
                df_temp = pd.read_excel(archivo, dtype={'numero_operacion': str})
                dfs.append(df_temp)
            
            df_metabase = pd.concat(dfs, ignore_index=True)

            buffer = BytesIO()
            df_metabase.to_excel(buffer, index=False)
            buffer.seek(0)

            archivo_metabase_consolidado = buffer

        # Verificar que ambos archivos estén cargados
        archivos_listos = archivo_metabase_consolidado is not None and archivo_gmoney is not None

        if st.button(
            "Conciliar",
            disabled=not archivos_listos,
            type="primary",
            use_container_width=True
        ):
            files = {
                "metabase": (
                    "metabase_consolidado.xlsx",
                    archivo_metabase_consolidado.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                "gmoney_txt": (
                    archivo_gmoney.name,
                    archivo_gmoney.getvalue(),
                    "text/plain"
                )
            }

            with st.spinner("Procesando conciliación..."):
                try:
                    session_metadata = {
                        'session_id':st.session_state.session_id,
                        'tipo_conciliacion': conciliacion_code,
                        'conciliacion':'payout_diaria'
                    }
                    response = requests.post(
                        N8N_CONCILIACION_PRODUCTON,
                        files=files,
                        data=session_metadata,
                        timeout=180
                    )

                    response.raise_for_status()

                    # ✅ El webhook ya devuelve JSON válido
                    data = response.json()

                except requests.exceptions.Timeout:
                    st.error("La solicitud tardó demasiado. Intenta nuevamente.")
                    st.stop()

                except requests.exceptions.RequestException as e:
                    st.error("Error al conectar con n8n")
                    st.exception(e)
                    st.stop()

                except ValueError:
                    st.error("El webhook no devolvió un JSON válido")
                    st.write(response.text)
                    st.stop()

                except Exception as e:
                    st.error("Error inesperado")
                    st.exception(e)
                    st.stop()

            st.session_state.resultado_conciliacion = data
            st.session_state.archivos_subidos = True

        # ========================
        # MOSTRAR RESULTADOS
        # ========================
        if st.session_state.resultado_conciliacion:

            resultado = st.session_state.resultado_conciliacion[0]
            importes = resultado.get("importes", [])
            detalle = resultado.get("detalle", [])

            # ========================
            # CONCILIACIÓN POR IMPORTE / DÍA
            # ========================
            st.divider()
            st.subheader("Conciliación por importes por día")
            st.write(
                "Resultado de la conciliación de los montos totales agregados por día, "
                "comparando Metabase vs GMoney"
            )

            if importes:
                df_importes = pd.DataFrame(importes)
                st.dataframe(df_importes, use_container_width=True)
            else:
                st.success("No se encontraron diferencias por importes.")

            # ========================
            # CONCILIACIÓN POR DETALLE
            # ========================
            st.divider()
            st.subheader("Conciliación por detalle de operaciones")
            st.write(
                "Resultado de la conciliación a nivel de operación individual, "
                "comparando los montos registrados entre Metabase y GMoney."
            )

            if detalle:
                df_detalle = pd.DataFrame(detalle)

                hay_diferencias = (
                    df_detalle['diferencia']
                    .notna()
                    .any()
                    and (df_detalle['diferencia'] != 0).any()
                )

                if hay_diferencias:
                    st.dataframe(df_detalle, use_container_width=True)
                    st.warning(f"Se identificaron {len(df_detalle)} diferencias.")
                else:
                    st.success("No se encontraron diferencias a nivel de detalle.")

            else:
                st.success("No se encontraron diferencias a nivel de detalle.")

elif tipo_conciliacion == 'Conciliacion PayIns - Online':

        st.title(f"📄 {tipo_conciliacion} - GMoney (v2)")
        conciliacion_code = "payins_online"

        # ========================
        # SUBIDA DE ARCHIVOS
        # ========================
        st.header("Subir archivos")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Metabase")
            archivo_metabase_online = st.file_uploader(
                'Archivo operaciones día anterior',
                type=['xlsx', 'json', 'csv'],
                accept_multiple_files=True,
                key='uploader_metabase_online'
            )

        with col2:
            st.subheader("GMoney")
            panda_empresas = st.file_uploader(
                "Archivo Panda Empresas",
                type=["csv"],
                key='uploader_gmoney_online'
            )

        # ========================
        # CARGA Y CACHÉ METABASE
        # ========================
        df_metabase_online = None
        if archivo_metabase_online:
            met_key = [(f.name, f.size) for f in archivo_metabase_online]
            if st.session_state.met_online_key != met_key:
                dfs = []
                for archivo in archivo_metabase_online:
                    if archivo.name.endswith('.json'):
                        t = pd.read_json(archivo, dtype={'PPY_external_id': str})
                    elif archivo.name.endswith('.csv'):
                        t = pd.read_csv(archivo, dtype={'PPY_external_id': str})
                    else:
                        t = pd.read_excel(archivo, dtype={'PPY_external_id': str})
                    dfs.append(t)
                df_metabase_online = pd.concat(dfs, ignore_index=True)
                st.session_state.met_online_key = met_key
                st.session_state.df_met_online_cache = df_metabase_online
            else:
                df_metabase_online = st.session_state.df_met_online_cache

        # ========================
        # CARGA Y CACHÉ PANDA EMPRESAS
        # ========================
        if panda_empresas is not None:
            panda_key = (panda_empresas.name, panda_empresas.size)
            if st.session_state.panda_online_key != panda_key:
                df_panda_cashin = pd.read_csv(BytesIO(panda_empresas.getvalue()), sep=";")
                df_panda_cashin = df_panda_cashin[df_panda_cashin['operation'] == 'CASHIN']
                # fix limpiar formato excel-style ="..."
                df_panda_cashin['instruction_id'] = (
                    df_panda_cashin['instruction_id']
                    .astype(str)
                    .str.replace('="', '', regex=False)
                    .str.replace('"', '', regex=False)
                    .str.strip()
                )
                st.session_state.panda_online_key = panda_key
                st.session_state.df_panda_cashin_cache = df_panda_cashin

        # ========================
        # VISTA PREVIA
        # ========================
        if df_metabase_online is not None or panda_empresas is not None:
            prev_col1, prev_col2 = st.columns(2)
            with prev_col1:
                if df_metabase_online is not None:
                    st.caption(f"Vista previa Metabase — {len(df_metabase_online)} filas totales")
                    muestra = "desconocido"
                    try:
                        muestra = str(df_metabase_online['PC_create_date_GMT_Peru'].dropna().iloc[0])
                        pd.to_datetime(
                            df_metabase_online['PC_create_date_GMT_Peru'].astype(str).str.replace(',', '', regex=False),
                            dayfirst=True, errors='coerce'
                        )
                    except Exception:
                        st.error(f"Formato de fecha no reconocido en `PC_create_date_GMT_Peru`: `{muestra}`")
            with prev_col2:
                if st.session_state.df_panda_cashin_cache is not None:
                    st.caption(f"Vista previa Panda Empresas — {len(st.session_state.df_panda_cashin_cache)} filas (CASHIN)")

        # ========================
        # BOTÓN CONCILIAR
        # ========================
        st.divider()
        archivos_listos = (df_metabase_online is not None) and (panda_empresas is not None)

        if st.button("Conciliar", disabled=not archivos_listos, type="primary", use_container_width=True):

            # 🔐 Garantizar session_id
            if not st.session_state.get('session_id'):
                st.session_state.session_id = generate_session_id()
            session_id = st.session_state.session_id

            # DEBUG temporal: verificar que esto SÍ tiene valor
            #st.write(f"🔍 session_id: `{session_id}`")

            hora_filtro = datetime.now(TIMEZONE).hour - 1

            # ----------- METABASE -----------
            dt_met = pd.to_datetime(
                df_metabase_online['PC_create_date_GMT_Peru'].astype(str).str.replace(',', '', regex=False),
                dayfirst=True, errors='coerce'
            )
            df_met_filtrado = df_metabase_online[dt_met.dt.hour == hora_filtro].copy()
            df_met_filtrado['_fecha_iso'] = dt_met[dt_met.dt.hour == hora_filtro].dt.strftime('%Y-%m-%d %H:%M:%S')

            meta_rows = [{
                "session_id": session_id,
                "source": "metabase",
                "join_key": str(r["PPY_external_id"]).strip(),
                "amount": float(r["amount"]) if pd.notna(r.get("amount")) else None,
                "currency": r.get("currency_code"),
                "fecha": r.get("_fecha_iso"),
                "comercio_nombre": r.get("Comercio_Nombre"),
                "deudor_nombre": r.get("Deudor_Nombre"),
                "deudor_documento": r.get("Deudor_Documento"),
                "deuda_public_id": r.get("Deuda_public_id"),
                "deuda_estado": r.get("Deuda_Estado"),
            } for r in df_met_filtrado.where(df_met_filtrado.notna(), None).to_dict("records")]

            # ----------- GMONEY -----------
            df_panda_envio = st.session_state.df_panda_cashin_cache.copy()
            df_panda_envio = df_panda_envio[df_panda_envio['movement_hour'].str[:2].astype(int) == hora_filtro]
            df_panda_envio['_fecha_iso'] = pd.to_datetime(
                df_panda_envio['movement_day'] + ' ' + df_panda_envio['movement_hour'],
                dayfirst=True, errors='coerce'
            ).dt.strftime('%Y-%m-%d %H:%M:%S')

            gm_rows = [{
                "session_id": session_id,
                "source": "gmoney",
                "join_key": str(r["instruction_id"]).strip().strip('"'),
                "amount": float(r["amount"]) if pd.notna(r.get("amount")) else None,
                "currency": r.get("currency"),
                "fecha": r.get("_fecha_iso"),
                "origin_name": r.get("origin_name"),
                "origin_document": str(r["origin_document"]) if pd.notna(r.get("origin_document")) else None,
                "target_name": r.get("target_name"),
                "fee": float(r["fee"]) if pd.notna(r.get("fee")) else None,
                "entity": r.get("entity"),
                "operation": r.get("operation"),
            } for r in df_panda_envio.where(df_panda_envio.notna(), None).to_dict("records")]

            # Normalizar a las mismas keys
            ALL_KEYS = [
                "session_id", "source", "join_key", "amount", "currency", "fecha",
                "comercio_nombre", "deudor_nombre", "deudor_documento", "deuda_public_id", "deuda_estado",
                "origin_name", "origin_document", "target_name", "fee", "entity", "operation",
            ]
            def _normalize(r):
                return {k: r.get(k) for k in ALL_KEYS}
            meta_rows = [_normalize(r) for r in meta_rows]
            gm_rows   = [_normalize(r) for r in gm_rows]

            payload = {
                "session_id": session_id,
                "tipo_conciliacion": "payins_online",
                "hora_filtro": hora_filtro,
                "fecha_inicio_iso": datetime.now(TIMEZONE).isoformat(),
                "rows": meta_rows + gm_rows,
            }

            with st.spinner("Procesando conciliación..."):
                try:
                    response = requests.post(
                        N8N_PAYINS_ONLINE_V2,
                        json=payload,
                        timeout=180,
                        headers={'Content-Type': 'application/json'}
                    )
                    response.raise_for_status()
                    if not response.text.strip():
                        st.warning("n8n respondió vacío.")
                        st.stop()
                    data = response.json()
                except requests.exceptions.Timeout:
                    st.error("La solicitud tardó demasiado."); st.stop()
                except requests.exceptions.RequestException as e:
                    st.error("Error al conectar con n8n"); st.exception(e); st.stop()
                except ValueError:
                    st.error("El webhook no devolvió un JSON válido"); st.write(response.text); st.stop()
                except Exception as e:
                    st.error("Error inesperado"); st.exception(e); st.stop()

            st.session_state.resultado_conciliacion = data
            st.session_state.archivos_subidos = True
            # ----------- CONCILIACIÓN LOCAL POR HORA -----------
            try:
                grp_met = (
                    df_metabase_online
                    .assign(_fecha=dt_met.dt.date, _hora=dt_met.dt.hour)
                    .groupby(['_fecha', '_hora'])['amount'].sum()
                    .reset_index()
                    .rename(columns={'_fecha': 'fecha_conciliacion', '_hora': 'hora', 'amount': 'total_amount_metabase'})
                )

                df_panda_hora = st.session_state.df_panda_cashin_cache.copy()
                dt_panda = pd.to_datetime(
                    df_panda_hora['movement_day'] + ' ' + df_panda_hora['movement_hour'],
                    dayfirst=True, errors='coerce'
                )
                grp_panda = (
                    df_panda_hora
                    .assign(_fecha=dt_panda.dt.date, _hora=dt_panda.dt.hour)
                    .groupby(['_fecha', '_hora'])['amount'].sum()
                    .reset_index()
                    .rename(columns={'_fecha': 'fecha_conciliacion', '_hora': 'hora', 'amount': 'total_amount_gmoney'})
                )

                df_conc_hora = (
                    grp_met.merge(grp_panda, on=['fecha_conciliacion', 'hora'], how='outer')
                    .fillna(0)
                    .sort_values(['fecha_conciliacion', 'hora'])
                    .reset_index(drop=True)
                )
                df_conc_hora['diferencia'] = df_conc_hora['total_amount_metabase'] - df_conc_hora['total_amount_gmoney']
                df_conc_hora['estado'] = df_conc_hora['diferencia'].apply(lambda x: 'Conciliado' if x == 0 else 'Diferencias')
                hora_actual = datetime.now(TIMEZONE).hour
                df_conc_hora = df_conc_hora[df_conc_hora['hora'] < hora_actual].reset_index(drop=True)
                st.session_state.conciliacion_hora = df_conc_hora
            except Exception as e:
                st.error(f"Error en conciliación local: {e}")

        # ========================
        # RESULTADOS
        # ========================
        if st.session_state.conciliacion_hora is not None:
            st.divider()
            st.subheader("Conciliación por importes por hora")
            st.write("Totales agregados por hora, Metabase vs GMoney (cálculo local).")
            st.dataframe(st.session_state.conciliacion_hora, use_container_width=True)

        if st.session_state.resultado_conciliacion:
            raw = st.session_state.resultado_conciliacion
            resultado = raw[0] if isinstance(raw, list) else raw

            resumen = resultado.get("resumen", {})
            detalle = resultado.get("detalle", [])

            st.divider()
            st.subheader("Conciliación por detalle de operaciones")
            st.write(
                "Resultado de la conciliación a nivel de operación individual, "
                "comparando los montos registrados entre Metabase y GMoney."
            )

            if detalle:
                df_raw = pd.DataFrame(detalle)

                df_view = pd.DataFrame({
                    "id":             df_raw["ppy_external_id"],
                    "Hora":           df_raw["hora"],
                    "Monto_metabase": df_raw["amount_metabase"],
                    "Monto_gmoney":   df_raw["monto_gmoney"],
                    "Resultado":      df_raw["resultado"],
                    "Comercio":       df_raw["gmoney_target_name"].fillna(df_raw.get("comercio_nombre")),
                    "Moneda":         df_raw["moneda_metabase"].fillna(df_raw["gmoney_currency"]),
                    "Banco":          df_raw["gmoney_entity"],
                    "Diferencia":     df_raw["diferencia"],
                    "Nombre GMoney":  df_raw["gmoney_origin_name"],
                    "DNI GMoney":     df_raw["gmoney_origin_document"],
                })

                st.dataframe(df_view, use_container_width=True)
                st.warning(f"Se identificaron {len(df_view)} diferencias.")
            else:
                st.success("No se encontraron diferencias a nivel de detalle.")

elif tipo_conciliacion == "Conciliacion PayIns - Diaria":
        st.title(f"📄 {tipo_conciliacion} - GMoney") 
        conciliacion_code = "conciliacion_diaria"

        # ========================
        # SUBIDA DE ARCHIVOS
        # ========================
        st.header("Subir archivos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Metabase")
            archivo_metabase = st.file_uploader(
                'Archivo operaciones día anterior', 
                type=['xlsx'], 
                accept_multiple_files=True,
                key='uploader_metabase'
            )

        with col2:
            st.subheader("GMoney")
            archivo_gmoney = st.file_uploader(
                "Archivo txt GMoney", 
                type=["txt"], 
                key='uploader_gmoney'
            )

        # ========================
        # BOTÓN DE CONCILIACIÓN
        # ========================
        st.divider()

        df_metabase = None
        archivo_metabase_consolidado = None

        if archivo_metabase:
            dfs = []

            for archivo in archivo_metabase:
                df_temp = pd.read_excel(archivo, dtype={'PPY_external_id': str})
                dfs.append(df_temp)
            
            df_metabase = pd.concat(dfs, ignore_index=True)

            buffer = BytesIO()
            df_metabase.to_excel(buffer, index=False)
            buffer.seek(0)

            archivo_metabase_consolidado = buffer

        # Verificar que ambos archivos estén cargados
        archivos_listos = archivo_metabase_consolidado is not None and archivo_gmoney is not None

        if st.button(
            "Conciliar",
            disabled=not archivos_listos,
            type="primary",
            use_container_width=True
        ):
            files = {
                "metabase": (
                    "metabase_consolidado.xlsx",
                    archivo_metabase_consolidado.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                "gmoney_txt": (
                    archivo_gmoney.name,
                    archivo_gmoney.getvalue(),
                    "text/plain"
                )
            }

            with st.spinner("Procesando conciliación..."):
                try:
                    session_metadata = {
                        'session_id':st.session_state.session_id,
                        'tipo_conciliacion': conciliacion_code,
                        'conciliacion': 'payin_diaria'
                    }
                    response = requests.post(
                        N8N_CONCILIACION_PRODUCTON,
                        files=files,
                        data=session_metadata,
                        timeout=180
                    )

                    response.raise_for_status()

                    # ✅ El webhook ya devuelve JSON válido
                    data = response.json()

                    #espera controlada
                    #time.sleep(10)

                except requests.exceptions.Timeout:
                    st.error("La solicitud tardó demasiado. Intenta nuevamente.")
                    st.stop()

                except requests.exceptions.RequestException as e:
                    st.error("Error al conectar con n8n")
                    st.exception(e)
                    st.stop()

                except ValueError:
                    st.error("El webhook no devolvió un JSON válido")
                    st.write(response.text)
                    st.stop()

                except Exception as e:
                    st.error("Error inesperado")
                    st.exception(e)
                    st.stop()

            st.session_state.resultado_conciliacion = data
            st.session_state.archivos_subidos = True

        # ========================
        # MOSTRAR RESULTADOS
        # ========================
        if st.session_state.resultado_conciliacion:

            resultado = st.session_state.resultado_conciliacion[0]
            importes = resultado.get("importes", [])
            detalle = resultado.get("detalle", [])

            # ========================
            # CONCILIACIÓN POR IMPORTE / DÍA
            # ========================
            st.divider()
            st.subheader("Conciliación por importes por día")
            st.write(
                "Resultado de la conciliación de los montos totales agregados por día, "
                "comparando Metabase vs GMoney"
            )

            if importes:
                df_importes = pd.DataFrame(importes)
                st.dataframe(df_importes, use_container_width=True)
            else:
                st.success("No se encontraron diferencias por importes.")

            # ========================
            # CONCILIACIÓN POR DETALLE
            # ========================
            st.divider()
            st.subheader("Conciliación por detalle de operaciones")
            st.write(
                "Resultado de la conciliación a nivel de operación individual, "
                "comparando los montos registrados entre Metabase y GMoney."
            )

            if detalle:
                df_detalle = pd.DataFrame(detalle)
                
                dif_detalle = (df_detalle['resultado_conciliacion'] != 'OK').any()

                if dif_detalle:
                    st.dataframe(df_detalle, use_container_width=True)
                    st.warning(f"Se identificaron {len(df_detalle)} diferencias.")
                else:
                    st.success("No se encontraron diferencias a nivel de detalle.")

            else:
                st.success("No se encontraron diferencias a nivel de detalle.")