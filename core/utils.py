import re
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

TIMEZONE = pytz.timezone('America/Lima')


def cargar_css(ruta: str):
    """Inyecta un archivo CSS externo en la app de Streamlit"""
    with open(ruta) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def area_de_turno(ahora=None):
    """'payments' de lunes a viernes 09:00–17:59 (Lima); 'customer' en cualquier otro horario.
    No contempla feriados: en esos casos el colaborador usa "Mostrar todos".
    """
    ahora = ahora or datetime.now(TIMEZONE)
    if ahora.weekday() < 5 and 9 <= ahora.hour < 18:
        return "payments"
    return "customer"

def generate_session_id():
    """Genera un ID único para la sesión"""
    import random
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{timestamp}_{random_part}"

def extraer_fecha_de_codigo(codigo_unico):
    """Extrae la fecha_inicio del timestamp dentro del codigo_unico.
    Formato esperado: 20260320120007... → 2026-03-20 12:00:07
    """
    try:
        timestamp_str = codigo_unico[:14]  # YYYYMMDDHHmmss
        fecha = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        return fecha.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

def extraer_origen_de_codigo(codigo_unico):
    """Detecta el origen a partir del texto en el codigo_unico."""
    codigo_upper = codigo_unico.upper()
    if "METABASE" in codigo_upper:
        return "METABASE"
    elif "GMONEY" in codigo_upper:
        return "GMONEY"
    return "DESCONOCIDO"

def parsear_fecha_operacion(mov_day: pd.Series, mov_hour: pd.Series) -> pd.Series:
    """
    Combina movement_day y movement_hour en una Series datetime64.

    Detecta automáticamente el formato de movement_day:
      - YYYY-MM-DD  → format="%Y-%m-%d" (ISO, sin ambigüedad de día/mes)
      - DD/MM/YYYY  → dayfirst=True
    """
    muestra = str(mov_day.dropna().iloc[0]).strip() if not mov_day.dropna().empty else ""

    if re.match(r"^\d{4}-\d{2}-\d{2}", muestra):
        _dt = pd.to_datetime(mov_day, format="%Y-%m-%d", errors="coerce")
    else:
        # DD/MM/YYYY u otros formatos con día primero
        _dt = pd.to_datetime(mov_day, dayfirst=True, errors="coerce")

    _hr = pd.to_datetime(mov_hour, errors="coerce").dt.strftime("%H:%M:%S")
    return pd.to_datetime(_dt.dt.strftime("%Y-%m-%d") + " " + _hr, errors="coerce")
