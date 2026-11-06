"""Escalamiento manual: botón + modal para avisar al responsable con contexto del colaborador."""
import streamlit as st

from core.errores import ERRORES, RESPONSABLE
from integraciones.notificaciones import escalamiento_enviado, escalar_una_vez


def boton_escalar(codigo, detalle=None, ciclo=None, operador=None, key="escalar"):
    """Muestra «Escalar a …» o, si ya se envió, la confirmación."""
    if escalamiento_enviado(codigo, ciclo):
        st.success(f"📨 Escalado a **{RESPONSABLE}**. Te contactará para resolverlo.")
        return
    if st.button(f"📨 Escalar a {RESPONSABLE}", key=key, use_container_width=True):
        confirmar_escalamiento(codigo, detalle, ciclo, operador)

@st.dialog("📨 Escalar fallo del sistema", width="medium")
def confirmar_escalamiento(codigo, detalle, ciclo, operador):
    st.caption(f"Se enviará un aviso a {RESPONSABLE} por Teams.")

    with st.container(border=True):
        st.markdown(f"**{ERRORES[codigo]['titulo']}**")
        if ciclo:
            st.markdown(f"**Banco:** {ciclo.get('banco_codigo', '—')} · "
                        f"**Bloque:** {ciclo['ventana_inicio'][11:16]} → {ciclo['ventana_fin'][11:16]}")
        if operador:
            st.markdown(f"**Reporta:** {operador}")
        if detalle:
            st.code(str(detalle)[:300], language=None)

    comentario = st.text_area(
        "¿Qué estabas haciendo? (opcional)",
        placeholder="Ej.: reintenté dos veces el envío del EECC y sigue fallando",
        key=f"comentario_escalar_{codigo}",
    ).strip()

    col_cancelar, col_enviar = st.columns(2)
    if col_cancelar.button("Cancelar", use_container_width=True):
        st.rerun()
    if col_enviar.button("Enviar", type="primary", use_container_width=True):
        with st.spinner("Enviando aviso..."):
            ok = escalar_una_vez(codigo, detalle, ciclo, operador, comentario)
        if ok:
            st.rerun()
        else:
            st.error(f"No se pudo enviar el aviso. Escríbele directamente a **{RESPONSABLE}** por Teams.")
