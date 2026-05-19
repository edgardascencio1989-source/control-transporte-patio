import streamlit as st
import pandas as pd
import datetime
import pytz
import os
import time
import json

# Configuración de la página web
st.set_page_config(page_title="Control Transportes", layout="wide", page_icon="🚚")
zona_local = pytz.timezone('America/Santiago')

# ID de tu planilla de Google Sheets suministrada
SPREADSHEET_ID = "19K8Mn8EGn06i1RXhTkOXrCGvVm8nriWOEbV6TT-uYEg"

# Archivos de respaldo local
BACKUP_ACTIVAS = "backup_patentes_activas.csv"
BACKUP_HISTORIAL = "backup_historial_final.csv"

# =====================================================================
# MOTOR DE CONEXIÓN CON GOOGLE SHEETS (LECTURA DESDE STREAMLIT SECRETS)
# =====================================================================
def conectar_google_sheets(pestaña_nombre):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        if "json_data" not in st.secrets:
            st.error("❌ ERROR CRÍTICO: No se encontró la variable 'json_data' en los Secrets.")
            st.stop()
            return None
            
        try:
            creds_dict = json.loads(st.secrets["json_data"])
        except Exception as json_err:
            st.error(f"❌ ERROR DE FORMATO JSON: El texto guardado en Secrets no es válido. Detalles: {str(json_err)}")
            st.stop()
            return None
        
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        try:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
        except Exception as spread_err:
            st.error(f"❌ ERROR DE ACCESO: El bot no pudo entrar a la planilla. Detalles: {str(spread_err)}")
            st.stop()
            return None
            
        try:
            sheet = spreadsheet.worksheet(pestaña_nombre)
            return sheet
        except Exception as work_err:
            st.error(f"❌ ERROR DE PESTAÑA: No existe la pestaña '{pestaña_nombre}'. Detalles: {str(work_err)}")
            st.stop()
            return None
            
    except Exception as e:
        st.error(f"❌ ERROR GENERAL DE CONEXIÓN SEGURA: {str(e)}")
        st.stop()
        return None

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
            
    df.to_csv(archivo_local, index=False)
    return df

# 🛠️ OPTIMIZACIÓN CRÍTICA: Reescribe completo solo si es necesario (ej. Patentes Activas que cambian estados)
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
            st.error(f"❌ Error crítico al guardar en '{pestaña_nombre}': {str(e)}")
            st.stop()
            return False
    return False

# ⚡ MOTOR DE INSERCIÓN ULTRA RÁPIDA: Añade solo una fila al final para el Histórico Historial sin recargar todo
def agregar_fila_historial_rapido(nueva_fila_dict):
    # 1. Respaldo Local de inmediato
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

    # 2. Inserción veloz en Google Sheets (Inyecta directo abajo)
    sheet = conectar_google_sheets("historial_final")
    if sheet:
        try:
            cols_hist = [
                "Fecha", "Semana", "Mes", "Empresa", "Patente", "Chofer", "RUT", "Ruta Auditada",
                "Ingreso Inversa", "Salida Inversa", "Ingreso Despacho", "Salida Despacho",
                "T. Retorno (Descarga)", "T. Despacho (Carga)", "Minutos_Carga_Raw", "Tipo de Cierre",
                "Chofer 2", "RUT Chofer 2"
            ]
            # Mapeamos los datos ordenados según las columnas
            valores_fila = [str(nueva_fila_dict.get(c, "")) for c in cols_hist]
            sheet.append_row(valores_fila)
            return True
        except Exception as e:
            st.error(f"❌ Error en grabación rápida: {str(e)}")
    return False

# =====================================================================
# INICIALIZACIÓN DE ARCHIVOS
# =====================================================================
st.session_state.df_activas = cargar_datos_cloud("patentes_activas")
st.session_state.df_historial = cargar_datos_cloud("historial_final")

if "limpiar_inversa" not in st.session_state:
    st.session_state.limpiar_inversa = 0
if "limpiar_despacho" not in st.session_state:
    st.session_state.limpiar_despacho = 0
if "limpiar_salida" not in st.session_state:
    st.session_state.limpiar_salida = 0

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
# DETECCIÓN DE ROL POR LINK (URL COMPARTIBLES)
# =====================================================================
parametros_url = st.query_params
vista_url = parametros_url.get("vista", "admin").lower()

mostrar_tab1, mostrar_tab2, mostrar_tab3, mostrar_tab4, mostrar_tab5 = False, False, False, False, False
titulos_pestañas = []
subtitulo_pantalla = ""

if vista_url == "inversa":
    mostrar_tab1, mostrar_tab2, mostrar_tab5 = True, True, True
    titulos_pestañas = ["📥 1. Ingreso Logística Inversa", "📤 2. Salida de Inversa", "📊 5. Monitoreo y KPIS"]
    subtitulo_pantalla = "🔄 Módulo Operativo: EQUIPO LOGÍSTICA INVERSA"
elif vista_url == "despacho":
    mostrar_tab3, mostrar_tab4, mostrar_tab5 = True, True, True
    titulos_pestañas = ["📦 3. Ingreso a despacho", "🚪 4. Salida Despacho", "📊 5. Monitoreo y KPIS"]
    subtitulo_pantalla = "📦 Módulo Operativo: EQUIPO DESPACHO"
elif vista_url == "monitoreo":
    mostrar_tab5 = True
    titulos_pestañas = ["📊 5. Monitoreo y KPIS"]
    subtitulo_pantalla = "🖥️
