import pandas as pd


def parsear_gmoney_txt(archivo):
    """
    Parsea archivo TXT GMoney de ancho fijo.
    Retorna (df, fecha_min, fecha_max).
    df columnas: id_transaccion_cce, estado, fecha_gmoney, doi, hora_completa, monto_gmoney
    """
    contenido = archivo.read().decode("latin-1")
    archivo.seek(0)

    filas = []
    for linea in contenido.splitlines():
        if len(linea) < 200:
            continue

        cci_origen         = linea[2:22].strip()
        importe_raw_str    = linea[42:57].strip()
        fecha_hora_raw     = linea[76:90].strip()
        id_transaccion_cce = linea[117:152].strip()
        estado             = linea[158:159].strip()

        doi = cci_origen[10:18] if len(cci_origen) >= 18 else ""

        fecha_gmoney  = ""
        hora_completa = ""
        if len(fecha_hora_raw) >= 14:
            y, m, d = fecha_hora_raw[0:4], fecha_hora_raw[4:6], fecha_hora_raw[6:8]
            hh, mm, ss = fecha_hora_raw[8:10], fecha_hora_raw[10:12], fecha_hora_raw[12:14]
            fecha_gmoney  = f"{y}-{m}-{d}"
            hora_completa = f"{hh}:{mm}:{ss}"

        try:
            monto_gmoney = round(int(importe_raw_str) / 100, 2)
        except (ValueError, TypeError):
            monto_gmoney = None

        filas.append({
            "id_transaccion_cce": id_transaccion_cce,
            "estado":             estado,
            "fecha_gmoney":       fecha_gmoney,
            "doi":                doi,
            "hora_completa":      hora_completa,
            "monto_gmoney":       monto_gmoney,
        })

    df = pd.DataFrame(filas, columns=[
        "id_transaccion_cce", "estado", "fecha_gmoney", "doi", "hora_completa", "monto_gmoney"
    ])

    # Las operaciones con estado R no participan en la conciliacion.
    df = df[df["estado"].str.upper().ne("R")].reset_index(drop=True)

    fecha_min = None
    fecha_max = None
    if not df.empty:
        dt_series = pd.to_datetime(df["fecha_gmoney"] + " " + df["hora_completa"], errors="coerce")
        fecha_min = dt_series.min()
        fecha_max = dt_series.max()

    return df, fecha_min, fecha_max
