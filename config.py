import streamlit as st
import pandas as pd
import re

# --- Entorno ---
ENTORNO: str = st.secrets["general"]["entorno"]
IS_DEV: bool = ENTORNO == "dev"
SCHEMA: str = "dev" if IS_DEV else "public"

# --- Supabase (una sola instancia, schema cambia según entorno) ---
SUPABASE_URL: str = st.secrets["supabase"]["url"]
SUPABASE_KEY: str = st.secrets["supabase"]["key"]

# --- n8n Webhooks ---
_n8n_env = "n8n_dev" if IS_DEV else "n8n_prod"
N8N_MOTOR_CONCI: str     = st.secrets[_n8n_env]["webhook_motor_conci"]
N8N_LOGIN: str           = st.secrets[_n8n_env]["webhook_login"]
N8N_CONCILIACION: str    = st.secrets[_n8n_env]["webhook_conciliacion"]
N8N_PAYINS_ONLINE_V2: str = st.secrets[_n8n_env]["webhook_payins_online_v2"]
N8N_PAYINS_DIARIA: str    = st.secrets[_n8n_env]["webhook_payins_diaria"]
N8N_JWT_SECRET: str       = st.secrets[_n8n_env].get("jwt_secret", "")   # firma HS256 para webhooks con JWT Auth

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

# --- Usuarios (desde secrets) ---
USERS: dict[str, dict] = st.secrets.get("users", {})

# --- Mapeo de columnas nativas del banco → esquema eecc_unificado ---
# None = valor hardcodeado desde el ciclo, no viene del archivo
COLUMNAS_BANCO: dict[str, dict] = {
    "GMONEY": {
        "operacion_id":    "instruction_id",
        "fecha_operacion": "fecha_movement",
        "amount":          "amount",
        "moneda":          "currency",
        "psptin":          "psptin_gmoney",    # = instruction_id (igual que el RPA); creada por _preprocesar_gmoney
        "banco_codigo":    None,   # hardcodeado desde ciclo
        "cuenta_origen":   None,   # hardcodeado desde ciclo
        "pais":            None,   # hardcodeado 'PE'
    },
    "BBVA": {
        "operacion_id":    "Núm.Movimiento",
        "fecha_operacion": "fecha_bbva",       # creada por _preprocesar_bbva
        "amount":          "importe_bbva",     # creada por _preprocesar_bbva
        "moneda":          "moneda_bbva",      # creada por _leer_bbva (cabecera)
        "psptin":          "psptin_bbva",      # creada por _preprocesar_bbva
        "banco_codigo":    None,
        "cuenta_origen":   None,
        "pais":            None,
    },
    # BCP, IBK se agregan aquí cuando se onboardeen
}

# --- Extensiones aceptadas en el uploader de EECC (default: txt, xlsx, csv) ---
EXTENSIONES_EECC_DEFAULT: list[str] = ["txt", "xlsx", "csv"]
EXTENSIONES_EECC: dict[str, list[str]] = {
    "BBVA": ["xls", "txt"],   # "Movimientos del Día": texto tabulado con extensión .xls
}

# --- Filtro de ventana por banco: "hora" (default, ventana del ciclo) o "dia" (fecha del ciclo) ---
# BBVA no trae hora en el EECC, solo fecha de operación.
FILTRO_VENTANA_BANCO: dict[str, str] = {
    "BBVA": "dia",
}

# --- Lectores por banco (reemplazan la lectura genérica xlsx/csv) ---
def _leer_bbva(archivo) -> pd.DataFrame:
    """Lee el reporte 'Movimientos del Día' de BBVA (texto tabulado latin-1 con extensión .xls).
    Descarta las líneas de título y el pie de saldos. Agrega la moneda de la cabecera como columna.
    El índice queda como (línea del archivo - 2) para que los errores reporten la línea real.
    """
    archivo.seek(0)
    lineas = archivo.read().decode("latin-1").splitlines()
    archivo.seek(0)

    idx_cab = next((i for i, l in enumerate(lineas) if l.strip().startswith("F.Operaci")), None)
    if idx_cab is None:
        raise ValueError("No se encontró la cabecera 'F.Operación'. ¿Es el reporte 'Movimientos del Día' de BBVA?")

    moneda = None
    for l in lineas[:idx_cab]:
        m = re.match(r"\s*\d{20}\s+([A-Z]{3})\b", l)
        if m:
            moneda = m.group(1)

    columnas = [c.strip() for c in lineas[idx_cab].split("\t") if c.strip()]
    filas, indices = [], []
    for nro_linea, l in enumerate(lineas[idx_cab + 1:], start=idx_cab + 2):
        partes = [p.strip() for p in l.split("\t")]
        if len(partes) < len(columnas) or not re.fullmatch(r"\d{2}-\d{2}-\d{4}", partes[0]):
            continue  # líneas vacías y pie "Saldo Contable"
        filas.append(partes[:len(columnas)])
        indices.append(nro_linea - 2)

    df = pd.DataFrame(filas, columns=columnas, index=indices)
    df["moneda_bbva"] = moneda
    return df

LECTORES_BANCO: dict[str, object] = {
    "BBVA": _leer_bbva,
}

# --- Preprocesadores por banco (se aplican ANTES del rename de columnas) ---
def _preprocesar_gmoney(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("movement_day", "movement_hour"):
        if col not in df.columns:
            raise ValueError(f"Columna requerida '{col}' no encontrada en el archivo GMONEY")
    df = df.copy()
    dt_day  = pd.to_datetime(df["movement_day"],  dayfirst=True, errors="coerce")
    dt_hour = pd.to_datetime(df["movement_hour"], errors="coerce")
    day  = dt_day.dt.strftime("%Y-%m-%d")
    hour = dt_hour.dt.strftime("%H:%M:%S")
    df["fecha_movement"] = day + " " + hour
    # En GMoney el psptin es el mismo instruction_id (el rename no puede mapear una columna a dos campos)
    if "instruction_id" in df.columns:
        df["psptin_gmoney"] = df["instruction_id"]
    return df

def _preprocesar_bbva(df: pd.DataFrame) -> pd.DataFrame:
    requeridas = ("F.Operación", "Código de Operación", "Concepto", "Núm.Movimiento", "Importe")
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        raise ValueError(f"Columnas requeridas no encontradas en el archivo BBVA: {', '.join(faltantes)}")

    # Solo abonos (802). Comisiones (735), ITF (527) y transferencias salientes no se concilian.
    df = df[df["Código de Operación"].astype(str).str.strip() == "802"].copy()
    if df.empty:
        raise ValueError("El archivo BBVA no contiene abonos (Código de Operación 802)")

    # El psptin va dentro del concepto con texto variable alrededor: "*262620692742 262620692742",
    # "*LIT805 262438856162    BANCA MOVIL". Se toma el primer número de 12 dígitos.
    df["psptin_bbva"] = df["Concepto"].astype(str).str.extract(r"\b(\d{12})\b", expand=False)
    df["fecha_bbva"]  = pd.to_datetime(df["F.Operación"], format="%d-%m-%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    df["importe_bbva"] = pd.to_numeric(df["Importe"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    return df

PREPROCESADORES_BANCO: dict[str, object] = {
    "GMONEY": _preprocesar_gmoney,
    "BBVA":   _preprocesar_bbva,
}
