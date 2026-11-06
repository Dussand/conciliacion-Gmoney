import time
from datetime import datetime

import streamlit as st

import config
from core.utils import TIMEZONE, generate_session_id
from integraciones.n8n import send_to_n8n


def init_session_state():
    """Inicializa session_state antes del login."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.login_time = None
        st.session_state.session_id = None
        st.session_state.modulo = None
        st.session_state.ciclo_seleccionado = None

def init_post_login_state():
    """Inicializa las claves de session_state que usan los módulos."""
    if 'resultado_conciliacion' not in st.session_state:
        st.session_state.resultado_conciliacion = None
    if 'archivos_subidos' not in st.session_state:
        st.session_state.archivos_subidos = False
    if 'modulo' not in st.session_state:
        st.session_state.modulo = None
    if 'ciclo_seleccionado' not in st.session_state:
        st.session_state.ciclo_seleccionado = None
    if 'archivo_eecc' not in st.session_state:
        st.session_state.archivo_eecc = None
    if 'operador_eecc' not in st.session_state:
        st.session_state.operador_eecc = None
    if 'archivo_validado' not in st.session_state:
        st.session_state.archivo_validado = False
    if 'df_mapeado' not in st.session_state:
        st.session_state.df_mapeado = None
    if 'carga_confirmada' not in st.session_state:
        st.session_state.carga_confirmada = False

def get_session_info():
    """Obtiene información básica de la sesión"""
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

@st.dialog("Login - Contingencia Motor Multibanco")
def login_dialog():
    st.markdown("### Inicio de Sesión")

    with st.form("login_form"):
        user = st.text_input("Usuario", key="login_user")
        password = st.text_input("Contraseña", type="password", key="login_pass")

        col1, col2 = st.columns([1, 1])

        with col1:
            submitted = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

        with col2:
            st.caption(f"⏱️ Sesión: {config.SESSION_TIMEOUT_MINUTES} min")

        if submitted:
            now = datetime.now(TIMEZONE)

            if user in config.USERS and config.USERS[user]['password'] == password:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.session_state.user_type = config.USERS[user]["role"]
                st.session_state.login_time = now
                st.session_state.session_id = generate_session_id()

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

                success = send_to_n8n(config.N8N_LOGIN, login_data)

                if success:
                    st.success("Acceso concedido")
                else:
                    st.success("Acceso concedido")
                    st.warning("Erro 008")

                time.sleep(1)
                st.rerun()
            else:
                failed_data = {
                    "evento": "login_failed",
                    "usuario_intento": user,
                    "timestamp": now.isoformat(),
                    "fecha": now.strftime("%Y-%m-%d"),
                    "hora": now.strftime("%H:%M:%S")
                }
                send_to_n8n(config.N8N_LOGIN, failed_data)

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
