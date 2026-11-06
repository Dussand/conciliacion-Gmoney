import time

import pandas as pd
import requests
import streamlit as st

import config


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
    except Exception:
        st.warning("Error 008")
        return False

def generar_jwt(secret, minutos_validez=5):
    """Firma un JWT HS256 para los webhooks de n8n con JWT Auth."""
    import base64, hashlib, hmac, json as _json

    def b64(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    ahora = int(time.time())
    header  = b64(_json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64(_json.dumps({"iat": ahora, "exp": ahora + minutos_validez * 60}, separators=(",", ":")).encode())
    firma   = b64(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{firma}"

def enviar_a_n8n(df_mapeado, ciclo, operador, fuera_de_lista=False):
    if not config.N8N_JWT_SECRET:
        return False, "falta jwt_secret en secrets.toml"
    # Mismo formato que envía el RPA: n8n solo ingesta los registros en eecc_unificado.
    def texto(v):
        return None if pd.isna(v) else str(v).strip()

    nombre_operador = texto(operador)
    registros = [{
        "banco_codigo":        texto(r["banco_codigo"]),
        "operacion_id":        texto(r["operacion_id"]),
        "pais":                texto(r["pais"]),
        "fecha_operacion":     texto(r["fecha_operacion"]),
        "monto":               f"{float(r['amount']):.2f}",
        "moneda":              texto(r["moneda"]),
        "psptin":              texto(r.get("psptin")),
        "estado_conciliacion": "PENDIENTE",
        "cuenta_origen":       texto(r["cuenta_origen"]),
        "origen_ingesta":      "MANUAL",
        "origin_document":     texto(r.get("origin_document")),
        "target_name":         texto(r.get("target_name")),
    } for _, r in df_mapeado.iterrows()]

    payload = {
        "ciclo_id":         ciclo["ciclo_id"],
        "banco":            ciclo["banco_codigo"],
        "status":           "success",
        "total_records":    len(registros),
        "operador":         nombre_operador,
        "operador_nombre":  nombre_operador,
        "operador_fuera_de_lista": fuera_de_lista,   # escrito a mano: no está en la tabla colaboradores
        "registros":        registros,
    }

    return _post_motor(payload)

def reportar_banco_no_disponible(ciclo, operador, fuera_de_lista, motivo, comentario):
    """Avisa a n8n que el EECC no se pudo obtener; n8n marca el ciclo NO_DISPONIBLE y registra la incidencia."""
    if not config.N8N_JWT_SECRET:
        return False, "falta jwt_secret en secrets.toml"
    payload = {
        "ciclo_id":                ciclo["ciclo_id"],
        "banco":                   ciclo["banco_codigo"],
        "cuenta_origen":           ciclo.get("cuenta_origen"),
        "status":                  "banco_no_disponible",
        "total_records":           0,
        "operador":                operador,
        "operador_nombre":         operador,
        "operador_fuera_de_lista": fuera_de_lista,
        "motivo":                  motivo,
        "comentario":              comentario or None,
        "registros":               [],
    }
    return _post_motor(payload)

def _post_motor(payload):
    try:
        resp = requests.post(
            config.N8N_MOTOR_CONCI,
            json=payload,
            timeout=30,
            headers={"Authorization": f"Bearer {generar_jwt(config.N8N_JWT_SECRET)}"},
        )
        return resp.status_code in (200, 201), resp.status_code
    except Exception as e:
        return False, str(e)
