import pandas as pd


def leer_archivo_metabase(archivo):
    """Lee un archivo de Metabase y devuelve un DataFrame válido."""
    if not archivo.name.lower().endswith(".xlsx"):
        raise ValueError("Metabase solo acepta archivos Excel (.xlsx).")
    if archivo.size == 0:
        raise ValueError(f"El archivo '{archivo.name}' está vacío.")

    archivo.seek(0)
    try:
        df = pd.read_excel(archivo)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"El archivo '{archivo.name}' no contiene columnas ni registros.") from exc

    if df.empty:
        raise ValueError(f"El archivo '{archivo.name}' no contiene registros.")
    return df

def filtrar_metabase_por_rango(df_metabase, fecha_min, fecha_max, columna_fecha="PC_create_date_GMT_Peru"):
    """
    Filtra df_metabase al rango [fecha_min - 2min, fecha_max + 2min].
    Retorna (df_filtrado, total_antes, total_despues).
    """
    total_antes = len(df_metabase)

    if fecha_min is None or fecha_max is None or pd.isna(fecha_min) or pd.isna(fecha_max):
        raise RuntimeError("No se pudo obtener un rango de fechas válido desde el archivo GMoney.")
    if columna_fecha not in df_metabase.columns:
        raise RuntimeError(f"Metabase no contiene la columna de fecha requerida: {columna_fecha}")

    df = df_metabase.copy()
    df[columna_fecha] = pd.to_datetime(df[columna_fecha], errors="coerce")

    limite_inferior = fecha_min - pd.Timedelta(minutes=2)
    limite_superior = fecha_max + pd.Timedelta(minutes=2)

    df_filtrado = df[
        (df[columna_fecha] >= limite_inferior) & (df[columna_fecha] <= limite_superior)
    ].copy()

    total_despues = len(df_filtrado)
    return df_filtrado, total_antes, total_despues

def mapear_metabase_a_staging(df_filtrado, codigo_conciliacion, tipo_conciliacion):
    """
    Renombra columnas del CSV Metabase al esquema de dev.staging_diaria_metabase.
    Retorna DataFrame listo para insertar_batches_supabase.
    """
    df = df_filtrado.copy()

    if tipo_conciliacion == "payout":
        MAPA = {
            "cus_name":                  "comercio_nombre",
            "codigo_kashio":             "deuda_id_interno",
            "moneda":                    "currency_code",
            "total":                     "amount",
            "estado":                    "estado",
            "creacion_deuda_fecha_peru": "fecha_operacion",
            "numero_operacion":          "id_operacion",
        }
        df = df.rename(columns=MAPA)
        df["deudor_documento"] = (
            df["tipo_de_documento"].astype(str).str.strip()
            + " - "
            + df["numero_documento"].astype(str).str.strip()
        )
        df["deudor_nombre"] = None
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    else:  # payin
        MAPA = {
            "Comercio_Nombre":         "comercio_nombre",
            "Deudor_Documento":        "deudor_documento",
            "Deudor_Nombre":           "deudor_nombre",
            "Deuda_public_id":         "deuda_id_interno",
            "currency_code":           "currency_code",
            "amount":                  "amount",
            "Deuda_Estado":            "estado",
            "PC_create_date_GMT_Peru": "fecha_operacion",
            "PPY_external_id":         "id_operacion",
        }
        df = df.rename(columns=MAPA)

    df["fecha_operacion"]     = pd.to_datetime(df["fecha_operacion"], errors="coerce")
    df["codigo_conciliacion"] = codigo_conciliacion
    df["tipo_conciliacion"]   = tipo_conciliacion

    COLUMNAS_STAGING = [
        "codigo_conciliacion",
        "tipo_conciliacion",
        "comercio_nombre",
        "deudor_documento",
        "deudor_nombre",
        "deuda_id_interno",
        "currency_code",
        "amount",
        "estado",
        "fecha_operacion",
        "id_operacion",
    ]

    columnas_presentes = [c for c in COLUMNAS_STAGING if c in df.columns]
    return df[columnas_presentes]
