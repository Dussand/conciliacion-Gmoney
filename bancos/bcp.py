"""Adaptador BCP (Telecrédito, cuenta …023).

Aplica las mismas reglas que el robot (TransformacionBCP v0.3.4); ver BCP_reglas_transformacion.md.
La carga manual debe dar el mismo resultado que el robot con el mismo archivo.
"""
import re
import unicodedata
from typing import BinaryIO

import pandas as pd

FILA_TITULOS = 7          # fila 8 del Excel (0-based)
MONEDAS = {"soles": "PEN"}
PATRON_PSPTIN = r"(2\d{11})(?!\d)"

# Columnas obligatorias: nombre canónico → patrón sobre el nombre normalizado.
# "?" representa un carácter dañado por la codificación (ó → �, ° → �).
COLUMNAS = {
    "Fecha":                 r"fecha",
    "Fecha valuta":          r"fechavaluta",
    "Descripción operación": r"descripci[o?]noperaci[o?]n",
    "Monto":                 r"monto",
    "Sucursal - agencia":    r"sucursalagencia",
    "N° operación":          r"n[o?]{0,2}operaci[o?]n",
    "Usuario":               r"usuario",
}


def _normalizar(nombre) -> str:
    """Minúsculas, sin tildes, espacios ni símbolos; cualquier otro carácter queda como '?'."""
    salida = []
    for ch in str(nombre).strip().lower():
        base = unicodedata.normalize("NFKD", ch)[0]
        if "a" <= base <= "z" or base.isdigit():
            salida.append(base)
        elif ch.isspace() or ch in "-_.:/()":
            continue
        else:
            salida.append("?")
    return "".join(salida)

def _texto_operacion(v):
    """N° operación como texto, sin el '.0' que agrega Excel a los números."""
    if pd.isna(v):
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()

def leer_eecc(archivo: BinaryIO) -> pd.DataFrame:
    """Lee el Excel de Telecrédito: moneda en B2, títulos en la fila 8, datos desde la fila 9.
    El índice queda como (fila del Excel - 2) para que los errores reporten la fila real.
    """
    archivo.seek(0)
    crudo = pd.read_excel(archivo, header=None, dtype=object)
    archivo.seek(0)
    if len(crudo) <= FILA_TITULOS:
        raise ValueError("El archivo no tiene la estructura de Telecrédito (títulos en la fila 8).")

    moneda_txt = _normalizar(crudo.iat[1, 1]) if crudo.shape[1] > 1 else ""
    if moneda_txt not in MONEDAS:
        raise ValueError(f"Moneda no reconocida en la celda B2: {crudo.iat[1, 1]!r}")

    titulos = [_normalizar(t) for t in crudo.iloc[FILA_TITULOS]]
    posiciones = {}
    for canonico, patron in COLUMNAS.items():
        idx = next((i for i, t in enumerate(titulos) if re.fullmatch(patron, t)), None)
        if idx is not None:
            posiciones[canonico] = idx
    faltantes = [c for c in COLUMNAS if c not in posiciones]
    if faltantes:
        raise ValueError(f"Columnas requeridas no encontradas en el archivo BCP: {', '.join(faltantes)}")

    df = crudo.iloc[FILA_TITULOS + 1:, list(posiciones.values())].copy()
    df.columns = list(posiciones.keys())
    df = df.dropna(how="all")
    # Todo como texto: la limpieza genérica posterior usa .str y borraría números en columnas mixtas.
    df["N° operación"] = df["N° operación"].map(_texto_operacion)
    for col in df.columns:
        df[col] = df[col].map(lambda v: None if pd.isna(v) else
                              (v.strftime("%d/%m/%Y") if isinstance(v, pd.Timestamp) or hasattr(v, "strftime")
                               else str(v).strip()))
    df.index = df.index - 1          # fila Excel = índice + 1 → errores muestran índice + 2
    df["moneda_bcp"] = MONEDAS[moneda_txt]
    return df

def preprocesar_eecc(df: pd.DataFrame, ciclo: dict) -> pd.DataFrame:
    """Fecha del ciclo → extornos → PSP TIN → repetidos → monto.
    Deja en df.attrs["resumen"] los conteos de cada descarte.
    Lanza ValueError si una fecha o un monto no se puede leer (cambio de formato).
    """
    fecha_ciclo = pd.Timestamp(ciclo["ventana_inicio"]).normalize()
    resumen = {"filas_archivo": len(df)}

    # 3. Fecha: dd/mm/aaaa (las fechas de Excel ya llegan así desde leer_eecc). Ilegible → se rechaza.
    fechas = pd.to_datetime(df["Fecha"].astype(str).str.strip(), format="%d/%m/%Y", errors="coerce")
    ilegibles = df.index[fechas.isna()]
    if len(ilegibles):
        fila = ilegibles[0] + 2
        raise ValueError(f"Fecha ilegible en la fila {fila}: {df.at[ilegibles[0], 'Fecha']!r}. "
                         "Puede haber cambiado el formato del archivo.")
    del_dia = fechas.dt.normalize() == fecha_ciclo
    resumen["otro_dia"] = int((~del_dia).sum())
    df = df[del_dia].copy()
    resumen["filas_del_dia"] = len(df)

    # 4. Extornos: si un N° operación se repite y una fila dice EXTORNO, salen todas sus filas.
    df["operacion_bcp"] = df["N° operación"].map(_texto_operacion)
    desc = df["Descripción operación"].astype(str).str.upper()
    repetida = df["operacion_bcp"].duplicated(keep=False)
    con_extorno = set(df.loc[repetida & desc.str.contains("EXTORNO", regex=False), "operacion_bcp"])
    excluir = df["operacion_bcp"].isin(con_extorno)
    resumen["extorno"] = int(excluir.sum())
    df = df[~excluir].copy()

    # 5. PSP TIN: 12 dígitos que empiezan en 2. Sin PSP TIN → fuera. Repetido → la primera fila.
    df["psptin_bcp"] = df["Descripción operación"].astype(str).str.extract(PATRON_PSPTIN, expand=False)
    sin_psptin = df["psptin_bcp"].isna()
    resumen["sin_psptin"] = int(sin_psptin.sum())
    df = df[~sin_psptin].copy()
    duplicado = df["psptin_bcp"].duplicated(keep="first")
    resumen["repetidos"] = int(duplicado.sum())
    df = df[~duplicado].copy()

    # 6. Monto: número con 2 decimales, sin comas de miles. Ilegible → se rechaza el archivo.
    montos = pd.to_numeric(df["Monto"].astype(str).str.replace(",", "", regex=False).str.strip(),
                           errors="coerce")
    if montos.isna().any():
        i = montos.index[montos.isna()][0]
        raise ValueError(f"Monto ilegible en la fila {i + 2}: {df.at[i, 'Monto']!r}.")
    df["monto_bcp"] = montos.round(2)

    df["fecha_bcp"] = fecha_ciclo.strftime("%Y-%m-%d")
    resumen["registros"] = len(df)
    resumen["monto_total"] = round(float(df["monto_bcp"].sum()), 2)
    df.attrs["resumen"] = resumen
    return df
