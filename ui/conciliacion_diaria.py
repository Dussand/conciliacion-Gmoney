"""Conciliación diaria (PayOuts y PayIns): Metabase + TXT GMoney → staging Supabase → n8n."""
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

import config
from core.utils import TIMEZONE, generate_session_id
from integraciones.supabase_client import insertar_batches_supabase
from procesamiento.gmoney import parsear_gmoney_txt
from procesamiento.metabase import filtrar_metabase_por_rango, leer_archivo_metabase, mapear_metabase_a_staging

# Lo único que cambia entre PayOuts y PayIns diaria
VARIANTES = {
    "payout": {
        "uploader_metabase":  "uploader_metabase_payout",
        "uploader_gmoney":    "uploader_gmoney_payout",
        "listar_archivos":    False,
        "columna_fecha":      "creacion_deuda_fecha_peru",
        "tipo_n8n":           "payout_diario",
    },
    "payin": {
        "uploader_metabase":  "uploader_metabase",
        "uploader_gmoney":    "uploader_gmoney",
        "listar_archivos":    True,
        "columna_fecha":      "PC_create_date_GMT_Peru",
        "tipo_n8n":           "payin_diaria",
    },
}


def render_conciliacion_diaria(tipo_conciliacion, tipo):
    v = VARIANTES[tipo]

    st.title(f"📄 {tipo_conciliacion} - GMoney")

    st.header("Subir archivos")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Metabase")
        archivo_metabase = st.file_uploader(
            'Archivo operaciones día anterior',
            type=['xlsx'],
            accept_multiple_files=True,
            key=v["uploader_metabase"]
        )

        if v["listar_archivos"] and archivo_metabase:
            st.caption("Archivos seleccionados:")
            for archivo in archivo_metabase:
                st.write(f"- {archivo.name} ({archivo.size:,} bytes)")

    with col2:
        st.subheader("GMoney")
        archivo_gmoney = st.file_uploader(
            "Archivo txt GMoney",
            type=["txt"],
            key=v["uploader_gmoney"]
        )

    st.divider()

    df_metabase = None

    if archivo_metabase:
        dfs = []
        try:
            for archivo in archivo_metabase:
                dfs.append(leer_archivo_metabase(archivo))
            df_metabase = pd.concat(dfs, ignore_index=True)
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            st.error(f"No se pudo leer el archivo de Metabase: {exc}")

    archivos_listos = df_metabase is not None and archivo_gmoney is not None

    if st.button(
        "Conciliar",
        disabled=not archivos_listos,
        type="primary",
        use_container_width=True
    ):
        data = _conciliar(df_metabase, archivo_gmoney, tipo, v)
        if data is not None:
            st.session_state.resultado_conciliacion = data
            st.session_state.archivos_subidos = True

    if st.session_state.resultado_conciliacion:
        _render_resultados(st.session_state.resultado_conciliacion)

def _conciliar(df_metabase, archivo_gmoney, tipo, v):
    codigo_conciliacion = generate_session_id()
    fecha_inicio = datetime.now(TIMEZONE).isoformat()
    inicio_ingesta = time.perf_counter()
    data = None
    response = None

    try:
        archivo_gmoney.seek(0)
        df_gmoney, fecha_min, fecha_max = parsear_gmoney_txt(archivo_gmoney)
        tx_gmoney          = len(df_gmoney)
        monto_gmoney_total = round(df_gmoney["monto_gmoney"].sum(), 2)

        df_filtrado_mb, _, _ = filtrar_metabase_por_rango(df_metabase, fecha_min, fecha_max, columna_fecha=v["columna_fecha"])

        df_mapeado_mb  = mapear_metabase_a_staging(df_filtrado_mb, codigo_conciliacion, tipo)
        tx_metabase    = len(df_mapeado_mb)
        monto_metabase = round(df_mapeado_mb["amount"].sum(), 2)

        bar_mb = st.progress(0, text="Metabase: preparando...")

        def cb_mb(actual, total):
            bar_mb.progress(actual / total, text=f"Metabase: {actual:,} / {total:,} filas")

        inicio_metabase = time.perf_counter()
        insertar_batches_supabase(df_mapeado_mb, "staging_diaria_metabase", callback=cb_mb)
        tiempo_metabase = time.perf_counter() - inicio_metabase
        bar_mb.empty()
        st.success(f"Metabase listo ✅ ({tiempo_metabase:.2f} s)")

        df_gmoney_staging = df_gmoney.copy()
        df_gmoney_staging["codigo_conciliacion"] = codigo_conciliacion
        bar_gm = st.progress(0, text="GMoney: preparando...")

        def cb_gm(actual, total):
            bar_gm.progress(actual / total, text=f"GMoney: {actual:,} / {total:,} filas")

        inicio_gmoney = time.perf_counter()
        insertar_batches_supabase(df_gmoney_staging, "staging_diaria_gmoney", callback=cb_gm)
        tiempo_gmoney = time.perf_counter() - inicio_gmoney
        bar_gm.empty()
        st.success(f"GMoney listo ✅ ({tiempo_gmoney:.2f} s)")
        st.info(
            f"Tiempo total de ingesta: {time.perf_counter() - inicio_ingesta:.2f} s"
        )

        # POST liviano a n8n — solo dispara el RPC, sin archivos
        with st.spinner("Conciliando..."):
            response = requests.post(
                config.N8N_CONCILIACION,
                json={
                    "codigo_conciliacion": codigo_conciliacion,
                    "tipo_conciliacion":   v["tipo_n8n"],
                    "session_id":          st.session_state.session_id,
                    "fecha_inicio":        fecha_inicio,
                    "tx_metabase":         tx_metabase,
                    "monto_metabase":      monto_metabase,
                    "tx_gmoney":           tx_gmoney,
                    "monto_gmoney_total":  monto_gmoney_total,
                },
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()

    except RuntimeError as e:
        st.error(str(e))
        st.stop()
    except requests.exceptions.Timeout:
        st.error("La solicitud tardó demasiado. Intenta nuevamente.")
        st.stop()
    except requests.exceptions.RequestException as e:
        st.error("Error al conectar con n8n")
        st.exception(e)
        st.stop()
    except ValueError:
        st.error("El webhook no devolvió un JSON válido")
        st.write(response.text)
        st.stop()
    except Exception as e:
        st.error(f"Error inesperado ({type(e).__name__}): {e}")
        st.stop()

    return data

def _render_resultados(resultado_conciliacion):
    resultado = resultado_conciliacion[0]
    importes = resultado.get("importes", [])
    detalle = resultado.get("detalle", [])

    st.divider()
    st.subheader("Conciliación por importes por día")
    st.write(
        "Resultado de la conciliación de los montos totales agregados por día, "
        "comparando Metabase vs GMoney"
    )

    if importes:
        df_importes = pd.DataFrame(importes)
        st.dataframe(df_importes, use_container_width=True)
    else:
        st.success("No se encontraron diferencias por importes.")

    st.divider()
    st.subheader("Conciliación por detalle de operaciones")
    st.write(
        "Resultado de la conciliación a nivel de operación individual, "
        "comparando los montos registrados entre Metabase y GMoney."
    )

    if detalle:
        df_detalle = pd.DataFrame(detalle)
        dif_detalle = (df_detalle['resultado'] != 'OK').any()
        if dif_detalle:
            st.dataframe(df_detalle, use_container_width=True)
            st.warning(f"Se identificaron {len(df_detalle)} diferencias.")
        else:
            st.success("No se encontraron diferencias a nivel de detalle.")
    else:
        st.success("No se encontraron diferencias a nivel de detalle.")
