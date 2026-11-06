import streamlit as st

from ui.conciliacion_diaria import render_conciliacion_diaria


def render_modulo_conciliacion():
    if st.button("← Volver", key="volver_conciliacion"):
        st.session_state.modulo = None
        st.rerun()

    # Seleccionamos el tipo de conciliacion que usaremos para validar operaciones
    tipo_conciliacion = st.selectbox(
        'Selecciona el tipo de conciliacion',
        [
            "Conciliacion PayOuts - Diaria",
            "Conciliacion PayIns - Diaria"
        ]
    )

    if tipo_conciliacion == "Conciliacion PayOuts - Diaria":
        render_conciliacion_diaria(tipo_conciliacion, "payout")
    elif tipo_conciliacion == "Conciliacion PayIns - Diaria":
        render_conciliacion_diaria(tipo_conciliacion, "payin")
