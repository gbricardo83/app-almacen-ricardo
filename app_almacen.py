import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime

# --- CONFIGURACIÓN ---
NOMBRE_HOJA_GOOGLE = "Inventario_Ricardo"  # Tiene que ser exacto al de Drive
ARCHIVO_CREDENCIALES = "credenciales.json" # El archivo que descargaste

st.set_page_config(page_title="Almacén en la Nube", page_icon="☁️")

# --- CONEXIÓN CON GOOGLE SHEETS ---
# --- CONEXIÓN HÍBRIDA (NUBE Y LOCAL) ---
def conectar_google_sheets():
    """Conecta con Google Sheets usando archivo local O secretos de la nube"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # 1. Intentamos buscar en los SECRETOS de la Nube (Streamlit Cloud)
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # 2. Si no hay secretos, buscamos el archivo LOCAL en tu Mac
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(ARCHIVO_CREDENCIALES, scope)
            
        client = gspread.authorize(creds)
        sheet = client.open(NOMBRE_HOJA_GOOGLE).sheet1
        return sheet
    except Exception as e:
        st.error(f"❌ Error conectando a Google: {e}")
        return None

def cargar_datos_nube(sheet):
    """Lee todos los datos de la nube"""
    if sheet:
        data = sheet.get_all_records()
        # Si la hoja está vacía, devuelve diccionario vacío
        if not data:
            return {}
        # Convertimos la lista de Google a nuestro formato {Producto: Cantidad}
        # Asumimos que las columnas se llaman "Producto" y "Cantidad"
        inventario = {fila['Producto']: fila['Cantidad'] for fila in data}
        return inventario
    return {}

def guardar_cambio_nube(sheet, producto, nueva_cantidad, accion):
    """
    Esta función es más inteligente: Busca si el producto ya existe.
    Si existe, actualiza la celda. Si no, crea una fila nueva.
    """
    if not sheet: return

    # Buscamos si el producto ya está en la hoja (Columna 1 = A)
    celda = sheet.find(producto)
    
    if celda:
        # Si existe, actualizamos la celda de al lado (Columna 2 = B)
        sheet.update_cell(celda.row, 2, nueva_cantidad)
    else:
        # Si no existe, agregamos una fila nueva al final
        sheet.append_row([producto, nueva_cantidad])

# --- INICIO DE SESIÓN ---
# 1. Conectamos al arrancar
if 'sheet_conector' not in st.session_state:
    st.session_state['sheet_conector'] = conectar_google_sheets()

# 2. Cargamos inventario inicial
if 'inventario' not in st.session_state:
    sheet = st.session_state['sheet_conector']
    st.session_state['inventario'] = cargar_datos_nube(sheet)

if 'historial' not in st.session_state:
    st.session_state['historial'] = []

def registrar_log(mensaje):
    hora = datetime.datetime.now().strftime("%H:%M")
    st.session_state['historial'].append(f"{hora} - {mensaje}")

# --- INTERFAZ ---
st.title("☁️ Almacén Conectado a Google Drive")

menu = st.sidebar.selectbox("Menú", ["📥 Entrada", "📤 Salida", "📋 Ver Hoja Drive", "🔄 Recargar Datos"])

# --- ENTRADA ---
if menu == "📥 Entrada":
    st.header("Recibir Mercancía")
    col1, col2 = st.columns(2)
    with col1:
        prod = st.text_input("Producto").upper()
    with col2:
        cant = st.number_input("Cantidad", min_value=1)
        
    if st.button("Guardar en la Nube"):
        if prod:
            # Lógica local
            inv = st.session_state['inventario']
            if prod in inv:
                inv[prod] += cant
            else:
                inv[prod] = cant
            
            # GUARDAR EN GOOGLE
            sheet = st.session_state['sheet_conector']
            guardar_cambio_nube(sheet, prod, inv[prod], "ENTRADA")
            
            registrar_log(f"ENTRADA: +{cant} de {prod}")
            st.success(f"✅ ¡Guardado en Google Drive! {prod}: {inv[prod]}")
        else:
            st.error("Escribe un nombre.")

# --- SALIDA ---
elif menu == "📤 Salida":
    st.header("Despachar Pedido")
    inv = st.session_state['inventario']
    
    if inv:
        prod = st.selectbox("Selecciona producto", options=list(inv.keys()))
        stock_actual = inv[prod]
        st.info(f"Stock en Drive: {stock_actual}")
        
        cant = st.number_input("Cantidad a sacar", min_value=1, max_value=stock_actual)
        
        if st.button("Confirmar Salida"):
            inv[prod] -= cant
            
            # GUARDAR EN GOOGLE
            sheet = st.session_state['sheet_conector']
            guardar_cambio_nube(sheet, prod, inv[prod], "SALIDA")
            
            registrar_log(f"SALIDA: -{cant} de {prod}")
            st.success("✅ Drive actualizado.")
    else:
        st.warning("No hay datos en la nube.")

# --- VER DATOS ---
elif menu == "📋 Ver Hoja Drive":
    st.header("Datos en Tiempo Real")
    if st.session_state['inventario']:
        df = pd.DataFrame(list(st.session_state['inventario'].items()), columns=["Producto", "Cantidad"])
        st.dataframe(df, use_container_width=True)
        st.success("Estos datos vienen directo de Google Sheets.")
    else:
        st.warning("La hoja está vacía.")

# --- RECARGAR ---
elif menu == "🔄 Recargar Datos":
    st.header("Sincronización Manual")
    if st.button("Forzar descarga de Google"):
        sheet = st.session_state['sheet_conector']
        st.session_state['inventario'] = cargar_datos_nube(sheet)
        st.success("Datos actualizados desde la nube.")