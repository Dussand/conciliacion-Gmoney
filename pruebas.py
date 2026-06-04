import streamlit as st
import pandas as pd
import requests
from datetime import datetime

WEBHOOK_URL = "https://infraestructura.app.n8n.cloud/webhook-test/rocketbot-callback"

def enmascarar_cuenta(cci):
    if cci and len(str(cci)) >= 4:
        return f"****{str(cci)[-4:]}"
    return "****0000"

st.title("Carga Manual EECC — GMONEY")
st.caption("Contingencia: ingesta manual cuando el RPA falla")

archivo = st.file_uploader("Selecciona el archivo Excel de GMONEY", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df_com = df[df['status'] == 'COM'].copy()
    
    st.info(f"Registros encontrados: {len(df)} | Registros COM: {len(df_com)}")
    st.dataframe(df_com[['instruction_id', 'movement_day', 'amount', 'currency', 'entity']].head(10))
    
    if st.button("Enviar al Motor de Conciliación", type="primary"):
        registros = []
        for _, row in df_com.iterrows():
            registros.append({
                "banco_codigo":    "GMONEY",
                "cuenta_origen":   enmascarar_cuenta(row.get('target_cci')),
                "operacion_id":    str(row['instruction_id']),
                "pais":            "PE",
                "fecha_operacion": str(row['movement_day']),
                "monto":           float(row['amount']),
                "moneda":          str(row['currency']),
                "psptin":          str(row['instruction_id']),
                "origen_ingesta":  "MANUAL"
            })
        
        payload = {
            "banco_codigo":    "GMONEY",
            "status":          "success",
            "ventana_horaria": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "registros":       registros
        }
        
        with st.spinner("Enviando registros..."):
            response = requests.post(WEBHOOK_URL, json=payload)
        
        if response.status_code == 200:
            st.success(f"✅ {len(registros)} registros enviados correctamente")
        else:
            st.error(f"❌ Error {response.status_code}: {response.text}")