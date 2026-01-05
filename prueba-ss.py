"""
Aplicación Streamlit - Conciliación con Captura Automática
Sistema de prueba para generación de evidencias
Captura inteligente de la ventana del navegador
"""

import streamlit as st
import pyautogui
from datetime import datetime
from pathlib import Path
import time
from PIL import ImageGrab

# Configuración de la página
st.set_page_config(
    page_title="Conciliación G-Money",
    page_icon="💰",
    layout="wide"
)

# Ruta donde se guardarán las capturas
RUTA_CAPTURAS = r"C:\Users\Dussand\OneDrive\Desktop\BPA\KASHIO\Business Process Analyst\Payins\Conciliacion-Gmoney\conciliacion-Gmoney"


def capturar_ventana_streamlit(tipo_resultado="general"):
    """
    Captura inteligente de la ventana del navegador donde está Streamlit
    Funciona con 1 o múltiples monitores
    """
    try:
        # Crear directorio si no existe
        Path(RUTA_CAPTURAS).mkdir(parents=True, exist_ok=True)
        
        # Crear nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"conciliacion_{tipo_resultado}_{timestamp}.png"
        ruta_completa = Path(RUTA_CAPTURAS) / nombre_archivo
        
        # Pequeña pausa para asegurar que la UI esté renderizada
        time.sleep(0.5)
        
        captura = None
        metodo_usado = ""
        
        # MÉTODO 1: Intentar capturar ventana del navegador (más preciso)
        try:
            import pygetwindow as gw
            
            # Buscar ventanas del navegador con términos relacionados a Streamlit
            terminos_busqueda = [
                "localhost:8501",
                "localhost",
                "Conciliación G-Money",
                "Streamlit",
                "Chrome",
                "Edge", 
                "Firefox",
                "Brave"
            ]
            
            ventana_encontrada = None
            
            for termino in terminos_busqueda:
                ventanas = gw.getWindowsWithTitle(termino)
                if ventanas:
                    ventana_encontrada = ventanas[0]
                    metodo_usado = f"Ventana: {termino}"
                    break
            
            if ventana_encontrada:
                # Activar y enfocar la ventana
                try:
                    ventana_encontrada.activate()
                except:
                    pass  # Si no se puede activar, continuar igual
                
                time.sleep(0.3)
                
                # Capturar la región exacta de la ventana
                captura = ImageGrab.grab(bbox=(
                    ventana_encontrada.left,
                    ventana_encontrada.top,
                    ventana_encontrada.right,
                    ventana_encontrada.bottom
                ))
                
                captura.save(ruta_completa)
                return str(ruta_completa), metodo_usado
        
        except ImportError:
            # pygetwindow no está instalado, pasar al siguiente método
            pass
        except Exception as e:
            # Error al intentar capturar ventana, pasar al siguiente método
            pass
        
        # MÉTODO 2: Capturar toda la pantalla (fallback)
        if captura is None:
            try:
                # Intentar capturar todos los monitores
                captura = ImageGrab.grab(all_screens=True)
                metodo_usado = "Pantalla completa (todos los monitores)"
            except:
                # Fallback final: captura con pyautogui
                captura = pyautogui.screenshot()
                metodo_usado = "Pantalla completa (monitor principal)"
            
            captura.save(ruta_completa)
            return str(ruta_completa), metodo_usado
        
        return str(ruta_completa), metodo_usado
    
    except Exception as e:
        st.error(f"Error al capturar pantalla: {str(e)}")
        return None, None


def enviar_correo_conciliacion(tipo_resultado, ruta_captura):
    """
    Función placeholder para envío de correo
    En tu implementación real, aquí irá el código de envío de email
    """
    # Aquí iría tu lógica real de envío de correo
    # Por ahora solo simulamos
    return True


# ==================== INTERFAZ PRINCIPAL ====================

st.title("💰 Sistema de Conciliación G-Money")
st.markdown("---")

# Información de la sesión
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("📅 Fecha", datetime.now().strftime("%Y-%m-%d"))

with col2:
    st.metric("⏰ Hora", datetime.now().strftime("%H:%M:%S"))

with col3:
    st.metric("👤 Usuario", "Dussand")

st.markdown("---")

# ==================== SIMULACIÓN DE RESULTADOS ====================

st.header("🔍 Resultado de Conciliación")

# Selector de tipo de resultado para pruebas
tipo_prueba = st.radio(
    "Selecciona el tipo de resultado a simular:",
    ["Conciliación Exitosa", "Discrepancias Encontradas", "Error en Proceso"],
    horizontal=True
)

st.markdown("---")

# ==================== MOSTRAR RESULTADO SEGÚN TIPO ====================

if tipo_prueba == "Conciliación Exitosa":
    st.success("✅ **CONCILIACIÓN EXITOSA**")
    st.markdown("""
    ### Detalles de la Conciliación
    - **Total de registros procesados:** 150
    - **Registros coincidentes:** 150
    - **Discrepancias:** 0
    - **Monto total conciliado:** S/ 45,230.50
    - **Estado:** ✅ Aprobado
    """)
    
    # Datos de ejemplo
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Registros Procesados", "150", delta="0")
    with col_b:
        st.metric("Coincidencias", "100%", delta="0%")
    with col_c:
        st.metric("Monto Total", "S/ 45,230.50", delta="S/ 0.00")
    
    tipo_captura = "exitosa"

elif tipo_prueba == "Discrepancias Encontradas":
    st.warning("⚠️ **DISCREPANCIAS ENCONTRADAS**")
    st.markdown("""
    ### Detalles de la Conciliación
    - **Total de registros procesados:** 150
    - **Registros coincidentes:** 145
    - **Discrepancias:** 5
    - **Monto total conciliado:** S/ 44,150.75
    - **Monto en discrepancia:** S/ 1,079.75
    - **Estado:** ⚠️ Requiere Revisión
    """)
    
    # Tabla de discrepancias
    st.markdown("#### 📋 Registros con Discrepancias")
    st.markdown("""
    | ID Transacción | Monto Esperado | Monto Encontrado | Diferencia |
    |----------------|----------------|------------------|------------|
    | TRX-001234     | S/ 250.00      | S/ 230.00        | -S/ 20.00  |
    | TRX-001456     | S/ 180.50      | S/ 200.50        | +S/ 20.00  |
    | TRX-002789     | S/ 320.25      | S/ 0.00          | -S/ 320.25 |
    | TRX-003012     | S/ 450.00      | S/ 450.00        | S/ 0.00    |
    | TRX-003334     | S/ 89.50       | S/ 109.50        | +S/ 20.00  |
    """)
    
    # Métricas
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Registros Procesados", "150", delta="-5")
    with col_b:
        st.metric("Coincidencias", "96.67%", delta="-3.33%")
    with col_c:
        st.metric("Monto Total", "S/ 44,150.75", delta="-S/ 1,079.75")
    
    tipo_captura = "discrepancia"

else:  # Error en Proceso
    st.error("❌ **ERROR EN PROCESO DE CONCILIACIÓN**")
    st.markdown("""
    ### Detalles del Error
    - **Código de error:** ERR-500
    - **Descripción:** Tiempo de espera agotado al conectar con el servidor
    - **Registros procesados antes del error:** 75 de 150
    - **Estado:** ❌ Fallido
    - **Acción requerida:** Reintentar proceso
    """)
    
    # Información adicional
    with st.expander("📄 Ver detalles técnicos del error"):
        st.code("""
ConnectionTimeout: Unable to connect to database
Server: gmoney-prod.database.com
Port: 5432
Timeout: 30s
Last successful connection: 2025-01-05 14:30:15
        """)
    
    tipo_captura = "error"

st.markdown("---")

# ==================== BOTÓN DE GENERAR CORREO ====================

st.header("📧 Generar Correo de Evidencia")

col_btn1, col_btn2 = st.columns([1, 3])

with col_btn1:
    if st.button("📧 Generar y Enviar Correo", type="primary", use_container_width=True):
        with st.spinner("Capturando pantalla..."):
            # Capturar la ventana de Streamlit
            ruta_captura, metodo_usado = capturar_ventana_streamlit(tipo_captura)
            
            if ruta_captura:
                st.success(f"✅ Captura guardada exitosamente")
                st.info(f"📁 **Ubicación:** `{Path(ruta_captura).name}`")
                
                # Mostrar método usado (útil para debugging)
                if metodo_usado:
                    with st.expander("🔍 Información técnica"):
                        st.text(f"Método de captura: {metodo_usado}")
                        st.text(f"Ruta completa: {ruta_captura}")
                
                # Simular envío de correo
                with st.spinner("Enviando correo..."):
                    time.sleep(1)  # Simular envío
                    exito = enviar_correo_conciliacion(tipo_captura, ruta_captura)
                    
                    if exito:
                        st.success("✅ Correo enviado exitosamente con la evidencia adjunta")
                        
                        # Mostrar resumen
                        st.markdown("""
                        ### 📨 Resumen del Correo Enviado
                        - **Para:** equipo.finanzas@kashio.com
                        - **Asunto:** Resultado de Conciliación G-Money
                        - **Adjunto:** Captura de pantalla (PNG)
                        - **Estado:** Enviado
                        """)
            else:
                st.error("❌ No se pudo capturar la pantalla")

with col_btn2:
    st.info("💡 **Tip:** La captura se tomará automáticamente de esta ventana del navegador")

# ==================== INFORMACIÓN ADICIONAL ====================

st.markdown("---")

with st.expander("ℹ️ Información sobre capturas automáticas"):
    st.markdown(f"""
    ### 📸 Sistema de Captura Inteligente
    
    - **Ubicación de guardado:** 
    ```
    {RUTA_CAPTURAS}
    ```
    
    - **Formato de nombre:** 
    ```
    conciliacion_[tipo]_[fecha]_[hora].png
    ```
    
    - **Tipos de captura:**
      - `exitosa`: Cuando la conciliación es 100% exitosa
      - `discrepancia`: Cuando hay diferencias encontradas
      - `error`: Cuando el proceso falla
    
    - **Cómo funciona:**
      1. Busca automáticamente la ventana del navegador con Streamlit
      2. Captura solo esa ventana (no toda la pantalla)
      3. Funciona con 1 o múltiples monitores
      4. Si no encuentra la ventana, captura toda la pantalla como respaldo
    
    - **Mejora opcional:**
    ```bash
    pip install pygetwindow
    ```
    Esto permite capturar con mayor precisión solo la ventana del navegador.
    """)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 12px;'>
        <p>🔒 Sistema de Conciliación G-Money v2.1 | Business Process Analyst | © 2025 Kashio</p>
    </div>
    """,
    unsafe_allow_html=True
)