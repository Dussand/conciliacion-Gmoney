import streamlit as st

from core.sesion import logout


def render_topbar():
    col_logo, col_user, col_logout = st.columns([7, 2, 1])
    with col_logo:
        st.markdown("🔴 &nbsp; **Motor de Conciliación · Contingencia**")
    with col_user:
        st.markdown(f"👤 &nbsp; `{st.session_state.user}`")
    with col_logout:
        if st.button("Cerrar sesión", key="btn_logout"):
            logout()

    st.divider()
