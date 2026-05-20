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
# 🚀 OPTIMIZACIÓN 1: CACHÉ DE CONEXIÓN A GOOGLE
# =====================================================================
@st.cache_resource(show_spinner=False)
def obtener_cliente_gspread():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        if "json_data" not in st.secrets:
            return None
        creds_dict = json.loads(st.secrets["json_data"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except:
        return None

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
        st.error(f"❌ ERROR DE PESTAÑA: {str(e)}")
        st.stop()
        return None

# =====================================================================
# 🪪 OPTIMIZACIÓN 2: LIMPIEZA DE RUT Y HORAS
# =====================================================================
def formatear_rut(rut_input):
    r = str(rut_input).upper().replace(".", "").replace("-", "").replace(" ", "").strip()
    if len(r) > 1:
        return r[:-1] + "-" + r[-1]
    return r

def parse_fecha(fecha_str):
    if pd.isna(fecha_str) or not fecha_str: 
        return None
    try:
        return datetime.datetime.strptime(str(fecha_str), '%Y-%m-%d %H:%M:%S')
    except:
        try: 
            return datetime.datetime.fromisoformat(str(fecha_str))
        except: 
            return None

def formatear_a_cronometro(minutos_decimales):
    if pd.isna(minutos_decimales) or minutos_decimales < 0:
        return "00:00:00"
    total_segundos = int(round(minutos_decimales * 60))
    horas = total_segundos // 3600
    minutos = (total_segundos % 3600) // 60
    segundos = total_segundos % 60
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"

def cronometro_a_minutos(texto):
    if pd.isna(texto) or texto in ["N/A", "No registra", ""]: 
        return 0.0
    try:
        partes = str(texto).split(":")
        return int(partes[0]) * 60 + int(partes[1]) + int(partes[2]) / 60.0
    except: 
        return 0.0

# =====================================================================
# FUNCIONES DE LECTURA Y ESCRITURA
# =====================================================================
def cargar_datos_cloud(pestaña_nombre):
    archivo_local = BACKUP_ACTIVAS if pestaña_nombre == "patentes_activas" else BACKUP_HISTORIAL
    sheet = conectar_google_sheets(pestaña_nombre)
    
    cols_activas = [
        "Patente", "Empresa", "Chofer", "RUT", "H1_Llegada_Inversa", 
        "H2_Salida_Inversa", "H3_Llegada_Despacho", "H4_Salida_Despacho", 
        "Ruta_Auditada", "Estado", "Chofer_2", "RUT_2"
    ]
    cols_hist = [
        "Fecha", "Semana", "Mes", "Empresa", "Patente", "Chofer", "RUT", "Ruta Auditada", 
        "Ingreso Inversa", "Salida Inversa", "Ingreso Despacho", "Salida Despacho", 
        "T. Retorno (Descarga)", "T. Despacho (Carga)", "Minutos_Carga_Raw", "Tipo de Cierre", 
        "Chofer 2", "RUT Chofer 2"
    ]
    columnas_requeridas = cols_activas if pestaña_nombre == "patentes_activas" else cols_hist

    df = None
    if sheet:
        try:
            records = sheet.get_all_records()
            if records: 
                df = pd.DataFrame(records)
        except: 
            pass
            
    if df is None or df.empty:
        if os.path.exists(archivo_local):
            try:
                df_local = pd.read_csv(archivo_local)
                if not df_local.empty: 
                    df = df_local
            except: 
                pass
                
    if df is None or df.empty:
        df = pd.DataFrame(columns=columnas_requeridas)
        
    for col in columnas_requeridas:
        if col not in df.columns: 
            df[col] = ""
            
    return df

def guardar_datos_cloud(df, pestaña_nombre):
    archivo_local = BACKUP_ACTIVAS if pestaña_nombre == "patentes_activas" else BACKUP_HISTORIAL
    df.to_csv(archivo_local, index=False)
    sheet = conectar_google_sheets(pestaña_nombre)
    if sheet:
        try:
            sheet.clear()
            df_enviar = df.fillna("").astype(str)
            valores_enviar = [df_enviar.columns.values.tolist()] + df_enviar.values.tolist()
            sheet.update(valores_enviar)
            return True
        except Exception as e:
            st.error(f"❌ Error al guardar en '{pestaña_nombre}': {str(e)}")
            return False
    return False

def agregar_fila_historial_rapido(nueva_fila_dict):
    archivo_local = BACKUP_HISTORIAL
    try:
        if os.path.exists(archivo_local): 
            df_local = pd.read_csv(archivo_local)
        else: 
            df_local = pd.DataFrame()
        df_local = pd.concat([df_local, pd.DataFrame([nueva_fila_dict])], ignore_index=True)
        df_local.to_csv(archivo_local, index=False)
        st.session_state.df_historial = df_local
    except: 
        pass

    sheet = conectar_google_sheets("historial_final")
    if sheet:
        try:
            cols_hist = [
                "Fecha", "Semana", "Mes", "Empresa", "Patente", "Chofer", "RUT", "Ruta Auditada", 
                "Ingreso Inversa", "Salida Inversa", "Ingreso Despacho", "Salida Despacho", 
                "T. Retorno (Descarga)", "T. Despacho (Carga)", "Minutos_Carga_Raw", "Tipo de Cierre", 
                "Chofer 2", "RUT Chofer 2"
            ]
            valores_fila = [str(nueva_fila_dict.get(c, "")) for c in cols_hist]
            sheet.append_row(valores_fila)
            return True
        except Exception as e:
            st.error(f"❌ Error en grabación rápida: {str(e)}")
    return False

# =====================================================================
# INICIO DE DATOS EN MEMORIA
# =====================================================================
if "datos_iniciados" not in st.session_state:
    st.session_state.df_activas = cargar_datos_cloud("patentes_activas")
    st.session_state.df_historial = cargar_datos_cloud("historial_final")
    st.session_state.datos_iniciados = True

if "limpiar_inversa" not in st.session_state: 
    st.session_state.limpiar_inversa = 0
if "limpiar_despacho" not in st.session_state: 
    st.session_state.limpiar_despacho = 0
if "limpiar_salida" not in st.session_state: 
    st.session_state.limpiar_salida = 0

ahora_actual = datetime.datetime.now(zona_local)

# =====================================================================
# ENRUTAMIENTO DE PESTAÑAS (URL)
# =====================================================================
parametros_url = st.query_params
vista_url = parametros_url.get("vista", "admin").lower()

mostrar_tab1 = False
mostrar_tab2 = False
mostrar_tab3 = False
mostrar_tab4 = False
mostrar_tab5 = False
titulos_pestañas = []

if vista_url == "inversa":
    mostrar_tab1, mostrar_tab2, mostrar_tab5 = True, True, True
    titulos_pestañas = ["📥 1. Ingreso Inversa", "📤 2. Salida Inversa", "📊 5. Monitoreo"]
elif vista_url == "despacho":
    mostrar_tab3, mostrar_tab4, mostrar_tab5 = True, True, True
    titulos_pestañas = ["📦 3. Ingreso Despacho", "🚪 4. Salida Despacho", "📊 5. Monitoreo"]
elif vista_url == "monitoreo":
    mostrar_tab5 = True
    titulos_pestañas = ["📊 5. Monitoreo"]
else:
    mostrar_tab1, mostrar_tab2, mostrar_tab3, mostrar_tab4, mostrar_tab5 = True, True, True, True, True
    titulos_pestañas = [
        "📥 1. Ingreso Inversa", "📤 2. Salida Inversa", 
        "📦 3. Ingreso Despacho", "🚪 4. Salida Despacho", "📊 5. Monitoreo"
    ]

pestañas_creadas = st.tabs(titulos_pestañas)
idx = 0
tab1 = pestañas_creadas[idx] if mostrar_tab1 else None
if mostrar_tab1: idx += 1
tab2 = pestañas_creadas[idx] if mostrar_tab2 else None
if mostrar_tab2: idx += 1
tab3 = pestañas_creadas[idx] if mostrar_tab3 else None
if mostrar_tab3: idx += 1
tab4 = pestañas_creadas[idx] if mostrar_tab4 else None
if mostrar_tab4: idx += 1
tab5 = pestañas_creadas[idx] if mostrar_tab5 else None

# =====================================================================
# PESTAÑA 1: INGRESO INVERSA
# =====================================================================
if tab1:
    with tab1:
        st.header("📥 Registro de Ingreso a Logística Inversa")
        with st.form(f"form_ingreso_inversa_{st.session_state.limpiar_inversa}"):
            patente_inv = st.text_input("🚚 Patente del Camión", max_chars=6).upper().strip()
            empresa_inv = st.text_input("🏢 Empresa de Transporte").upper().strip()
            chofer_inv = st.text_input("👤 Nombre del Chofer").upper().strip()
            rut_inv = st.text_input("🆔 RUT del Chofer").strip()
            
            if st.form_submit_button("💾 Registrar Llegada"):
                rut_limpio = formatear_rut(rut_inv)
                
                df_act = st.session_state.df_activas
                patente_existe = not df_act.empty and (patente_inv in df_act["Patente"].values)
                
                if not patente_inv or not empresa_inv or not chofer_inv or not rut_limpio:
                    st.error("❌ Todos los campos son obligatorios.")
                elif len(patente_inv) != 6:
                    st.error("❌ La patente debe tener exactamente 6 caracteres.")
                elif patente_existe:
                    # Texto cortado de forma segura en Python
                    st.warning("⚠️ Esta patente ya registra una operación activa en patio.")
                else:
                    nuevo_registro = pd.DataFrame([{
                        "Patente": patente_inv, 
                        "Empresa": empresa_inv, 
                        "Chofer": chofer_inv, 
                        "RUT": rut_limpio,
                        "H1_Llegada_Inversa": ahora_actual.strftime('%Y-%m-%d %H:%M:%S'), 
                        "H2_Salida_Inversa": "",
                        "H3_Llegada_Despacho": "", 
                        "H4_Salida_Despacho": "",
                        "Ruta_Auditada": "", 
                        "Estado": "En Logística Inversa", 
                        "Chofer_2": "", 
                        "RUT_2": ""
                    }])
                    st.session_state.df_activas = pd.concat([df_act, nuevo_registro], ignore_index=True)
                    guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                    st.success("✅ Registrado con éxito.")
                    st.session_state.limpiar_inversa += 1
                    time.sleep(1)
                    st.rerun()

# =====================================================================
# PESTAÑA 2: SALIDA INVERSA
# =====================================================================
if tab2:
    with tab2:
        st.header("📤 Registro de Salida de Logística Inversa")
        df_act = st.session_state.df_activas
        if
