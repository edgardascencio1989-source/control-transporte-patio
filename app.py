import streamlit as st
import pandas as pd
import datetime
import pytz
import os
import time
import json

# =====================================================================
# CONFIGURACIÓN GENERAL
# =====================================================================
st.set_page_config(page_title="Control Transportes", layout="wide", page_icon="🚚")
zona_local = pytz.timezone('America/Santiago')

SPREADSHEET_ID = "19K8Mn8EGn06i1RXhTkOXrCGvVm8nriWOEbV6TT-uYEg"
BACKUP_ACTIVAS = "backup_patentes_activas.csv"
BACKUP_HISTORIAL = "backup_historial_final.csv"

# =====================================================================
# MOTOR DE CONEXIÓN CON GOOGLE SHEETS
# =====================================================================
@st.cache_resource(show_spinner=False)
def obtener_cliente_gspread():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        if "json_data" not in st.secrets: return None
        creds_dict = json.loads(st.secrets["json_data"])
        if "private_key" in creds_dict: creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except: return None

def conectar_google_sheets(pestaña_nombre):
    client = obtener_cliente_gspread()
    if not client:
        st.error("❌ ERROR: Problemas con las credenciales Secrets.")
        st.stop()
        return None
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return spreadsheet.worksheet(pestaña_nombre)
    except Exception as e:
        st.error(f"❌ ERROR buscando pestaña '{pestaña_nombre}': {str(e)}")
        st.stop()
        return None

# =====================================================================
# FUNCIONES DE APOYO (LIMPIEZA Y FORMATO)
# =====================================================================
def formatear_rut(rut_input):
    r = str(rut_input).upper().replace(".", "").replace("-", "").replace(" ", "").strip()
    return r[:-1] + "-" + r[-1] if len(r) > 1 else r

def parse_fecha(fecha_str):
    if pd.isna(fecha_str) or not fecha_str: return None
    try: return datetime.datetime.strptime(str(fecha_str), '%Y-%m-%d %H:%M:%S')
    except: return None

def formatear_a_cronometro(minutos_decimales):
    if pd.isna(minutos_decimales) or minutos_decimales < 0: return "00:00:00"
    total_segundos = int(round(minutos_decimales * 60))
    return f"{total_segundos // 3600:02d}:{(total_segundos % 3600) // 60:02d}:{total_segundos % 60:02d}"

def cronometro_a_minutos(texto):
    if pd.isna(texto) or texto in ["N/A", ""]: return 0.0
    try:
        p = str(texto).split(":")
        return int(p[0]) * 60 + int(p[1]) + int(p[2]) / 60.0
    except: return 0.0

# =====================================================================
# LÓGICA DE DATOS
# =====================================================================
def cargar_datos_cloud(pestaña_nombre):
    sheet = conectar_google_sheets(pestaña_nombre)
    if sheet:
        try: return pd.DataFrame(sheet.get_all_records())
        except: pass
    return pd.DataFrame()

def guardar_datos_cloud(df, pestaña_nombre):
    sheet = conectar_google_sheets(pestaña_nombre)
    if sheet:
        sheet.clear()
        df_enviar = df.fillna("").astype(str)
        sheet.update([df_enviar.columns.values.tolist()] + df_enviar.values.tolist())

def agregar_fila_historial_rapido(nueva_fila_dict):
    sheet = conectar_google_sheets("historial_final")
    if sheet:
        sheet.append_row([str(nueva_fila_dict.get(c, "")) for c in [
            "Fecha", "Semana", "Mes", "Empresa", "Patente", "Chofer", "RUT", "Ruta Auditada", 
            "Ingreso Inversa", "Salida Inversa", "Ingreso Despacho", "Salida Despacho", 
            "T. Retorno (Descarga)", "T. Despacho (Carga)", "Minutos_Carga_Raw", "Tipo de Cierre", 
            "Chofer 2", "RUT Chofer 2"
        ]])

# =====================================================================
# INICIALIZACIÓN
# =====================================================================
if "df_activas" not in st.session_state:
    st.session_state.df_activas = cargar_datos_cloud("patentes_activas")
    st.session_state.df_historial = cargar_datos_cloud("historial_final")

ahora_actual = datetime.datetime.now(zona_local)

# =====================================================================
# PESTAÑAS Y ENRUTAMIENTO
# =====================================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 1. Ingreso Logística Inversa", 
    "📤 2. Salida de Inversa", 
    "📦 3. Ingreso a despacho", 
    "🚪 4. Salida Despacho", 
    "📊 5. Monitoreo y KPIS"
])

# =====================================================================
# PESTAÑA 1: INGRESO INVERSA
# =====================================================================
with tab1:
    st.header("📥 Registro de Ingreso a Logística Inversa")
    with st.form("form_ingreso_inversa"):
        patente = st.text_input("🚚 Patente", max_chars=6).upper().strip()
        empresa = st.text_input("🏢 Empresa").upper().strip()
        chofer = st.text_input("👤 Chofer").upper().strip()
        rut = st.text_input("🆔 RUT Chofer").strip()
        if st.form_submit_button("💾 Registrar Llegada"):
            rut_l = formatear_rut(rut)
            if not patente or not empresa or not chofer or not rut_l: st.error("Faltan datos")
            elif patente in st.session_state.df_activas["Patente"].values: st.warning("Ya activa")
            else:
                nuevo = pd.DataFrame([{"Patente": patente, "Empresa": empresa, "Chofer": chofer, "RUT": rut_l, "H1_Llegada_Inversa": ahora_actual.strftime('%Y-%m-%d %H:%M:%S'), "Estado": "En Logística Inversa"}])
                st.session_
