import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Inventario Pro", page_icon="🏭", layout="wide")

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "google_json" in st.secrets:
            import json
            creds_dict = json.loads(st.secrets["google_json"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

# --- FUNCIONES DE GESTIÓN ---
def obtener_hoja(client, nombre_hoja):
    """Busca una pestaña por nombre, si no existe, intenta crearla"""
    try:
        # Intenta abrir la hoja del cliente
        sheet = client.open("Inventario_Ricardo").worksheet(nombre_hoja)
        return sheet
    except gspread.WorksheetNotFound:
        # Si no existe, la creamos con los encabezados por defecto
        st.warning(f"⚠️ La hoja '{nombre_hoja}' no existía. Creándola ahora...")
        main_doc = client.open("Inventario_Ricardo")
        sheet = main_doc.add_worksheet(title=nombre_hoja, rows=100, cols=20)
        # Encabezados obligatorios
        encabezados = ["Date", "Lot#", "Initial", "Product", "Balance", 
                       "GAN_1 (COGA 53)", "GAN_2 (COGA 53)", "GAN_3 (COGA 53)", "GAN_4 (COGA 53)"]
        sheet.append_row(encabezados)
        return sheet

def guardar_cambios(sheet, df):
    """Sobreescribe toda la hoja con los datos nuevos del editor"""
    try:
        # Limpiamos la hoja vieja
        sheet.clear()
        # Ponemos los datos nuevos (convertimos a lista)
        # Primero los encabezados
        sheet.append_row(df.columns.tolist())
        # Luego los datos
        datos = df.astype(str).values.tolist()
        sheet.append_rows(datos)
        st.toast("✅ ¡Cambios guardados en la Nube!", icon="☁️")
    except Exception as e:
        st.error(f"Error guardando: {e}")

# --- INTERFAZ PRINCIPAL ---
st.title("🏭 Gestión de Inventario Multi-Cliente")

client = conectar_google_sheets()

if client:
    # 1. BARRA LATERAL: SELECCIÓN DE CLIENTE
    st.sidebar.header("📁 Clientes")
    
    # Lista de clientes predefinidos
    clientes_opciones = ["General", "Coprisa", "Peninsula", "Mamamia", "Veggie", "Full Fresh", "Ben Bud"]
    
    # Opción para crear uno nuevo manual
    nuevo_cliente = st.sidebar.text_input("¿Nuevo Cliente? Escribe nombre:")
    if nuevo_cliente and nuevo_cliente not in clientes_opciones:
        clientes_opciones.append(nuevo_cliente)
    
    cliente_seleccionado = st.sidebar.selectbox("Selecciona la hoja de trabajo:", clientes_opciones)
    
    # 2. CARGAR DATOS
    sheet = obtener_hoja(client, cliente_seleccionado)
    data = sheet.get_all_records()
    
    # Estructura base si está vacía
    if not data:
        df = pd.DataFrame(columns=["Date", "Lot#", "Initial", "Product", "Balance", 
                                   "GAN_1 (COGA 53)", "GAN_2 (COGA 53)", "GAN_3 (COGA 53)", "GAN_4 (COGA 53)"])
    else:
        df = pd.DataFrame(data)

    # Aseguramos que las columnas numéricas sean números para poder sumar
    cols_numericas = ["Initial", "Balance"]
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 3. EDITOR TIPO EXCEL (Aquí insertas/borras filas)
    st.subheader(f"📋 Planilla: {cliente_seleccionado}")
    st.info("💡 Instrucciones: Haz clic en una celda para editar. Usa la tecla '+' abajo para agregar filas. Selecciona filas y presiona 'Delete' para borrar.")

    # El data_editor es el corazón de la nueva app
    df_editado = st.data_editor(
        df,
        num_rows="dynamic", # Permite añadir/quitar filas
        use_container_width=True,
        key=f"editor_{cliente_seleccionado}" # Clave única por cliente
    )

    # 4. CÁLCULOS AUTOMÁTICOS (Totales)
    st.divider()
    col_tot1, col_tot2, col_tot3 = st.columns(3)
    
    total_initial = df_editado["Initial"].sum() if "Initial" in df_editado.columns else 0
    total_balance = df_editado["Balance"].sum() if "Balance" in df_editado.columns else 0
    
    col_tot1.metric("Total Initial", f"{total_initial:,.2f}")
    col_tot2.metric("Total Balance", f"{total_balance:,.2f}")
    
    # 5. BOTÓN DE GUARDADO MANUAL
    # Streamlit no guarda automático en Google Sheets para no saturar la API
    if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary"):
        guardar_cambios(sheet, df_editado)

    # 6. BACKUP Y EXPORTACIÓN
    st.sidebar.divider()
    st.sidebar.subheader("📦 Descargas / Backup")
    
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    nombre_archivo = f"{cliente_seleccionado}_{fecha_hoy}.csv"
    
    # Convertir a CSV para descargar
    csv = df_editado.to_csv(index=False).encode('utf-8')
    
    st.sidebar.download_button(
        label=f"📥 Descargar Respaldo ({fecha_hoy})",
        data=csv,
        file_name=nombre_archivo,
        mime='text/csv',
        help="Guarda una copia exacta de esta tabla en tu computadora"
    )