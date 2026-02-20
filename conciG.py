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
    "operador_gmoney": {
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
show_session_info()

# URLs de webhooks
N8N_CONCILIACION_TEST = 'https://operationskashio.app.n8n.cloud/webhook-test/conciliacion-gmoney'
N8N_CONCILIACION_PRODUCTON = 'https://operationskashio.app.n8n.cloud/webhook/conciliacion-gmoney'

# Inicializar session_state
if 'resultado_conciliacion' not in st.session_state:
    st.session_state.resultado_conciliacion = None
if 'archivos_subidos' not in st.session_state:
    st.session_state.archivos_subidos = False

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
                df_temp = pd.read_excel(archivo)
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

        st.title(f"📄 {tipo_conciliacion} - GMoney") 
        conciliacion_code = "conciliacion_online"

        # ========================
        # SUBIDA DE ARCHIVOS
        # ========================
        st.header("Subir archivos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Metabase")
            archivo_metabase_online = st.file_uploader(
                'Archivo operaciones día anterior', 
                type=['xlsx'], 
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
        # BOTÓN DE CONCILIACIÓN
        # ========================
        st.divider()

        df_metabase_online = None
        archivo_metabase_consolidado_online = None

        if archivo_metabase_online:
            dfs = []

            for archivo in archivo_metabase_online:
                temp_online = pd.read_excel(archivo)
                dfs.append(temp_online)
            
            df_metabase_online = pd.concat(dfs, ignore_index=True)

            buffer = BytesIO()
            df_metabase_online.to_excel(buffer, index=False)
            buffer.seek(0)

            archivo_metabase_consolidado_online = buffer

        # Verificar que ambos archivos estén cargados
        archivos_listos_online = archivo_metabase_consolidado_online is not None and panda_empresas is not None

        if st.button(
            "Conciliar",
            disabled=not archivos_listos_online,
            type="primary",
            use_container_width=True
        ):
            files = {
                "metabase": (
                    "metabase_conciliacion_online.xlsx",
                    archivo_metabase_consolidado_online.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                "panda_empresas": (
                    panda_empresas.name,
                    panda_empresas.getvalue(),
                    "text/csv"
                )
            }

            with st.spinner("Procesando conciliación..."):
                try:
                    session_metadata = {
                        'session_id':st.session_state.session_id,
                        'tipo_conciliacion': conciliacion_code,
                        'conciliacion': 'payin_online'
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
                df_temp = pd.read_excel(archivo)
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