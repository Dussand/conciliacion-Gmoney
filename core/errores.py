"""Catálogo de errores de la contingencia: qué pasó, qué hacer y si se escala.

Los textos se editan aquí sin tocar la lógica.
- cuenta_intento: suma al contador de intentos del bloque (a los 3 se ofrece marcar banco no disponible).
- escala: es un fallo del sistema. BANCO_SIN_CONFIGURAR se notifica automáticamente;
  ORQUESTADOR y BASE_DATOS se escalan con el botón «Escalar» (ui/escalamiento.py).
"""
import streamlit as st

RESPONSABLE = "Dussand Hurtado"
MAX_INTENTOS = 3

ERRORES = {
    "ARCHIVO_NO_VALIDO": {
        "titulo": "El archivo no se pudo leer o no es el estado de cuenta esperado",
        "que_hacer": [
            "Vuelve a descargar el estado de cuenta desde la plataforma del banco.",
            "Súbelo tal como se descarga: no lo abras ni lo guardes en Excel antes.",
            "Verifica que sea el estado de cuenta de la cuenta y del banco del bloque.",
        ],
        "cuenta_intento": True,
        "escala": False,
    },
    "SIN_ABONOS": {
        "titulo": "El estado de cuenta no tiene abonos",
        "que_hacer": [
            "Verifica que descargaste la cuenta correcta.",
            "Verifica que la fecha del reporte sea la del bloque.",
        ],
        "cuenta_intento": True,
        "escala": False,
    },
    "FUERA_DE_BLOQUE": {
        "titulo": "Ninguna operación del archivo corresponde al bloque",
        "que_hacer": [
            "Descarga el estado de cuenta del día y la hora del bloque (se muestran arriba).",
            "Si el banco aún no muestra las operaciones de ese horario, espera unos minutos y vuelve a descargarlo.",
        ],
        "cuenta_intento": True,
        "escala": False,
    },
    "DATOS_INVALIDOS": {
        "titulo": "Hay registros con datos inválidos",
        "que_hacer": [
            "Revisa en la tabla la fila y el campo de cada error.",
            "Monto: debe ser numérico y mayor a 0. Moneda: 3 letras (PEN, USD). Psptin: solo dígitos.",
            "Vuelve a descargar el archivo; si los datos vienen así desde el banco, el archivo está incompleto.",
        ],
        "cuenta_intento": True,
        "escala": False,
    },
    "BANCO_SIN_CONFIGURAR": {
        "titulo": "Este banco todavía no está configurado para carga manual",
        "que_hacer": ["No es un problema del archivo: la herramienta no tiene la configuración de este banco."],
        "cuenta_intento": False,
        "escala": True,
    },
    "ORQUESTADOR": {
        "titulo": "No se pudo enviar al orquestador",
        "que_hacer": ["Reintenta una vez. Si vuelve a fallar, es un problema del sistema: usa «Escalar»."],
        "cuenta_intento": False,
        "escala": True,
    },
    "BASE_DATOS": {
        "titulo": "No se pudo conectar con la base de datos",
        "que_hacer": ["Refresca la bandeja. Si vuelve a fallar, es un problema del sistema: usa «Escalar»."],
        "cuenta_intento": False,
        "escala": True,
    },
}


def mostrar_error(codigo, detalle=None, intento=None, notificado=None):
    """Muestra el error con sus pasos.
    intento: número de intento del bloque (para errores que cuentan intento).
    notificado: True/False si se intentó escalar automáticamente; None si todavía no se escala.
    """
    err = ERRORES[codigo]
    sufijo = f" · Intento {intento} de {MAX_INTENTOS}" if intento else ""
    pasos = "\n".join(f"- {p}" for p in err["que_hacer"])
    texto = f"**{err['titulo']}**{sufijo}\n\n**Qué hacer:**\n{pasos}"
    if err["escala"] and notificado is not None:
        if notificado:
            texto += f"\n\n📨 Se notificó automáticamente a **{RESPONSABLE}**."
        else:
            texto += f"\n\n⚠️ No se pudo notificar automáticamente: avisa a **{RESPONSABLE}**."
    st.error(texto, icon="❌")
    if detalle:
        with st.expander("Detalle técnico"):
            st.code(str(detalle), language=None)

def registrar_intento(ciclo_id, codigo):
    """Suma un intento fallido al bloque y devuelve el número de intento."""
    intentos = st.session_state.setdefault("intentos_eecc", {})
    intentos.setdefault(ciclo_id, []).append(codigo)
    return len(intentos[ciclo_id])

def intentos_de(ciclo_id):
    return st.session_state.get("intentos_eecc", {}).get(ciclo_id, [])
