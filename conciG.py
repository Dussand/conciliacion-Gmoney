import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from io import BytesIO
import time
import re
import config


def cargar_css(ruta: str):
    """Inyecta un archivo CSS externo en la app de Streamlit"""
    with open(ruta) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Configuración de la página
st.set_page_config(
    page_title="Conciliación G-Money",
    page_icon="💰",
    layout="wide"
)

cargar_css("style.css")

TIMEZONE = pytz.timezone('America/Lima')

# Inicializar session_state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.login_time = None
    st.session_state.session_id = None
    st.session_state.modulo = None
    st.session_state.ciclo_seleccionado = None

def send_to_n8n(endpoint, data):
    """Envía datos al webhook de n8n"""
    try:
        response = requests.post(
            endpoint,
            json=data,
            timeout=5,
            headers={'Content-Type': 'application/json'}
        )
        return response.status_code == 200
    except Exception:
        st.warning("Error 008")
        return False

def get_session_info():
    """Obtiene información básica de la sesión"""
    now = datetime.now(TIMEZONE)
    return {
        "usuario": st.session_state.user,
        "session_id": st.session_state.session_id,
        "tiempo_sesion_minutos": get_session_duration()
    }

def get_session_duration():
    """Calcula la duración de la sesión en minutos"""
    if st.session_state.login_time:
        now = datetime.now(TIMEZONE)
        duration = (now - st.session_state.login_time).total_seconds() / 60
        return round(duration, 2)
    return 0

def generate_session_id():
    """Genera un ID único para la sesión"""
    from datetime import datetime
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

def validar_y_mapear_eecc(df, banco_codigo, ciclo):
    # Verificar que el banco tiene mapeo definido
    if banco_codigo not in config.COLUMNAS_BANCO:
        return df, [{"fila": "-", "columna": banco_codigo, "valor": None,
                     "motivo": "Banco sin mapeo de columnas definido — contactar al equipo técnico"}]

    mapa = config.COLUMNAS_BANCO[banco_codigo]

    # Columnas que deben venir del archivo (valor != None)
    cols_archivo = {k: v for k, v in mapa.items() if v is not None}

    # Verificar columnas nativas requeridas
    df.columns = df.columns.str.strip()
    if banco_codigo in config.PREPROCESADORES_BANCO:
        try:
            df = config.PREPROCESADORES_BANCO[banco_codigo](df)
        except ValueError as e:
            return df, [{"fila": "-", "columna": "preprocesador", "valor": None, "motivo": str(e)}]
    faltantes = [v for v in cols_archivo.values() if v not in df.columns]
    if faltantes:
        cols_reales = ", ".join(str(c) for c in df.columns.tolist())
        return df, [{"fila": "-", "columna": ", ".join(faltantes), "valor": None,
                     "motivo": f"Columnas requeridas ausentes. Columnas reales del archivo: {cols_reales}"}]

    # Renombrar al esquema eecc_unificado
    df = df.rename(columns={v: k for k, v in cols_archivo.items()})

    # Agregar columnas hardcodeadas
    df["banco_codigo"]  = ciclo["banco_codigo"]
    df["cuenta_origen"] = ciclo.get("cuenta_origen")
    df["pais"]          = "PE"

    # Ventana dinámica: hora anterior a la hora actual en Lima
    ahora       = datetime.now(TIMEZONE).replace(tzinfo=None)
    hora_fin    = ahora.replace(minute=0, second=0, microsecond=0)
    hora_inicio = hora_fin - timedelta(hours=1)

    df["_datetime_op"] = pd.to_datetime(
        df["fecha_operacion"].astype(str).str.strip(),
        dayfirst=True, errors="coerce"
    )

    df = df[(df["_datetime_op"] >= hora_inicio) & (df["_datetime_op"] < hora_fin)].copy()
    df["fecha_operacion"] = df["_datetime_op"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.drop(columns=["_datetime_op"], errors="ignore")

    if df.empty:
        return df, [{"fila": "-", "columna": "ventana",
                     "valor": f"{ciclo['ventana_inicio']} → {ciclo['ventana_fin']}",
                     "motivo": "Ningún registro del archivo corresponde a la fecha de esta ventana"}]

    # Validar por fila
    errores = []
    for i, fila in df.iterrows():
        nro = i + 2

        def err(col, val, motivo, _nro=nro):
            errores.append({"fila": _nro, "columna": col, "valor": val, "motivo": motivo})

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
        # passthrough → n8n los necesita
        "created_at", "updated_at", "origin_name", "origin_type",
        "origin_document", "operation", "fee", "status",
    ]
    df_mapeado = df[[col for col in COLUMNAS_EECC if col in df.columns]]
    return df_mapeado, errores

def enviar_a_n8n(df_mapeado, ciclo, operador):
    df_send = df_mapeado.rename(columns={"operacion_id": "instruction_id"})
    contenido_csv = df_send.to_csv(index=False)

    payload = {
        "ciclo_id":       ciclo["ciclo_id"],
        "banco_codigo":   ciclo["banco_codigo"],
        "cuenta_origen":  ciclo.get("cuenta_origen") or ciclo.get("cuenta"),
        "origen_ingesta": "MANUAL",
        "status":         "success",
        "error_code":     "",
        "total_records":  str(len(df_mapeado)),
        "operador":       operador,
        "contenido":      contenido_csv,
    }

    try:
        resp = requests.post(config.N8N_WEBHOOK_EECC, json=payload, timeout=30)
        return resp.status_code in (200, 201), resp.status_code
    except Exception as e:
        return False, str(e)

@st.dialog("Resultado de validación", width="large")
def mostrar_validacion(errores, df_mapeado):
    total = len(df_mapeado)
    if len(errores) == 0:
        st.success(f"✅ Archivo válido — {total} registros listos para cargar")
        col1, col2 = st.columns(2)
        col1.metric("Total registros", total)
        col2.metric("Errores", 0)
        st.dataframe(df_mapeado.head(5), use_container_width=True)
        if st.button("Enviar operaciones →", type="primary", use_container_width=True):
            st.session_state.df_mapeado = df_mapeado
            st.session_state.archivo_validado = True
            st.session_state.carga_confirmada = True
            st.rerun()
    else:
        st.error(f"❌ {len(errores)} errores encontrados — corrige el archivo y vuelve a subir")
        col1, col2 = st.columns(2)
        col1.metric("Total registros", total)
        col2.metric("Errores", len(errores))
        st.dataframe(pd.DataFrame(errores), use_container_width=True, hide_index=True)
        if st.button("Cerrar y corregir", use_container_width=True):
            st.rerun()


@st.dialog("Login – Conciliación GMoney")
def login_dialog():
    st.markdown("### Inicio de Sesión")

    with st.form("login_form"):
        user = st.text_input("Usuario", key="login_user")
        password = st.text_input("Contraseña", type="password", key="login_pass")

        col1, col2 = st.columns([1, 1])

        with col1:
            submitted = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

        with col2:
            st.caption(f"⏱️ Sesión: {config.SESSION_TIMEOUT_MINUTES} min")

        if submitted:
            now = datetime.now(TIMEZONE)

            if user in config.USERS and config.USERS[user]['password'] == password:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.session_state.user_type = config.USERS[user]["role"]
                st.session_state.login_time = now
                st.session_state.session_id = generate_session_id()

                login_data = {
                    "evento": "login",
                    "usuario": user,
                    "session_id": st.session_state.session_id,
                    "timestamp": now.isoformat(),
                    "fecha": now.strftime("%Y-%m-%d"),
                    "hora": now.strftime("%H:%M:%S"),
                    "dia_semana": now.strftime("%A"),
                    'tipo_usuario': st.session_state.user_type
                }

                success = send_to_n8n(config.N8N_LOGIN, login_data)

                if success:
                    st.success("Acceso concedido")
                else:
                    st.success("Acceso concedido")
                    st.warning("Erro 008")

                import time
                time.sleep(1)
                st.rerun()
            else:
                failed_data = {
                    "evento": "login_failed",
                    "usuario_intento": user,
                    "timestamp": now.isoformat(),
                    "fecha": now.strftime("%Y-%m-%d"),
                    "hora": now.strftime("%H:%M:%S")
                }
                send_to_n8n(config.N8N_LOGIN, failed_data)

                st.error("❌ Usuario o contraseña incorrectos")

def logout():
    """Cierra la sesión del usuario"""
    st.session_state.clear()
    st.rerun()

def show_session_info():
    """Muestra información de conciliación y botón de cerrar sesión en el sidebar"""
    with st.sidebar:
        st.markdown("### 📋 Pasos para Conciliar")
        st.markdown("""
        1. **Subir archivo Metabase  ayer - ayer**
           _(en calendario metabase)_

        2. **Subir TXT GMoney**

        3. **Click Conciliar**
        """)

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="primary"):
            logout()

# -----------------------
# VERIFICACIÓN DE SESIÓN — comentado para pruebas
# -----------------------
if not st.session_state.authenticated:
    login_dialog()
    st.stop()
st.session_state.authenticated = True
st.session_state.user = st.session_state.get("user") or "dev"

# Inicializar session_state post-login
if 'resultado_conciliacion' not in st.session_state:
    st.session_state.resultado_conciliacion = None
if 'archivos_subidos' not in st.session_state:
    st.session_state.archivos_subidos = False
if 'modulo' not in st.session_state:
    st.session_state.modulo = None
if 'ciclo_seleccionado' not in st.session_state:
    st.session_state.ciclo_seleccionado = None
if 'archivo_eecc' not in st.session_state:
    st.session_state.archivo_eecc = None
if 'operador_eecc' not in st.session_state:
    st.session_state.operador_eecc = None
if 'archivo_validado' not in st.session_state:
    st.session_state.archivo_validado = False
if 'df_mapeado' not in st.session_state:
    st.session_state.df_mapeado = None
if 'carga_confirmada' not in st.session_state:
    st.session_state.carga_confirmada = False
if 'met_online_key' not in st.session_state:
    st.session_state.met_online_key = None
    st.session_state.df_met_online_cache = None
if 'panda_online_key' not in st.session_state:
    st.session_state.panda_online_key = None
    st.session_state.df_panda_cashin_cache = None
if 'conciliacion_hora' not in st.session_state:
    st.session_state.conciliacion_hora = None

# -----------------------
# TOPBAR
# -----------------------
col_logo, col_user, col_logout = st.columns([7, 2, 1])
with col_logo:
    st.markdown("🔴 &nbsp; **Motor de Conciliación · Contingencia**")
with col_user:
    st.markdown(f"👤 &nbsp; `{st.session_state.user}`")
with col_logout:
    if st.button("Cerrar sesión", key="btn_logout"):
        logout()

st.divider()

# -----------------------
# ROUTING DE MÓDULOS
# -----------------------
if st.session_state.modulo == "eecc":
    if st.button("← Volver", key="volver_eecc"):
        st.session_state.modulo = None
        st.session_state.ciclo_seleccionado = None
        st.session_state.archivo_eecc = None
        st.session_state.operador_eecc = None
        st.session_state.archivo_validado = False
        st.session_state.df_mapeado = None
        st.session_state.carga_confirmada = False
        st.rerun()

    if st.session_state.ciclo_seleccionado is not None:
        # -----------------------------------------------
        # PANTALLA DE CARGA DEL EECC
        # -----------------------------------------------
        ciclo = st.session_state.ciclo_seleccionado

        if st.button("← Volver a bandeja", key="volver_bandeja"):
            st.session_state.ciclo_seleccionado = None
            st.session_state.archivo_eecc = None
            st.session_state.operador_eecc = None
            st.session_state.archivo_validado = False
            st.session_state.df_mapeado = None
            st.session_state.carga_confirmada = False
            st.rerun()

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

        # ── Sección 1 · Datos del registro ──────────────────────────────────
        st.markdown("### 1 · Datos del registro")
        st.caption("Información traída desde base de datos. No editable.")

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("🔢 ID Registro",        value=ciclo["ciclo_id"],  disabled=True)
            st.text_input("🏦 Proveedor",           value=banco,              disabled=True)
            st.text_input("💳 Cuenta",              value=cuenta_ciclo,       disabled=True)
        with c2:
            st.text_input("📅 Fecha",               value=fecha_ciclo,        disabled=True)
            st.text_input("🕐 Hora de conciliacion",   value=hora_fallo,         disabled=True)

        st.divider()

        # ── Sección 2 · Colaborador a cargo ─────────────────────────────────
        st.markdown("### 2 · Colaborador a cargo")
        st.caption("Selecciona tu nombre. Campo obligatorio.")

        # Hardcodeado — descomentar bloque Supabase cuando esté disponible
        # colaboradores = config.OPERADORES

        #BBDD externa (prod) — completar config.TABLA_COLABORADORES y config.COLUMNA_COLABORADORES y descomentar
        try:
            resp = requests.get(
                f"{config.BBDD_COLABORADORES_URL}/rest/v1/{config.TABLA_COLABORADORES}",
                headers={
                    "apikey": config.BBDD_COLABORADORES_KEY,
                    "Authorization": f"Bearer {config.BBDD_COLABORADORES_KEY}",
                    "Accept": "application/json",
                },
                params={
                    "select": config.COLUMNA_COLABORADORES,
                    "order":  f"{config.COLUMNA_COLABORADORES}.asc",
                },
                timeout=10,
            )
            resp.raise_for_status()
            colaboradores = [row[config.COLUMNA_COLABORADORES] for row in resp.json()]
        except Exception:
            colaboradores = config.OPERADORES  # fallback al hardcode

        operador = st.selectbox(
            "👤 Colaborador",
            options=["— Selecciona tu nombre —"] + colaboradores,
        )

        st.divider()

        # ── Sección 3 · Subir EECC ───────────────────────────────────────────
        st.markdown(f"### 3 · ⬆️ Subir EECC — {banco}")
        st.caption("Sube el archivo que el RPA no pudo extraer automáticamente.")

        archivo = st.file_uploader(
            "Archivo EECC del banco",
            type=["txt", "xlsx", "csv"],
        )

        operador_valido = operador != "— Selecciona tu nombre —"
        listo = operador_valido and archivo is not None

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
                if archivo.name.endswith(".xlsx"):
                    df = pd.read_excel(archivo)
                else:
                    df = pd.read_csv(archivo, sep=None, engine="python")
                df.columns = df.columns.str.strip()
                # Limpiar formato de fórmula Excel: ="valor" → valor
                for col in df.select_dtypes(include="object").columns:
                    df[col] = df[col].str.replace(r'^="(.*)"$', r'\1', regex=True)
                df_mapeado, errores = validar_y_mapear_eecc(df, ciclo["banco_codigo"], ciclo)
                mostrar_validacion(errores, df_mapeado)
        else:
            if st.session_state.carga_confirmada:
                with st.spinner("Enviando operaciones al orquestador..."):
                    exito, status = enviar_a_n8n(
                        st.session_state.df_mapeado,
                        st.session_state.ciclo_seleccionado,
                        st.session_state.operador_eecc,
                    )

                if exito:
                    st.success(f"✅ {len(st.session_state.df_mapeado):,} operaciones enviadas — conciliación reanudada")
                    if st.button("← Volver a bandeja", key="volver_tras_carga", use_container_width=True):
                        st.session_state.ciclo_seleccionado = None
                        st.session_state.archivo_eecc       = None
                        st.session_state.operador_eecc      = None
                        st.session_state.df_mapeado         = None
                        st.session_state.archivo_validado   = False
                        st.session_state.carga_confirmada   = False
                        st.rerun()
                else:
                    st.error(f"❌ Error al contactar el orquestador (status: {status}) — intenta nuevamente o contacta al equipo técnico")
                    if st.button("Reintentar", use_container_width=True):
                        st.session_state.carga_confirmada = False
                        st.rerun()

    else:
        # -----------------------------------------------
        # BANDEJA DE FALLOS
        # -----------------------------------------------

        try:
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
                    "banco_codigo":  row["banco_codigo"],
                    "ventana_inicio": vi.strftime("%Y-%m-%dT%H:%M:%S"),
                    "ventana_fin":    vf.strftime("%Y-%m-%dT%H:%M:%S"),
                    "cuenta_origen": row.get("cuenta"),
                    "estado":        row["estado"],
                    "created_at":    row["created_at"],
                })
        except requests.exceptions.HTTPError:
            st.error(f"Error Supabase {resp.status_code}: {resp.text}")
            st.stop()
        except Exception as e:
            st.error(f"No se pudo conectar con Supabase: {e}")
            st.stop()

        ahora = datetime.now(TIMEZONE)

        COLORES_BANCO = {
            "GMONEY":     "#F59E0B",
            "BCP":        "#3B82F6",
            "BBVA":       "#1D4ED8",
            "INTERBANK":  "#10B981",
            "SCOTIABANK": "#EF4444",
        }

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
                try:
                    vi    = datetime.fromisoformat(ciclo["ventana_inicio"]).strftime("%H:%M")
                    vf_dt = datetime.fromisoformat(ciclo["ventana_fin"])
                    if vf_dt.tzinfo is None:
                        vf_dt = TIMEZONE.localize(vf_dt)
                    vf = vf_dt.strftime("%H:%M")
                except (ValueError, TypeError):
                    vi, vf = "?", "?"

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
                secs_r  = _secs_restantes(ciclo)
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

        st.write("")
        if st.button("↻ Refrescar bandeja", key="refrescar_bandeja"):
            st.rerun()

elif st.session_state.modulo == "conciliacion":
    if st.button("← Volver", key="volver_conciliacion"):
        st.session_state.modulo = None
        st.rerun()

    # Seleccionamos el tipo de conciliacion que usaremos para validar operaciones
    tipo_conciliacion = st.selectbox(
        'Selecciona el tipo de conciliacion',
        [
            "Conciliacion PayOuts - Diaria",
            "Conciliacion PayIns - Online",
            "Conciliacion PayIns - Diaria"
        ]
    )

    if tipo_conciliacion == "Conciliacion PayOuts - Diaria":
        st.title(f"📄 {tipo_conciliacion} - GMoney")
        conciliacion_code = "conciliacion_diaria"

        st.header("Subir archivos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Metabase")
            archivo_metabase = st.file_uploader(
                'Archivo operaciones día anterior',
                type=['xlsx'],
                accept_multiple_files=True,
                key='uploader_metabase'
            )

        with col2:
            st.subheader("GMoney")
            archivo_gmoney = st.file_uploader(
                "Archivo txt GMoney",
                type=["txt"],
                key='uploader_gmoney'
            )

        st.divider()

        df_metabase = None
        archivo_metabase_consolidado = None

        if archivo_metabase:
            dfs = []
            for archivo in archivo_metabase:
                df_temp = pd.read_excel(archivo)
                dfs.append(df_temp)
            df_metabase = pd.concat(dfs, ignore_index=True)
            buffer = BytesIO()
            df_metabase.to_excel(buffer, index=False)
            buffer.seek(0)
            archivo_metabase_consolidado = buffer

        archivos_listos = archivo_metabase_consolidado is not None and archivo_gmoney is not None

        if st.button(
            "Conciliar",
            disabled=not archivos_listos,
            type="primary",
            use_container_width=True
        ):
            files = {
                "metabase": (
                    "metabase_consolidado.xlsx",
                    archivo_metabase_consolidado.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                "gmoney_txt": (
                    archivo_gmoney.name,
                    archivo_gmoney.getvalue(),
                    "text/plain"
                )
            }

            with st.spinner("Procesando conciliación..."):
                try:
                    session_metadata = {
                        'session_id': st.session_state.session_id,
                        'tipo_conciliacion': conciliacion_code,
                        'conciliacion': 'payout_diaria'
                    }
                    response = requests.post(
                        config.N8N_CONCILIACION,
                        files=files,
                        data=session_metadata,
                        timeout=180
                    )
                    response.raise_for_status()
                    data = response.json()

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
                    st.error("Error inesperado")
                    st.exception(e)
                    st.stop()

            st.session_state.resultado_conciliacion = data
            st.session_state.archivos_subidos = True

        if st.session_state.resultado_conciliacion:
            resultado = st.session_state.resultado_conciliacion[0]
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
                hay_diferencias = (
                    df_detalle['diferencia'].notna().any()
                    and (df_detalle['diferencia'] != 0).any()
                )
                if hay_diferencias:
                    st.dataframe(df_detalle, use_container_width=True)
                    st.warning(f"Se identificaron {len(df_detalle)} diferencias.")
                else:
                    st.success("No se encontraron diferencias a nivel de detalle.")
            else:
                st.success("No se encontraron diferencias a nivel de detalle.")

    # ============================================================
    # PAYINS ONLINE — CONCILIACIÓN POR HORA (v2)
    # ============================================================
    elif tipo_conciliacion == 'Conciliacion PayIns - Online':
        st.title(f"📄 {tipo_conciliacion} - GMoney (v2)")
        conciliacion_code = "payins_online"

        st.header("Subir archivos")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Metabase")
            archivo_metabase_online = st.file_uploader(
                'Archivo operaciones día anterior',
                type=['xlsx', 'json', 'csv'],
                accept_multiple_files=True,
                key='uploader_metabase_online'
            )

        with col2:
            st.subheader("GMoney")
            panda_empresas = st.file_uploader(
                "Archivo Panda Empresas",
                type=["csv"],
                key='uploader_gmoney_online'
            )

        # ========================
        # CARGA Y CACHÉ METABASE
        # ========================
        df_metabase_online = None
        if archivo_metabase_online:
            met_key = [(f.name, f.size) for f in archivo_metabase_online]
            if st.session_state.met_online_key != met_key:
                dfs = []
                for archivo in archivo_metabase_online:
                    if archivo.name.endswith('.json'):
                        t = pd.read_json(archivo, dtype={'PPY_external_id': str})
                    elif archivo.name.endswith('.csv'):
                        t = pd.read_csv(archivo, dtype={'PPY_external_id': str})
                    else:
                        t = pd.read_excel(archivo, dtype={'PPY_external_id': str})
                    dfs.append(t)
                df_metabase_online = pd.concat(dfs, ignore_index=True)
                st.session_state.met_online_key = met_key
                st.session_state.df_met_online_cache = df_metabase_online
            else:
                df_metabase_online = st.session_state.df_met_online_cache

        # ========================
        # CARGA Y CACHÉ PANDA EMPRESAS
        # ========================
        if panda_empresas is not None:
            panda_key = (panda_empresas.name, panda_empresas.size)
            if st.session_state.panda_online_key != panda_key:
                df_panda_cashin = pd.read_csv(BytesIO(panda_empresas.getvalue()), sep=";")
                df_panda_cashin = df_panda_cashin[df_panda_cashin['operation'] == 'CASHIN']
                # limpiar formato excel-style ="..."
                df_panda_cashin['instruction_id'] = (
                    df_panda_cashin['instruction_id']
                    .astype(str)
                    .str.replace('="', '', regex=False)
                    .str.replace('"', '', regex=False)
                    .str.strip()
                )
                st.session_state.panda_online_key = panda_key
                st.session_state.df_panda_cashin_cache = df_panda_cashin

        # ========================
        # VISTA PREVIA
        # ========================
        if df_metabase_online is not None or panda_empresas is not None:
            prev_col1, prev_col2 = st.columns(2)
            with prev_col1:
                if df_metabase_online is not None:
                    st.caption(f"Vista previa Metabase — {len(df_metabase_online)} filas totales")
                    muestra = "desconocido"
                    try:
                        muestra = str(df_metabase_online['PC_create_date_GMT_Peru'].dropna().iloc[0])
                        pd.to_datetime(
                            df_metabase_online['PC_create_date_GMT_Peru'].astype(str).str.replace(',', '', regex=False),
                            dayfirst=True, errors='coerce'
                        )
                    except Exception:
                        st.error(f"Formato de fecha no reconocido en `PC_create_date_GMT_Peru`: `{muestra}`")
            with prev_col2:
                if st.session_state.df_panda_cashin_cache is not None:
                    st.caption(f"Vista previa Panda Empresas — {len(st.session_state.df_panda_cashin_cache)} filas (CASHIN)")

        # ========================
        # BOTÓN CONCILIAR
        # ========================
        st.divider()
        archivos_listos_online = (df_metabase_online is not None) and (panda_empresas is not None)

        if st.button("Conciliar", disabled=not archivos_listos_online, type="primary", use_container_width=True):

            if not st.session_state.get('session_id'):
                st.session_state.session_id = generate_session_id()
            session_id = st.session_state.session_id

            hora_filtro = datetime.now(TIMEZONE).hour - 1

            # ----------- METABASE -----------
            dt_met = pd.to_datetime(
                df_metabase_online['PC_create_date_GMT_Peru'].astype(str).str.replace(',', '', regex=False),
                dayfirst=True, errors='coerce'
            )
            df_met_filtrado = df_metabase_online[dt_met.dt.hour == hora_filtro].copy()
            df_met_filtrado['_fecha_iso'] = dt_met[dt_met.dt.hour == hora_filtro].dt.strftime('%Y-%m-%d %H:%M:%S')

            meta_rows = [{
                "session_id": session_id,
                "source": "metabase",
                "join_key": str(r["PPY_external_id"]).strip(),
                "amount": float(r["amount"]) if pd.notna(r.get("amount")) else None,
                "currency": r.get("currency_code"),
                "fecha": r.get("_fecha_iso"),
                "comercio_nombre": r.get("Comercio_Nombre"),
                "deudor_nombre": r.get("Deudor_Nombre"),
                "deudor_documento": r.get("Deudor_Documento"),
                "deuda_public_id": r.get("Deuda_public_id"),
                "deuda_estado": r.get("Deuda_Estado"),
            } for r in df_met_filtrado.where(df_met_filtrado.notna(), None).to_dict("records")]

            # ----------- GMONEY -----------
            df_panda_envio = st.session_state.df_panda_cashin_cache.copy()
            df_panda_envio = df_panda_envio[df_panda_envio['movement_hour'].str[:2].astype(int) == hora_filtro]
            df_panda_envio['_fecha_iso'] = pd.to_datetime(
                df_panda_envio['movement_day'] + ' ' + df_panda_envio['movement_hour'],
                dayfirst=True, errors='coerce'
            ).dt.strftime('%Y-%m-%d %H:%M:%S')

            gm_rows = [{
                "session_id": session_id,
                "source": "gmoney",
                "join_key": str(r["instruction_id"]).strip().strip('"'),
                "amount": float(r["amount"]) if pd.notna(r.get("amount")) else None,
                "currency": r.get("currency"),
                "fecha": r.get("_fecha_iso"),
                "origin_name": r.get("origin_name"),
                "origin_document": str(r["origin_document"]) if pd.notna(r.get("origin_document")) else None,
                "target_name": r.get("target_name"),
                "fee": float(r["fee"]) if pd.notna(r.get("fee")) else None,
                "entity": r.get("entity"),
                "operation": r.get("operation"),
            } for r in df_panda_envio.where(df_panda_envio.notna(), None).to_dict("records")]

            # Normalizar a las mismas keys
            ALL_KEYS = [
                "session_id", "source", "join_key", "amount", "currency", "fecha",
                "comercio_nombre", "deudor_nombre", "deudor_documento", "deuda_public_id", "deuda_estado",
                "origin_name", "origin_document", "target_name", "fee", "entity", "operation",
            ]
            def _normalize(r):
                return {k: r.get(k) for k in ALL_KEYS}
            meta_rows = [_normalize(r) for r in meta_rows]
            gm_rows   = [_normalize(r) for r in gm_rows]

            payload = {
                "session_id": session_id,
                "tipo_conciliacion": "payins_online",
                "hora_filtro": hora_filtro,
                "fecha_inicio_iso": datetime.now(TIMEZONE).isoformat(),
                "rows": meta_rows + gm_rows,
            }

            with st.spinner("Procesando conciliación..."):
                try:
                    response = requests.post(
                        config.N8N_PAYINS_ONLINE_V2,
                        json=payload,
                        timeout=180,
                        headers={'Content-Type': 'application/json'}
                    )
                    response.raise_for_status()
                    if not response.text.strip():
                        st.warning("n8n respondió vacío.")
                        st.stop()
                    data = response.json()
                except requests.exceptions.Timeout:
                    st.error("La solicitud tardó demasiado."); st.stop()
                except requests.exceptions.RequestException as e:
                    st.error("Error al conectar con n8n"); st.exception(e); st.stop()
                except ValueError:
                    st.error("El webhook no devolvió un JSON válido"); st.write(response.text); st.stop()
                except Exception as e:
                    st.error("Error inesperado"); st.exception(e); st.stop()

            st.session_state.resultado_conciliacion = data
            st.session_state.archivos_subidos = True

            # ----------- CONCILIACIÓN LOCAL POR HORA -----------
            try:
                grp_met = (
                    df_metabase_online
                    .assign(_fecha=dt_met.dt.date, _hora=dt_met.dt.hour)
                    .groupby(['_fecha', '_hora'])['amount'].sum()
                    .reset_index()
                    .rename(columns={'_fecha': 'fecha_conciliacion', '_hora': 'hora', 'amount': 'total_amount_metabase'})
                )

                df_panda_hora = st.session_state.df_panda_cashin_cache.copy()
                dt_panda = pd.to_datetime(
                    df_panda_hora['movement_day'] + ' ' + df_panda_hora['movement_hour'],
                    dayfirst=True, errors='coerce'
                )
                grp_panda = (
                    df_panda_hora
                    .assign(_fecha=dt_panda.dt.date, _hora=dt_panda.dt.hour)
                    .groupby(['_fecha', '_hora'])['amount'].sum()
                    .reset_index()
                    .rename(columns={'_fecha': 'fecha_conciliacion', '_hora': 'hora', 'amount': 'total_amount_gmoney'})
                )

                df_conc_hora = (
                    grp_met.merge(grp_panda, on=['fecha_conciliacion', 'hora'], how='outer')
                    .fillna(0)
                    .sort_values(['fecha_conciliacion', 'hora'])
                    .reset_index(drop=True)
                )
                df_conc_hora['diferencia'] = df_conc_hora['total_amount_metabase'] - df_conc_hora['total_amount_gmoney']
                df_conc_hora['estado'] = df_conc_hora['diferencia'].apply(lambda x: 'Conciliado' if x == 0 else 'Diferencias')
                hora_actual = datetime.now(TIMEZONE).hour
                df_conc_hora = df_conc_hora[df_conc_hora['hora'] < hora_actual].reset_index(drop=True)
                st.session_state.conciliacion_hora = df_conc_hora
            except Exception as e:
                st.error(f"Error en conciliación local: {e}")

        # ========================
        # RESULTADOS
        # ========================
        if st.session_state.conciliacion_hora is not None:
            st.divider()
            st.subheader("Conciliación por importes por hora")
            st.write("Totales agregados por hora, Metabase vs GMoney (cálculo local).")
            st.dataframe(st.session_state.conciliacion_hora, use_container_width=True)

        if st.session_state.resultado_conciliacion:
            raw = st.session_state.resultado_conciliacion
            resultado = raw[0] if isinstance(raw, list) else raw

            detalle = resultado.get("detalle", [])

            st.divider()
            st.subheader("Conciliación por detalle de operaciones")
            st.write(
                "Resultado de la conciliación a nivel de operación individual, "
                "comparando los montos registrados entre Metabase y GMoney."
            )

            if detalle:
                df_raw = pd.DataFrame(detalle)

                df_view = pd.DataFrame({
                    "id":             df_raw["ppy_external_id"],
                    "Hora":           df_raw["hora"],
                    "Monto_metabase": df_raw["amount_metabase"],
                    "Monto_gmoney":   df_raw["monto_gmoney"],
                    "Resultado":      df_raw["resultado"],
                    "Comercio":       df_raw["gmoney_target_name"].fillna(df_raw.get("comercio_nombre")),
                    "Moneda":         df_raw["moneda_metabase"].fillna(df_raw["gmoney_currency"]),
                    "Banco":          df_raw["gmoney_entity"],
                    "Diferencia":     df_raw["diferencia"],
                    "Nombre GMoney":  df_raw["gmoney_origin_name"],
                    "DNI GMoney":     df_raw["gmoney_origin_document"],
                })

                st.dataframe(df_view, use_container_width=True)
                st.warning(f"Se identificaron {len(df_view)} diferencias.")
            else:
                st.success("No se encontraron diferencias a nivel de detalle.")

    elif tipo_conciliacion == "Conciliacion PayIns - Diaria":
        st.title(f"📄 {tipo_conciliacion} - GMoney")
        conciliacion_code = "conciliacion_diaria"

        st.header("Subir archivos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Metabase")
            archivo_metabase = st.file_uploader(
                'Archivo operaciones día anterior',
                type=['xlsx'],
                accept_multiple_files=True,
                key='uploader_metabase'
            )

        with col2:
            st.subheader("GMoney")
            archivo_gmoney = st.file_uploader(
                "Archivo txt GMoney",
                type=["txt"],
                key='uploader_gmoney'
            )

        st.divider()

        df_metabase = None
        archivo_metabase_consolidado = None

        if archivo_metabase:
            dfs = []
            for archivo in archivo_metabase:
                df_temp = pd.read_excel(archivo)
                dfs.append(df_temp)
            df_metabase = pd.concat(dfs, ignore_index=True)
            buffer = BytesIO()
            df_metabase.to_excel(buffer, index=False)
            buffer.seek(0)
            archivo_metabase_consolidado = buffer

        archivos_listos = archivo_metabase_consolidado is not None and archivo_gmoney is not None

        if st.button(
            "Conciliar",
            disabled=not archivos_listos,
            type="primary",
            use_container_width=True
        ):
            files = {
                "metabase": (
                    "metabase_consolidado.xlsx",
                    archivo_metabase_consolidado.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                "gmoney_txt": (
                    archivo_gmoney.name,
                    archivo_gmoney.getvalue(),
                    "text/plain"
                )
            }

            with st.spinner("Procesando conciliación..."):
                try:
                    session_metadata = {
                        'session_id': st.session_state.session_id,
                        'tipo_conciliacion': conciliacion_code,
                        'conciliacion': 'payin_diaria'
                    }
                    response = requests.post(
                        config.N8N_CONCILIACION,
                        files=files,
                        data=session_metadata,
                        timeout=180
                    )
                    response.raise_for_status()
                    data = response.json()

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
                    st.error("Error inesperado")
                    st.exception(e)
                    st.stop()

            st.session_state.resultado_conciliacion = data
            st.session_state.archivos_subidos = True

        if st.session_state.resultado_conciliacion:
            resultado = st.session_state.resultado_conciliacion[0]
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
                dif_detalle = (df_detalle['resultado_conciliacion'] != 'OK').any()
                if dif_detalle:
                    st.dataframe(df_detalle, use_container_width=True)
                    st.warning(f"Se identificaron {len(df_detalle)} diferencias.")
                else:
                    st.success("No se encontraron diferencias a nivel de detalle.")
            else:
                st.success("No se encontraron diferencias a nivel de detalle.")

else:
    # -----------------------
    # PANTALLA DE SELECCIÓN
    # -----------------------
    st.markdown("<h2 style='text-align:center'>¿Qué necesitas hacer?</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray'>Selecciona el módulo que necesitas usar</p>", unsafe_allow_html=True)
    st.write("")

    _, col_centro, _ = st.columns([1, 2, 1])

    with col_centro:
        with st.container(border=True):
            st.markdown("### ⬆️ Subir EECC")
            st.markdown("El RPA no pudo extraer el archivo del banco. Súbelo manualmente para reanudar la conciliación.")
            st.write("")
            if st.button("Ir a bandeja →", key="btn_eecc", type="primary", use_container_width=True):
                st.session_state.modulo = "eecc"
                st.rerun()

        st.write("")

        with st.container(border=True):
            st.markdown("### 📄 Ejecutar Conciliación")
            st.markdown("Concilia manualmente archivos cuando el sistema automatizado no está disponible.")
            st.write("")
            if st.button("Ir a conciliación →", key="btn_conciliacion", use_container_width=True):
                st.session_state.modulo = "conciliacion"
                st.rerun()
