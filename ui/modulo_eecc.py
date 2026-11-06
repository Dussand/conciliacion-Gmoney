from datetime import datetime

import pandas as pd
import pytz
import requests
import streamlit as st

import config
from core.errores import ERRORES, MAX_INTENTOS, intentos_de, mostrar_error, registrar_intento
from core.utils import TIMEZONE, area_de_turno
from integraciones.n8n import enviar_a_n8n, reportar_banco_no_disponible
from integraciones.notificaciones import escalar_una_vez
from ui.escalamiento import boton_escalar
from integraciones.supabase_client import obtener_ciclos_fallidos, obtener_colaboradores
from procesamiento.eecc import leer_archivo_eecc, validar_y_mapear_eecc

COLORES_BANCO = {
    "GMONEY":     "#F59E0B",
    "BCP":        "#3B82F6",
    "BBVA":       "#1D4ED8",
    "INTERBANK":  "#10B981",
    "SCOTIABANK": "#EF4444",
}


def _limpiar_carga():
    st.session_state.archivo_eecc = None
    st.session_state.operador_eecc = None
    st.session_state.archivo_validado = False
    st.session_state.df_mapeado = None
    st.session_state.carga_confirmada = False
    st.session_state.resultado_envio = None

@st.dialog("Resultado de validación", width="large")
def mostrar_validacion(errores, df_mapeado, intento=None):
    total = len(df_mapeado)
    if len(errores) == 0:
        st.success(f"✅ Archivo válido — {total} registros listos para cargar")
        col1, col2 = st.columns(2)
        col1.metric("Total registros", total)
        col2.metric("Errores", 0)
        resumen = df_mapeado.attrs.get("resumen")
        if resumen:
            st.caption(
                f"Filas del día: {resumen['filas_del_dia']:,} · Otro día: {resumen['otro_dia']:,} · "
                f"Extornos: {resumen['extorno']:,} · Sin PSP TIN: {resumen['sin_psptin']:,} · "
                f"Repetidos: {resumen['repetidos']:,} · Monto total: S/ {resumen['monto_total']:,.2f}"
            )
        if total == 0:
            st.info("No hay movimientos para este bloque: se enviará la carga sin registros (es válido).")
        st.dataframe(df_mapeado.head(5), use_container_width=True)
        if st.button("Enviar operaciones →", type="primary", use_container_width=True):
            st.session_state.df_mapeado = df_mapeado
            st.session_state.archivo_validado = True
            st.session_state.carga_confirmada = True
            st.rerun()
    else:
        mostrar_error("DATOS_INVALIDOS", intento=intento)
        col1, col2 = st.columns(2)
        col1.metric("Total registros", total)
        col2.metric("Errores", len(errores))
        st.dataframe(pd.DataFrame(errores).drop(columns="codigo", errors="ignore"),
                     use_container_width=True, hide_index=True)
        if st.button("Cerrar", use_container_width=True):
            st.rerun()

def render_modulo_eecc():
    en_carga = st.session_state.ciclo_seleccionado is not None
    col_bandeja, col_menu = st.columns(2) if en_carga else (None, st.container())

    if col_menu.button("← Volver al menú", key="volver_eecc", use_container_width=True):
        st.session_state.modulo = None
        st.session_state.ciclo_seleccionado = None
        _limpiar_carga()
        st.rerun()
    if en_carga and col_bandeja.button("← Volver a bandeja", key="volver_bandeja", use_container_width=True):
        st.session_state.ciclo_seleccionado = None
        _limpiar_carga()
        st.rerun()

    if en_carga:
        _render_carga(st.session_state.ciclo_seleccionado)
    else:
        _render_bandeja()

def _render_carga(ciclo):
    # -----------------------------------------------
    # PANTALLA DE CARGA DEL EECC
    # -----------------------------------------------
    # --- Extraer datos del ciclo para mostrar ---
    banco        = ciclo["banco_codigo"]
    hora_fallo   = ciclo["ventana_inicio"][11:16]
    fecha_ciclo  = ciclo["ventana_inicio"][:10]
    cuenta_ciclo = ciclo.get("cuenta_origen") or "—"

    # Banner de contingencia
    st.warning(
        f"⚠️ **MODO CONTINGENCIA · {banco}** — "
        f"Sube el EECC del banco para reanudar la conciliación del fallo detectado a las **{hora_fallo}**."
    )

    st.write("")

    # ── Resumen del registro (detalle en desplegable) ───────────────────
    ventana_str = f"{ciclo['ventana_inicio'][11:16]} → {ciclo['ventana_fin'][11:16]}"
    st.markdown(f"**{banco}** · {cuenta_ciclo} · {fecha_ciclo} · bloque {ventana_str}")

    with st.expander("Ver detalle del registro"):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("🔢 ID Registro",        value=ciclo["ciclo_id"],  disabled=True)
            st.text_input("🏦 Proveedor",           value=banco,              disabled=True)
            st.text_input("💳 Cuenta",              value=cuenta_ciclo,       disabled=True)
        with c2:
            st.text_input("📅 Fecha",               value=fecha_ciclo,        disabled=True)
            st.text_input("🕐 Hora de conciliacion",   value=hora_fallo,         disabled=True)
            st.text_input("⏱️ Ventana horaria (filtro)", value=ventana_str, disabled=True)

    st.divider()

    # ── Sección 1 · Colaborador a cargo ─────────────────────────────────
    st.markdown("### 1 · Colaborador a cargo")
    st.caption("Selecciona tu nombre. Campo obligatorio.")

    operador, fuera_de_lista = _selector_colaborador()
    st.session_state.operador_eecc = operador
    st.session_state.operador_fuera_de_lista = fuera_de_lista

    st.divider()

    # ── Sección 2 · Subir EECC o reportar banco no disponible ───────────
    st.markdown(f"### 2 · Estado de cuenta — {banco}")
    _aplicar_prefill_no_disponible()
    no_disponible = st.toggle(
        "Banco no disponible",
        key="banco_no_disponible",
        disabled=st.session_state.archivo_validado,
    )
    if no_disponible:
        _render_banco_no_disponible(ciclo, operador, fuera_de_lista)
        return

    st.caption("Sube el archivo que el RPA no pudo extraer automáticamente.")

    archivo = st.file_uploader(
        "Archivo EECC del banco",
        type=config.EXTENSIONES_EECC.get(banco, config.EXTENSIONES_EECC_DEFAULT),
    )

    if archivo is not None:
        archivo.seek(0)

    listo = operador is not None and archivo is not None

    st.caption("Paso 1 de 2 · Al continuar se abrirá un resumen para confirmar antes de enviar.")

    if not st.session_state.archivo_validado:
        if st.button(
            "📎 Revisar y confirmar envío →",
            disabled=not listo,
            type="primary",
            use_container_width=True
        ):
            st.session_state.archivo_eecc = archivo
            st.session_state.operador_eecc = operador
            _validar_archivo(archivo, ciclo, operador)

        _render_error_carga(ciclo)
        _render_oferta_no_disponible(ciclo)
    else:
        # Se envía una sola vez; el resultado queda guardado para que un rerun no reenvíe.
        if st.session_state.carga_confirmada:
            with st.spinner("Enviando operaciones al orquestador..."):
                st.session_state.resultado_envio = enviar_a_n8n(
                    st.session_state.df_mapeado,
                    st.session_state.ciclo_seleccionado,
                    st.session_state.operador_eecc,
                    st.session_state.get("operador_fuera_de_lista", False),
                )
            st.session_state.carga_confirmada = False
            if not st.session_state.resultado_envio[0]:
                _contar_fallo_orquestador(ciclo)

        if st.session_state.get("resultado_envio"):
            exito, status = st.session_state.resultado_envio
            if exito:
                st.success(f"✅ {len(st.session_state.df_mapeado):,} operaciones enviadas — conciliación reanudada")
                if st.button("← Volver a bandeja", key="volver_tras_carga", use_container_width=True):
                    st.session_state.ciclo_seleccionado = None
                    _limpiar_carga()
                    st.rerun()
            else:
                _mostrar_fallo_orquestador(ciclo, operador, status)
                if st.button("Reintentar", use_container_width=True):
                    st.session_state.resultado_envio = None
                    st.session_state.carga_confirmada = True
                    st.rerun()

def _validar_archivo(archivo, ciclo, operador):
    """Lee y valida el EECC; registra el error del bloque (y el intento) si falla."""
    ciclo_id = ciclo["ciclo_id"]
    errores_carga = st.session_state.setdefault("error_carga_eecc", {})
    errores_carga.pop(ciclo_id, None)

    try:
        df = leer_archivo_eecc(archivo, ciclo["banco_codigo"])
    except ValueError as e:
        intento = registrar_intento(ciclo_id, "ARCHIVO_NO_VALIDO")
        errores_carga[ciclo_id] = {"codigo": "ARCHIVO_NO_VALIDO", "detalle": str(e), "intento": intento}
        return

    _bar = st.progress(0, text="Validando registros...")
    df_mapeado, errores = validar_y_mapear_eecc(df, ciclo["banco_codigo"], ciclo, _bar)
    _bar.empty()

    if not errores:
        mostrar_validacion(errores, df_mapeado)
        return

    codigo = errores[0].get("codigo", "ARCHIVO_NO_VALIDO")
    if codigo == "DATOS_INVALIDOS":
        mostrar_validacion(errores, df_mapeado, intento=registrar_intento(ciclo_id, codigo))
    elif ERRORES[codigo]["escala"]:
        notificado = escalar_una_vez(codigo, errores[0]["motivo"], ciclo, operador)
        errores_carga[ciclo_id] = {"codigo": codigo, "detalle": errores[0]["motivo"], "notificado": notificado}
    else:
        intento = registrar_intento(ciclo_id, codigo)
        errores_carga[ciclo_id] = {"codigo": codigo, "detalle": errores[0]["motivo"], "intento": intento}

def _render_error_carga(ciclo):
    err = st.session_state.get("error_carga_eecc", {}).get(ciclo["ciclo_id"])
    if err:
        mostrar_error(err["codigo"], err.get("detalle"), err.get("intento"), err.get("notificado"))

def _render_oferta_no_disponible(ciclo):
    """A partir del 3er intento fallido, ofrece marcar el banco como no disponible."""
    intentos = intentos_de(ciclo["ciclo_id"])
    if len(intentos) < MAX_INTENTOS:
        return
    with st.container(border=True):
        st.markdown(f"**Ya intentaste {len(intentos)} veces.** Si el banco no entrega un archivo válido, "
                    "márcalo como no disponible: cuenta como contingencia atendida.")
        if st.button("🚫 Marcar como banco no disponible", key="ofrecer_no_disponible", use_container_width=True):
            titulos = ", ".join(ERRORES[c]["titulo"] for c in intentos)
            st.session_state.prefill_no_disponible = {
                "motivo":     "Estado de cuenta incompleto o sin las operaciones del bloque",
                "comentario": f"{len(intentos)} intentos fallidos de carga: {titulos}.",
            }
            st.rerun()

def _aplicar_prefill_no_disponible():
    """Aplica el prellenado antes de crear los widgets (Streamlit no permite cambiarlos después)."""
    prefill = st.session_state.pop("prefill_no_disponible", None)
    if prefill:
        st.session_state.banco_no_disponible = True
        st.session_state.motivo_nd = prefill["motivo"]
        st.session_state.comentario_nd = prefill["comentario"]

def _contar_fallo_orquestador(ciclo):
    fallos = st.session_state.setdefault("fallos_orquestador", {})
    fallos[ciclo["ciclo_id"]] = fallos.get(ciclo["ciclo_id"], 0) + 1

def _fallos_orquestador(ciclo):
    return st.session_state.get("fallos_orquestador", {}).get(ciclo["ciclo_id"], 0)

def _mostrar_fallo_orquestador(ciclo, operador, status, en_modal=False):
    """1er fallo: pedir reintento. Desde el 2do: ofrecer escalar (el botón no puede ir dentro de otro modal)."""
    mostrar_error("ORQUESTADOR", f"status: {status}")
    if _fallos_orquestador(ciclo) >= 2 and not en_modal:
        boton_escalar("ORQUESTADOR", f"status: {status}", ciclo, operador, key="escalar_orquestador")

SIN_MOTIVO  = "— Selecciona el motivo —"
MOTIVO_OTRO = "Otro motivo"
MOTIVOS_NO_DISPONIBLE = [
    "Plataforma del banco en mantenimiento",
    "Credenciales de acceso rechazadas o bloqueadas",
    "Estado de cuenta incompleto o sin las operaciones del bloque",
    "La plataforma no permite descargar el estado de cuenta",
    MOTIVO_OTRO,
]

def _render_banco_no_disponible(ciclo, operador, fuera_de_lista):
    if st.session_state.get("reporte_enviado") == ciclo["ciclo_id"]:
        st.success("✅ Reporte enviado — el bloque queda atendido como banco no disponible")
        if st.button("← Volver a bandeja", key="volver_tras_reporte", use_container_width=True):
            st.session_state.ciclo_seleccionado = None
            st.session_state.reporte_enviado = None
            _limpiar_carga()
            st.rerun()
        return

    st.caption("Indica qué impidió obtener el estado de cuenta.")
    seleccion = st.selectbox(
        "🚫 Motivo",
        options=[SIN_MOTIVO] + MOTIVOS_NO_DISPONIBLE,
        key="motivo_nd",
    )
    motivo = None if seleccion == SIN_MOTIVO else seleccion
    comentario = st.text_area(
        "Comentario" + (" (obligatorio)" if motivo == MOTIVO_OTRO else " (opcional)"),
        placeholder="Ej.: el portal muestra error 503 desde las 14:10",
        key="comentario_nd",
    ).strip()

    falta = None
    if operador is None:
        falta = "Selecciona el colaborador a cargo."
    elif motivo is None:
        falta = "Selecciona el motivo."
    elif motivo == MOTIVO_OTRO and not comentario:
        falta = "Describe el motivo en el comentario."
    if falta:
        st.caption(falta)

    if st.button("🚫 Reportar banco no disponible", disabled=falta is not None,
                 type="primary", use_container_width=True):
        confirmar_no_disponible(ciclo, operador, fuera_de_lista, motivo, comentario)

    if _fallos_orquestador(ciclo) >= 2:
        boton_escalar("ORQUESTADOR", f"status: {st.session_state.get('ultimo_status_reporte')}",
                      ciclo, operador, key="escalar_reporte")

@st.dialog("🚫 Reportar banco no disponible", width="medium")
def confirmar_no_disponible(ciclo, operador, fuera_de_lista, motivo, comentario):
    st.caption("Revisa los datos antes de enviar.")

    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.markdown(f"**Banco**  \n{ciclo['banco_codigo']}")
        c2.markdown(f"**Cuenta**  \n{ciclo.get('cuenta_origen') or '—'}")
        c1.markdown(f"**Fecha**  \n{ciclo['ventana_inicio'][:10]}")
        c2.markdown(f"**Bloque**  \n{ciclo['ventana_inicio'][11:16]} → {ciclo['ventana_fin'][11:16]}")

    with st.container(border=True):
        st.markdown(f"**Motivo**  \n{motivo}")
        if comentario:
            st.markdown(f"**Comentario**  \n{comentario}")
        st.markdown(f"**Reporta**  \n{operador}" + (" · _no figura en la lista_" if fuera_de_lista else ""))

    st.success("✅ **Cuenta como contingencia atendida.** Reportar que el banco no está disponible "
               "suma a tu cumplimiento de atención, igual que una carga manual. No te perjudica.")
    st.info("El bloque quedará **atendido como banco no disponible** y saldrá de la bandeja. "
            "Ya no se podrá subir el EECC de este bloque.")

    col_cancelar, col_enviar = st.columns(2)
    if col_cancelar.button("Cancelar", use_container_width=True):
        st.rerun()
    if col_enviar.button("Confirmar y enviar", type="primary", use_container_width=True):
        with st.spinner("Enviando reporte al orquestador..."):
            exito, status = reportar_banco_no_disponible(ciclo, operador, fuera_de_lista, motivo, comentario)
        if exito:
            st.session_state.reporte_enviado = ciclo["ciclo_id"]
            st.rerun()
        else:
            _contar_fallo_orquestador(ciclo)
            st.session_state.ultimo_status_reporte = status
            _mostrar_fallo_orquestador(ciclo, operador, status, en_modal=True)
            if _fallos_orquestador(ciclo) >= 2:
                st.caption("Cierra esta ventana y usa «Escalar» debajo del formulario.")

SIN_SELECCION = "— Selecciona tu nombre —"
OTRO          = "Otro colaborador…"
NO_FIGURO     = "No figuro en la lista"

def _selector_colaborador():
    """Muestra solo al equipo del turno; el resto aparece únicamente al elegir «Otro colaborador…».
    Retorna (operador | None, fuera_de_lista).
    """
    colaboradores = obtener_colaboradores()
    turno = area_de_turno()
    del_turno = [c["nombre"] for c in colaboradores if c["area"] == turno]
    otros     = [c["nombre"] for c in colaboradores if c["area"] != turno]
    if not del_turno:  # nadie asignado al turno (o tabla sin área): lista completa
        del_turno, otros = otros, []

    seleccion = st.selectbox(
        "👤 Colaborador",
        options=[SIN_SELECCION] + del_turno + [OTRO],
        key="operador_eecc_selector",
    )
    if seleccion == SIN_SELECCION:
        return None, False
    if seleccion != OTRO:
        return seleccion, False

    seleccion_otro = st.selectbox(
        "👤 Selecciona tu nombre",
        options=[SIN_SELECCION] + otros + [NO_FIGURO],
        key="operador_eecc_selector_otro",
    )
    if seleccion_otro == NO_FIGURO:
        nombre = st.text_input("Nombre y apellido", key="operador_eecc_manual").strip()
        return (nombre or None), True
    if seleccion_otro == SIN_SELECCION:
        return None, False
    return seleccion_otro, False

def _render_bandeja():
    # -----------------------------------------------
    # BANDEJA DE FALLOS
    # -----------------------------------------------
    try:
        ciclos = obtener_ciclos_fallidos()
    except requests.exceptions.HTTPError as e:
        detalle = f"Supabase {e.response.status_code}: {e.response.text[:300]}"
        mostrar_error("BASE_DATOS", detalle)
        boton_escalar("BASE_DATOS", detalle, key="escalar_bd")
        st.stop()
    except Exception as e:
        mostrar_error("BASE_DATOS", e)
        boton_escalar("BASE_DATOS", str(e), key="escalar_bd")
        st.stop()

    ahora = datetime.now(TIMEZONE)

    def _secs_restantes(ciclo):
        try:
            vf = datetime.fromisoformat(ciclo["ventana_fin"])
            if vf.tzinfo is None:
                vf = TIMEZONE.localize(vf)
            return max(0.0, (vf - ahora).total_seconds())
        except Exception:
            return 0.0

    ciclos_ordenados = sorted(ciclos, key=_secs_restantes)

    # --- Métricas de cabecera ---
    secs_urgente = _secs_restantes(ciclos_ordenados[0]) if ciclos_ordenados else 0
    mm_u, ss_u   = int(secs_urgente // 60), int(secs_urgente % 60)
    tiempo_str   = f"{mm_u:02d}:{ss_u:02d}" if ciclos_ordenados else "—"

    m1, m2, m3 = st.columns(3)
    m1.metric("Fallos pendientes",    len(ciclos_ordenados))
    m2.metric("Resueltos hoy",        "—")
    m3.metric("Tiempo máx. restante", tiempo_str)

    st.divider()

    if not ciclos_ordenados:
        st.success("✅ Sin fallos activos — el sistema está operando con normalidad")
    else:
        st.markdown("**FALLOS ACTIVOS — ORDENADOS POR URGENCIA**")
        st.caption("Selecciona un fallo para resolver la contingencia manualmente.")
        st.write("")

        for ciclo in ciclos_ordenados:
            _render_tarjeta_fallo(ciclo, ahora, _secs_restantes(ciclo))

    st.write("")
    if st.button("↻ Refrescar bandeja", key="refrescar_bandeja"):
        st.rerun()

def _render_tarjeta_fallo(ciclo, ahora, secs_r):
    try:
        created = datetime.fromisoformat(ciclo["created_at"])
        if created.tzinfo is None:
            created = pytz.utc.localize(created)
        mins_creado = int((ahora - created.astimezone(TIMEZONE)).total_seconds() // 60)
        elapsed = f"{mins_creado} min" if mins_creado < 60 else f"{mins_creado // 60}h {mins_creado % 60}min"
    except (ValueError, TypeError):
        elapsed = "?"

    cuenta  = ciclo.get("cuenta_origen") or "—"
    banco   = ciclo["banco_codigo"]
    color   = COLORES_BANCO.get(banco, "#6B7280")
    mm_r, ss_r = int(secs_r // 60), int(secs_r % 60)
    fecha_monitoreo = (
        datetime.fromisoformat(ciclo["ventana_inicio"]).strftime("%H:%M")
        + " · " + ahora.strftime("%d %b %Y")
    )

    with st.container(border=True):
        col_info, col_accion = st.columns([7, 2])

        with col_info:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:16px'>"
                f"<div style='background:{color};border-radius:10px;min-width:56px;height:56px;"
                f"display:flex;align-items:center;justify-content:center;"
                f"font-weight:700;font-size:16px;color:#fff;flex-shrink:0'>{banco[:3]}</div>"
                f"<div>"
                f"<div><strong>{banco}</strong> &nbsp;·&nbsp;"
                f"<span style='color:gray;font-size:0.85em'>{cuenta}</span></div>"
                f"<div style='color:gray;font-size:0.8em;margin-top:3px'>Hora de monitoreo {fecha_monitoreo}</div>"
                f"<div style='color:gray;font-size:0.8em;margin-top:2px'>Fallo detectado hace {elapsed}</div>"
                f"</div></div>",
                unsafe_allow_html=True
            )

        with col_accion:
            st.markdown(
                f"<div style='color:#F59E0B;font-size:0.82em;text-align:right;"
                f"margin-bottom:6px'>⏱ {mm_r:02d}:{ss_r:02d} restantes</div>",
                unsafe_allow_html=True
            )
            if st.button("Resolver »", key=f"resolver_{ciclo['ciclo_id']}",
                         type="primary", use_container_width=True):
                st.session_state.ciclo_seleccionado = ciclo
                st.rerun()
