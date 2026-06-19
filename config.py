import streamlit as st
import pandas as pd

# --- Entorno ---
ENTORNO: str = st.secrets["general"]["entorno"]
IS_DEV: bool = ENTORNO == "dev"
SCHEMA: str = "dev" if IS_DEV else "public"

# --- Supabase (una sola instancia, schema cambia según entorno) ---
SUPABASE_URL: str = st.secrets["supabase"]["url"]
SUPABASE_KEY: str = st.secrets["supabase"]["key"]

# --- n8n Webhooks ---
_n8n_env = "n8n_dev" if IS_DEV else "n8n_prod"
N8N_WEBHOOK_EECC: str    = st.secrets[_n8n_env]["webhook_eecc"]
N8N_LOGIN: str           = st.secrets[_n8n_env]["webhook_login"]
N8N_CONCILIACION: str    = st.secrets[_n8n_env]["webhook_conciliacion"]
N8N_PAYINS_ONLINE_V2: str = st.secrets[_n8n_env]["webhook_payins_online_v2"]

# --- Sesión ---
SESSION_TIMEOUT_MINUTES: int = 30

# --- Operadores (provisional hasta Microsoft Auth) ---
OPERADORES: list[str] = ["DU", "AA", "JK", "LK"]

# --- Colaboradores de contingencia (base de datos externa, solo prod) ---
_bbdd_col = st.secrets.get("bbdd_colaboradores", {})
BBDD_COLABORADORES_URL: str = _bbdd_col.get("url", "")
BBDD_COLABORADORES_KEY: str = _bbdd_col.get("key", "")
TABLA_COLABORADORES:    str = "colaboradores"   # nombre de la tabla
COLUMNA_COLABORADORES:  str = "nombre_completo"   # columna que contiene el nombre del colaborador

# --- Usuarios hardcodeados (provisional) ---
# Formato: { username: { "password": str, "role": str } }
USERS: dict[str, dict] = {
    "operador_payments": {"password": "gmoney123",    "role": "operador"},
    "admin_gmoney":      {"password": "admin123",     "role": "admin"},
    "supervisor_gmoney": {"password": "supervisor123", "role": "supervisor"},
    "operador_support":  {"password": "Soporte2026$", "role": "soporte"},
}

# --- Mapeo de columnas nativas del banco → esquema eecc_unificado ---
# None = valor hardcodeado desde el ciclo, no viene del archivo
COLUMNAS_BANCO: dict[str, dict] = {
    "GMONEY": {
        "operacion_id":    "instruction_id",
        "fecha_operacion": "fecha_movement",
        "amount":          "amount",
        "moneda":          "currency",
        "psptin":          "external_core_id",
        "banco_codigo":    None,   # hardcodeado desde ciclo
        "cuenta_origen":   None,   # hardcodeado desde ciclo
        "pais":            None,   # hardcodeado 'PE'
    },
    # BCP, BBVA, IBK se agregan aquí cuando se onboardeen
}

# --- Preprocesadores por banco (se aplican ANTES del rename de columnas) ---
def _preprocesar_gmoney(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("movement_day", "movement_hour"):
        if col not in df.columns:
            raise ValueError(f"Columna requerida '{col}' no encontrada en el archivo GMONEY")
    day  = df["movement_day"].astype(str).str.strip()
    hour = df["movement_hour"].astype(str).str.strip()
    df = df.copy()
    df["fecha_movement"] = day + " " + hour
    return df

PREPROCESADORES_BANCO: dict[str, object] = {
    "GMONEY": _preprocesar_gmoney,
}
