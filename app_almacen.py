import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import os
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Inventario Pro", page_icon="🏭", layout="wide")

# --- 🔄 EL TRUCO DE MAGIA (RECUPERADO) ---
# Esto es vital para que funcione en la nube.
# Reconstruye el archivo credenciales.json usando la info guardada en Secrets.
if not os.path.exists("credenciales.json"):
    # Buscamos si existe el secreto llamado "contenido_archivo" (Plan C)
    if "contenido_archivo" in st.secrets:
        with open("credenciales.json", "w") as f:
            f.write(st.secrets["contenido_archivo"])
    # Por si acaso lo llamaste google_json en algún intento anterior
    elif "google_json" in st.secrets:
         with open("credenciales.json", "w") as f:
            f.write(st.secrets["google_json"])

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # Ahora que aseguramos que el archivo existe, nos conectamos directo
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        st.info("Verifica que en 'Secrets' tengas pegado el contenido del JSON bajo el nombre 'contenido_archivo'.")
        return None

# --- FUNCIONES DE GESTIÓN ---
def obtener_hoja(client, nombre_hoja):
    """Busca una pestaña por nombre, si no existe, intenta crearla"""
    try:
        main_doc = client.open("Inventario_Ricardo")
        try:
            sheet = main_doc.worksheet(nombre_hoja)
            return sheet
        except gspread.WorksheetNotFound:
            # Si no existe la pestaña, la creamos
            st.toast(f"⚠️ Creando hoja nueva para: {nombre_hoja}...")
            sheet = main_doc.add_worksheet(title=nombre_hoja, rows=100, cols=20)
            encabezados = ["Date", "Lot#", "Initial", "Product", "Balance", 
                           "GAN_1 (COGA 53)", "GAN_2 (COGA 53)", "GAN_3 (COGA 53)", "GAN_4 (COGA 53)"]
            sheet.append_row(encabezados)
            return sheet
    except Exception as e:
        st.error(f"Error abriendo documento principal: {e}")
        return None

def guardar_cambios(sheet, df):
    """Sobreescribe toda la hoja con los datos nuevos del editor"""
    try:
        sheet.clear()
        # Convertimos encabezados y datos a lista
        datos_lista = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name=None, values=datos_lista)
        st.success("✅ ¡Cambios guardados en la Nube exitosamente!")
    except Exception as e:
        st.error(f"Error guardando: {e}")

# --- INTERFAZ PRINCIPAL ---
st.title("🏭 Gestión de Inventario Multi-Cliente")

client = conectar_google_sheets()

if client:
    # 1. BARRA LATERAL: SELECCIÓN DE CLIENTE
    st.sidebar.header("📁 Clientes")
    
    clientes_opciones = ["General", "Coprisa", "Peninsula", "Mamamia", "Veggie", "Full Fresh", "Ben Bud"]
    
    nuevo_cliente = st.sidebar.text_input("➕ Crear Nuevo Cliente:")
    if nuevo_cliente:
        if nuevo_cliente not in clientes_opciones:
            clientes_opciones.append(nuevo_cliente)
            # Seleccionamos automáticamente el nuevo
            index_nuevo = len(clientes_opciones) - 1
        else:
            index_nuevo = clientes_opciones.index(nuevo_cliente)
    else:
        index_nuevo = 0
    
    cliente_seleccionado = st.sidebar.selectbox(
        "Selecciona la hoja de trabajo:", 
        clientes_opciones, 
        index=index_nuevo if nuevo_cliente else 0
    )
    
    # 2. CARGAR DATOS
    sheet = obtener_hoja(client, cliente_seleccionado)
    
    if sheet:
        data = sheet.get_all_records()
        
        # Estructura base
        columnas_base = ["Date", "Lot#", "Initial", "Product", "Balance", 
                         "GAN_1 (COGA 53)", "GAN_2 (COGA 53)", "GAN_3 (COGA 53)", "GAN_4 (COGA 53)"]
        
        if not data:
            df = pd.DataFrame(columns=columnas_base)
        else:
            df = pd.DataFrame(data)
            # Asegurar que todas las columnas base existan, si no, las crea vacías
            for col in columnas_base:
                if col not in df.columns:
                    df[col] = ""

        # Ordenar columnas visualmente
        df = df[columnas_base]

        # Convertir a números para sumar
        cols_numericas = ["Initial", "Balance"]
        for col in cols_numericas:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 3. EDITOR TIPO EXCEL
        st.subheader(f"📋 Planilla: {cliente_seleccionado}")
        
        # Editor
        df_editado = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{cliente_seleccionado}"
        )

        # 4. CÁLCULOS
        st.divider()
        c1, c2 = st.columns(2)
        total_ini = df_editado["Initial"].sum()
        total_bal = df_editado["Balance"].sum()
        
        c1.metric("Total Initial", f"{total_ini:,.2f}")
        c2.metric("Total Balance", f"{total_bal:,.2f}")

        # 5. BOTÓN GUARDAR
        st.info("⚠️ Recuerda: Los cambios no se guardan en Google hasta que presiones el botón rojo.")
        if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary"):
            guardar_cambios(sheet, df_editado)

        # 6. BACKUP
        st.sidebar.divider()
        fecha = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        csv = df_editado.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button(
            "📥 Descargar Backup CSV",
            csv,
            f"{cliente_seleccionado}_{fecha}.csv",
            "text/csv"
        )