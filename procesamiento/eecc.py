import re

import pandas as pd

import config
from core.utils import parsear_fecha_operacion

# Opcionales en config.py: solo existen en ramas con bancos que los usan (ej. BCP).
PREPROCESADORES_CON_CICLO = getattr(config, "PREPROCESADORES_CON_CICLO", {})
EECC_VACIO_VALIDO         = getattr(config, "EECC_VACIO_VALIDO", set())


def leer_archivo_eecc(archivo, banco):
    """Lee el EECC con el lector del banco (si existe) o como xlsx/csv genérico.
    Lanza ValueError si el archivo no se puede leer o está vacío.
    """
    try:
        if banco in config.LECTORES_BANCO:
            df = config.LECTORES_BANCO[banco](archivo)
        elif archivo.name.endswith(".xlsx"):
            df = pd.read_excel(archivo)
        else:
            df = pd.read_csv(archivo, sep=None, engine="python")
    except ValueError:
        raise
    except Exception as e:  # archivo vacío, dañado o con otra codificación
        raise ValueError(f"No se pudo leer el archivo: {e}") from e
    if df.empty:
        raise ValueError("El archivo no contiene registros.")
    df.columns = df.columns.str.strip()
    # Limpiar formato de fórmula Excel: ="valor" → valor
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.replace(r'^="(.*)"$', r'\1', regex=True)
    return df

def validar_y_mapear_eecc(df, banco_codigo, ciclo, _progress=None):
    banco_codigo = banco_codigo.strip()
    if banco_codigo not in config.COLUMNAS_BANCO:
        return df, [{"fila": "-", "columna": banco_codigo, "valor": None,
                     "motivo": "Banco sin mapeo de columnas definido — contactar al equipo técnico",
                     "codigo": "BANCO_SIN_CONFIGURAR"}]

    mapa = config.COLUMNAS_BANCO[banco_codigo]

    # Columnas que deben venir del archivo (valor != None)
    cols_archivo = {k: v for k, v in mapa.items() if v is not None}

    # Verificar columnas nativas requeridas
    df.columns = df.columns.str.strip()

    # Capturar columnas de fecha antes del preprocesador para parsear con dayfirst=True
    _mov_day  = df["movement_day"].copy()  if "movement_day"  in df.columns else None
    _mov_hour = df["movement_hour"].copy() if "movement_hour" in df.columns else None

    if banco_codigo in config.PREPROCESADORES_BANCO:
        try:
            df = config.PREPROCESADORES_BANCO[banco_codigo](df)
        except ValueError as e:
            codigo = "SIN_ABONOS" if "802" in str(e) else "ARCHIVO_NO_VALIDO"
            return df, [{"fila": "-", "columna": "preprocesador", "valor": None, "motivo": str(e), "codigo": codigo}]
    resumen = None
    if banco_codigo in PREPROCESADORES_CON_CICLO:
        try:
            df = PREPROCESADORES_CON_CICLO[banco_codigo](df, ciclo)
            resumen = df.attrs.get("resumen")
        except ValueError as e:
            return df, [{"fila": "-", "columna": "preprocesador", "valor": None, "motivo": str(e), "codigo": "ARCHIVO_NO_VALIDO"}]
    faltantes = [v for v in cols_archivo.values() if v not in df.columns]
    if faltantes:
        cols_reales = ", ".join(str(c) for c in df.columns.tolist())
        return df, [{"fila": "-", "columna": ", ".join(faltantes), "valor": None,
                     "motivo": f"Columnas requeridas ausentes. Columnas reales del archivo: {cols_reales}",
                     "codigo": "ARCHIVO_NO_VALIDO"}]

    # Renombrar al esquema eecc_unificado
    df = df.rename(columns={v: k for k, v in cols_archivo.items()})

    # Construir fecha_operacion detectando el formato de movement_day automáticamente
    if _mov_day is not None:
        df["fecha_operacion"] = parsear_fecha_operacion(_mov_day, _mov_hour)

    # Agregar columnas hardcodeadas
    df["banco_codigo"]  = ciclo["banco_codigo"]
    df["cuenta_origen"] = ciclo.get("cuenta_origen")
    df["pais"]          = "PE"

    # Filtro por ventana horaria del ciclo (o por fecha del ciclo si el banco no trae hora)
    filtro_dia = config.FILTRO_VENTANA_BANCO.get(banco_codigo) == "dia"
    if filtro_dia:
        hora_inicio = pd.Timestamp(ciclo["ventana_inicio"]).normalize()
        hora_fin    = hora_inicio + pd.Timedelta(days=1)
    else:
        hora_inicio = pd.Timestamp(ciclo["ventana_inicio"])
        hora_fin    = pd.Timestamp(ciclo["ventana_fin"])
    _dt_op = pd.to_datetime(df["fecha_operacion"], errors="coerce")

    df = df[(_dt_op >= hora_inicio) & (_dt_op < hora_fin)].copy()
    formato_fecha = "%Y-%m-%d" if filtro_dia else "%Y-%m-%d %H:%M:%S"
    df["fecha_operacion"] = pd.to_datetime(df["fecha_operacion"], errors="coerce").dt.strftime(formato_fecha)

    # Vacío válido solo si el archivo no trae movimientos de otro día (si los trae, es el archivo de otra fecha)
    otro_dia = (resumen or {}).get("otro_dia", 0)
    if df.empty and (banco_codigo not in EECC_VACIO_VALIDO or otro_dia > 0):
        return df, [{"fila": "-", "columna": "ventana",
                     "valor": f"{ciclo['ventana_inicio'].replace('T',' ')} → {ciclo['ventana_fin'].replace('T',' ')}",
                     "motivo": "Ningún registro del archivo corresponde a la ventana horaria de este ciclo",
                     "codigo": "FUERA_DE_BLOQUE"}]

    # Validar por fila
    errores = []
    total = len(df)
    for idx, (i, fila) in enumerate(df.iterrows()):
        if _progress is not None:
            _progress.progress((idx + 1) / total, text=f"Validando {idx + 1:,} / {total:,} registros...")
        nro = i + 2

        def err(col, val, motivo, _nro=nro):
            errores.append({"fila": _nro, "columna": col, "valor": val, "motivo": motivo, "codigo": "DATOS_INVALIDOS"})

        v = fila.get("operacion_id")
        if pd.isna(v):
            err("operacion_id", v, "Campo obligatorio ausente")

        fecha = fila.get("fecha_operacion")
        if pd.isna(fecha):
            err("fecha_operacion", fecha, "Campo obligatorio ausente")
        else:
            try:
                pd.to_datetime(fecha)
            except Exception:
                err("fecha_operacion", fecha, "No es una fecha válida")

        monto = fila.get("amount")
        if pd.isna(monto):
            err("amount", monto, "Campo obligatorio ausente")
        else:
            try:
                if float(monto) <= 0:
                    err("amount", monto, "Debe ser mayor a 0")
            except (ValueError, TypeError):
                err("amount", monto, "No es un valor numérico")

        moneda = fila.get("moneda")
        if pd.isna(moneda) or not re.fullmatch(r"[A-Z]{3}", str(moneda)):
            err("moneda", moneda, "Debe ser exactamente 3 letras mayúsculas")

        psptin = fila.get("psptin")
        if psptin is not None and not pd.isna(psptin):
            psptin_str = str(psptin).strip()
            esperado = 28 if banco_codigo == "GMONEY" else 12
            if not psptin_str.isdigit() or len(psptin_str) != esperado:
                err("psptin", psptin, f"Debe tener exactamente {esperado} dígitos para {banco_codigo}")

    COLUMNAS_EECC = [
        # esquema eecc_unificado
        "banco_codigo", "cuenta_origen", "operacion_id",
        "pais", "fecha_operacion", "amount", "moneda", "psptin",
        # opcionales de eecc_unificado (vienen en GMoney; en otros bancos van null)
        "origin_document", "target_name",
    ]
    df_mapeado = df[[col for col in COLUMNAS_EECC if col in df.columns]]
    df_mapeado.attrs["resumen"] = resumen
    return df_mapeado, errores
