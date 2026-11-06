from datetime import datetime, timedelta

import pandas as pd
import requests

import config
from core.utils import TIMEZONE


def insertar_batches_supabase(df, tabla, batch_size=5000, callback=None):
    """
    Inserta df en chunks en tabla de Supabase (schema según config.SCHEMA).
    callback(filas_insertadas, total_filas) se llama tras cada batch exitoso.
    Retorna True si todo OK, lanza RuntimeError con detalle si algún batch falla.
    """
    total = len(df)
    if total == 0:
        raise RuntimeError(f"No hay operaciones para insertar en {tabla}: el filtro dejó el DataFrame vacío.")

    insertadas = 0

    for inicio in range(0, total, batch_size):
        chunk = df.iloc[inicio:inicio + batch_size].copy()
        for col in chunk.columns:
            if pd.api.types.is_datetime64_any_dtype(chunk[col]):
                chunk[col] = chunk[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
        import json as _json
        registros = _json.loads(chunk.to_json(orient="records"))

        resp = requests.post(
            f"{config.SUPABASE_URL}/rest/v1/{tabla}",
            headers={
                "apikey":          config.SUPABASE_KEY,
                "Authorization":   f"Bearer {config.SUPABASE_KEY}",
                "Content-Type":    "application/json",
                "Content-Profile": "dev",
                "Prefer":          "return=minimal",
            },
            json=registros,
        )

        if resp.status_code >= 300:
            batch_num = inicio // batch_size + 1
            raise RuntimeError(
                f"Batch {batch_num} falló — status {resp.status_code}: {resp.text[:500]}"
            )

        insertadas += len(chunk)
        if callback is not None:
            callback(insertadas, total)

    return True

def obtener_ciclos_fallidos():
    """Trae los ciclos FALLIDO de ciclo_ejecucion normalizados al esquema interno.
    Lanza requests.exceptions.HTTPError (con .response) o cualquier otro error de conexión.
    """
    resp = requests.get(
        f"{config.SUPABASE_URL}/rest/v1/ciclo_ejecucion",
        headers={
            "apikey": config.SUPABASE_KEY,
            "Authorization": f"Bearer {config.SUPABASE_KEY}",
            "Accept": "application/json",
            "Accept-Profile": config.SCHEMA,
        },
        params={
            "select": "ciclo_id,banco_codigo,fecha,hora,cuenta,estado,created_at",
            "estado": "eq.FALLIDO",
            "order": "created_at.asc",
        },
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json()
    # Normalizar al esquema interno (ventana_inicio/fin desde fecha+hora)
    ciclos = []
    for row in raw:
        try:
            vi = datetime.strptime(f"{row['fecha']}T{row['hora']}", "%Y-%m-%dT%H:%M:%S")
        except Exception:
            try:
                vi = datetime.strptime(f"{row['fecha']}T{row['hora']}", "%Y-%m-%dT%H:%M")
            except Exception:
                vi = datetime.now(TIMEZONE).replace(tzinfo=None)
        vf = vi + timedelta(hours=1)
        ciclos.append({
            "ciclo_id":      row["ciclo_id"],
            "banco_codigo":  row["banco_codigo"].strip(),
            "fecha":         row["fecha"],
            "ventana_inicio": vi.strftime("%Y-%m-%dT%H:%M:%S"),
            "ventana_fin":    vf.strftime("%Y-%m-%dT%H:%M:%S"),
            "cuenta_origen": row.get("cuenta"),
            "estado":        row["estado"],
            "created_at":    row["created_at"],
        })
    return ciclos

def obtener_colaboradores():
    """Colaboradores activos de la BBDD externa (schema según entorno) como [{"nombre", "area"}].
    Si la tabla aún no tiene la columna `area`, se devuelven con area=None.
    Fallback al hardcode de config si la consulta falla.
    """
    col = config.COLUMNA_COLABORADORES

    def _consultar(select):
        resp = requests.get(
            f"{config.BBDD_COLABORADORES_URL}/rest/v1/{config.TABLA_COLABORADORES}",
            headers={
                "apikey": config.BBDD_COLABORADORES_KEY,
                "Authorization": f"Bearer {config.BBDD_COLABORADORES_KEY}",
                "Accept": "application/json",
                "Accept-Profile": config.SCHEMA,
            },
            params={
                "select": select,
                "activo": "eq.true",
                "order":  f"{col}.asc",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        try:
            filas = _consultar(f"{col},area")
        except requests.exceptions.HTTPError:
            filas = _consultar(col)  # la columna area todavía no existe
        return [{"nombre": f[col], "area": f.get("area")} for f in filas]
    except Exception:
        return [{"nombre": n, "area": None} for n in config.OPERADORES]  # fallback al hardcode
