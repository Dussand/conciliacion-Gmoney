"""Escalamiento automático de fallos del sistema al responsable vía n8n (Teams / correo)."""
from datetime import datetime

import requests
import streamlit as st

import config
from core.errores import ERRORES, RESPONSABLE
from core.utils import TIMEZONE
from integraciones.n8n import generar_jwt

# Se lee de secrets.toml ([n8n_dev] / [n8n_prod] → webhook_escalamiento) sin tocar config.py.
_n8n_env = "n8n_dev" if config.IS_DEV else "n8n_prod"
WEBHOOK_ESCALAMIENTO: str = st.secrets.get(_n8n_env, {}).get("webhook_escalamiento", "")


def notificar_escalamiento(codigo, detalle=None, ciclo=None, operador=None, comentario=None):
    """Envía el aviso al responsable. Devuelve True si n8n lo recibió."""
    if not WEBHOOK_ESCALAMIENTO:
        return False
    ahora = datetime.now(TIMEZONE)
    payload = {
        "tipo":        "escalamiento_contingencia",
        "entorno":     config.ENTORNO,
        "codigo":      codigo,
        "titulo":      ERRORES[codigo]["titulo"],
        "detalle":     str(detalle)[:1000] if detalle else None,
        "comentario":  comentario or None,           # lo que escribió el colaborador en el modal
        "responsable": RESPONSABLE,
        "ciclo_id":    (ciclo or {}).get("ciclo_id"),
        "banco":       (ciclo or {}).get("banco_codigo"),
        "operador":    operador,
        "usuario":     st.session_state.get("user"),
        "fecha_hora":  ahora.strftime("%Y-%m-%d %H:%M:%S"),
    }
    headers = {}
    if config.N8N_JWT_SECRET:
        headers["Authorization"] = f"Bearer {generar_jwt(config.N8N_JWT_SECRET)}"
    try:
        resp = requests.post(WEBHOOK_ESCALAMIENTO, json=payload, timeout=10, headers=headers)
        return resp.status_code in (200, 201)
    except Exception:
        return False

def _clave(codigo, ciclo):
    return f"{codigo}|{(ciclo or {}).get('ciclo_id')}"

def escalamiento_enviado(codigo, ciclo=None):
    """True si ya se escaló con éxito este (código, ciclo) en la sesión."""
    return st.session_state.get("escalamientos_enviados", {}).get(_clave(codigo, ciclo)) is True

def escalar_una_vez(codigo, detalle=None, ciclo=None, operador=None, comentario=None):
    """Notifica solo una vez por (código, ciclo) en la sesión, para no repetir avisos en cada rerun.
    Si un envío falló, permite reintentarlo.
    """
    enviados = st.session_state.setdefault("escalamientos_enviados", {})
    clave = _clave(codigo, ciclo)
    if enviados.get(clave) is not True:
        enviados[clave] = notificar_escalamiento(codigo, detalle, ciclo, operador, comentario)
    return enviados[clave]
