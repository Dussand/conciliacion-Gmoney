import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from io import BytesIO
import time
import re


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

def extraer_fecha_de_codigo(codigo_unico):
    """Extrae la fecha_inicio del timestamp dentro del codigo_unico.
    Formato esperado: 20260320120007... → 2026-03-20 12:00:07
    """
    try:
        timestamp_str = codigo_unico[:14]  # YYYYMMDDHHmmss
        fecha = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        return fecha.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

def extraer_origen_de_codigo(codigo_unico):
    """Detecta el origen a partir del texto en el codigo_unico."""
    codigo_upper = codigo_unico.upper()
    if "METABASE" in codigo_upper:
        return "METABASE"
    elif "GMONEY" in codigo_upper:
        return "GMONEY"
    return "DESCONOCIDO"

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
N8N_CONCILIACION_TEST = 'https://operationskashio.app.n8n.cloud/webhook-test/pruebas-streamlit'
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
                        N8N_CONCILIACION_TEST,
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

# ============================================================
# PAYINS ONLINE — ENVÍO SECUENCIAL CON SEMÁFORO
# ============================================================
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
                'Archivo JSON Metabase', 
                type=['json'], 
                key='uploader_metabase_online'
            )

        with col2:
            st.subheader("GMoney")
            panda_empresas = st.file_uploader(
                "Archivo CSV Panda Empresas", 
                type=["csv"], 
                key='uploader_gmoney_online'
            )

        # ========================
        # CÓDIGOS DE CONCILIACIÓN
        # ========================
        st.divider()
        st.header("Códigos de conciliación")
        st.caption("Ingresa los códigos únicos para cada origen. La fecha y el origen se extraen automáticamente del código.")

        col_cod1, col_cod2 = st.columns(2)

        with col_cod1:
            codigo_unico_metabase = st.text_input(
                "Código único — Metabase",
                placeholder="Ej: 20260320120007METABASE2616",
                key="cod_unico_metabase"
            )
            if codigo_unico_metabase:
                fecha_mb = extraer_fecha_de_codigo(codigo_unico_metabase)
                origen_mb = extraer_origen_de_codigo(codigo_unico_metabase)
                st.caption(f"📅 Fecha: `{fecha_mb}` · 🏷️ Origen: `{origen_mb}`")

        with col_cod2:
            codigo_unico_gmoney = st.text_input(
                "Código único — GMoney",
                placeholder="Ej: 20260320120007GMONEY8784",
                key="cod_unico_gmoney"
            )
            if codigo_unico_gmoney:
                fecha_gm = extraer_fecha_de_codigo(codigo_unico_gmoney)
                origen_gm = extraer_origen_de_codigo(codigo_unico_gmoney)
                st.caption(f"📅 Fecha: `{fecha_gm}` · 🏷️ Origen: `{origen_gm}`")

        codigo_conciliacion = st.text_input(
            "Código de conciliación",
            placeholder="Ej: 20260320120007PAYINONLINE",
            key="cod_conciliacion"
        )

        # ========================
        # BOTÓN DE CONCILIACIÓN — ENVÍO SECUENCIAL
        # ========================
        st.divider()

        # Validar que todo esté completo
        archivos_listos_online = (
            archivo_metabase_online is not None 
            and panda_empresas is not None
            and codigo_unico_metabase.strip() != ""
            and codigo_unico_gmoney.strip() != ""
            and codigo_conciliacion.strip() != ""
        )

        if st.button(
            "Conciliar",
            disabled=not archivos_listos_online,
            type="primary",
            use_container_width=True
        ):
            # Leer contenido de los archivos como texto
            contenido_metabase = archivo_metabase_online.getvalue().decode("utf-8")
            contenido_gmoney = panda_empresas.getvalue().decode("utf-8")

            # ---------- PAYLOAD METABASE ----------
            payload_metabase = {
                "codigo_unico": codigo_unico_metabase.strip(),
                "fecha_inicio": extraer_fecha_de_codigo(codigo_unico_metabase),
                "origen": extraer_origen_de_codigo(codigo_unico_metabase),
                "estado": "Fallido",
                "tipo_conciliacion": "payin_online",
                "contenido": contenido_metabase,
                "codigo_conciliacion": codigo_conciliacion.strip()
            }

            # ---------- PAYLOAD GMONEY ----------
            payload_gmoney = {
                "codigo_unico": codigo_unico_gmoney.strip(),
                "fecha_inicio": extraer_fecha_de_codigo(codigo_unico_gmoney),
                "origen": extraer_origen_de_codigo(codigo_unico_gmoney),
                "estado": "Fallido",
                "tipo_conciliacion": "payin_online",
                "contenido": contenido_gmoney,
                "codigo_conciliacion": codigo_conciliacion.strip()
            }

            # ---------- ENVÍO SECUENCIAL ----------
            progress_container = st.container()

            with progress_container:
                # PASO 1: Enviar Metabase
                step1 = st.empty()
                step1.info("📤 Enviando archivo Metabase...")

                try:
                    resp_metabase = requests.post(
                        N8N_CONCILIACION_TEST,
                        json=payload_metabase,
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    resp_metabase.raise_for_status()
                    step1.success("✅ Metabase enviado correctamente")
                except Exception as e:
                    step1.error(f"❌ Error al enviar Metabase: {e}")
                    st.stop()

                # PASO 2: Delay de 5 segundos con countdown
                countdown_placeholder = st.empty()
                for i in range(5, 0, -1):
                    countdown_placeholder.warning(f"⏳ Esperando {i} segundos antes de enviar GMoney...")
                    time.sleep(1)
                countdown_placeholder.empty()

                # PASO 3: Enviar GMoney
                step3 = st.empty()
                step3.info("📤 Enviando archivo GMoney...")

                try:
                    resp_gmoney = requests.post(
                        N8N_CONCILIACION_TEST,
                        json=payload_gmoney,
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    resp_gmoney.raise_for_status()
                    step3.success("✅ GMoney enviado correctamente")
                except Exception as e:
                    step3.error(f"❌ Error al enviar GMoney: {e}")
                    st.stop()

                # PASO 4: Confirmación final
                st.divider()
                st.success("🎯 Ambos archivos enviados. El semáforo de n8n se encarga del resto.")
                st.caption("La conciliación se procesará automáticamente cuando n8n detecte ambos registros.")

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
                        N8N_CONCILIACION_TEST,
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
                
                dif_detalle = (df_detalle['resultado_conciliacion'] != 'OK').any()

                if dif_detalle:
                    st.dataframe(df_detalle, use_container_width=True)
                    st.warning(f"Se identificaron {len(df_detalle)} diferencias.")
                else:
                    st.success("No se encontraron diferencias a nivel de detalle.")

            else:
                st.success("No se encontraron diferencias a nivel de detalle.")