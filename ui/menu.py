import streamlit as st


def render_menu():
    # -----------------------
    # PANTALLA DE SELECCIÓN
    # -----------------------
    st.markdown("<h2 style='text-align:center'>¿Qué necesitas hacer?</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray'>Selecciona el módulo que necesitas usar</p>", unsafe_allow_html=True)
    st.write("")

    _, col_centro, _ = st.columns([1, 2, 1])

    with col_centro:
        with st.container(border=True):
            st.markdown("### ⬆️ Subir EECC")
            st.markdown("El RPA no pudo extraer el archivo del banco. Súbelo manualmente para reanudar la conciliación.")
            st.write("")
            if st.button("Ir a bandeja →", key="btn_eecc", type="primary", use_container_width=True):
                st.session_state.modulo = "eecc"
                st.rerun()

        st.write("")

        with st.container(border=True):
            st.markdown("### 📄 Ejecutar Conciliación")
            st.markdown("Concilia manualmente archivos cuando el sistema automatizado no está disponible.")
            st.write("")
            if st.button("Ir a conciliación →", key="btn_conciliacion", use_container_width=True):
                st.session_state.modulo = "conciliacion"
                st.rerun()
