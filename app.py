"""Punto de entrada modular de la app de contingencia (reemplazo de conciG.py)."""
import streamlit as st

# set_page_config debe ser el primer comando de Streamlit
st.set_page_config(
    page_title="Conciliación G-Money",
    page_icon="💰",
    layout="wide"
)

from core.sesion import init_post_login_state, init_session_state, login_dialog
from core.utils import cargar_css
from ui.menu import render_menu
from ui.modulo_conciliacion import render_modulo_conciliacion
from ui.modulo_eecc import render_modulo_eecc
from ui.topbar import render_topbar

cargar_css("style.css")

init_session_state()

# -----------------------
# VERIFICACIÓN DE SESIÓN
# -----------------------
if not st.session_state.authenticated:
    login_dialog()
    st.stop()
st.session_state.authenticated = True
st.session_state.user = st.session_state.get("user") or "dev"

init_post_login_state()

render_topbar()

# -----------------------
# ROUTING DE MÓDULOS
# -----------------------
if st.session_state.modulo == "eecc":
    render_modulo_eecc()
elif st.session_state.modulo == "conciliacion":
    render_modulo_conciliacion()
else:
    render_menu()
