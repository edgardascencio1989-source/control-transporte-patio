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

# ID de la planilla
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
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except: return None

def conectar_google_sheets(pestaña_nombre):
    client = obtener_cliente_gspread()
    if not client:
        st.error("❌ Error con las credenciales.")
        st.stop()
        return None
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return spreadsheet.worksheet(pestaña_nombre)
    except Exception as e:
        st.error(f"❌ Error buscando pestaña '{pestaña_nombre}': {str(e)}")
        st.stop()
        return None

# =====================================================================
# FUNCIONES DE APOYO (RUT, FECHAS, FORMATOS)
# =====================================================================
def formatear_rut(rut_input):
    r = str(rut_input).upper().replace(".", "").replace("-", "").replace(" ", "").strip()
    if len(r) > 1:
        return r[:-1] + "-" + r[-1]
    return r

def parse_fecha(fecha_str):
    if pd.isna(fecha_str) or not fecha_str: return None
    try: return datetime.datetime.strptime(str(fecha_str), '%Y-%m-%d %H:%M:%S')
    except:
        try: return datetime.datetime.fromisoformat(str(fecha_str))
        except: return None

def formatear_a_cronometro(minutos_decimales):
    if pd.isna(minutos_decimales) or minutos_decimales < 0: return "00:00:00"
    total_segundos = int(round(minutos_decimales * 60))
    h = total_segundos // 3600
    m = (total_segundos % 3600) // 60
    s = total_segundos % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def cronometro_a_minutos(texto):
    if pd.isna(texto) or texto in ["N/A", ""]: return 0.0
    try:
        p = str(texto).split(":")
        return int(p[0]) * 60 + int(p[1]) + int(p[2]) / 60.0
    except: return 0.0

# =====================================================================
# FUNCIONES DE LECTURA Y ESCRITURA
# =====================================================================
def cargar_datos_cloud(pestaña_nombre):
    archivo_local = BACKUP_ACTIVAS if pestaña_nombre == "patentes_activas" else BACKUP_HISTORIAL
    sheet = conectar_google_sheets(pestaña_nombre)
    df = None
    if sheet:
        try:
            records = sheet.get_all_records()
            if records: df = pd.DataFrame(records)
        except: pass
    
    if df is None or df.empty:
        if os.path.exists(archivo_local):
            try: df = pd.read_csv(archivo_local)
            except: pass
    return df if df is not None else pd.DataFrame()

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

if "limpiar_inversa" not in st.session_state: st.session_state.limpiar_inversa = 0
if "limpiar_despacho" not in st.session_state: st.session_state.limpiar_despacho = 0
if "limpiar_salida" not in st.session_state: st.session_state.limpiar_salida = 0

ahora_actual = datetime.datetime.now(zona_local)

# =====================================================================
# ESTRUCTURA DE PESTAÑAS
# =====================================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 1. Ingreso Logística Inversa", 
    "📤 2. Salida de Inversa", 
    "📦 3. Ingreso a despacho", 
    "🚪 4. Salida Despacho", 
    "📊 5. Monitoreo y KPIS"
])

# =====================================================================
# PESTAÑA 1
# =====================================================================
with tab1:
    st.header("📥 Registro de Ingreso a Logística Inversa")
    with st.form(f"form_ingreso_inversa_{st.session_state.limpiar_inversa}"):
        patente_inv = st.text_input("🚚 Patente", max_chars=6).upper().strip()
        empresa_inv = st.text_input("🏢 Empresa").upper().strip()
        chofer_inv = st.text_input("👤 Chofer").upper().strip()
        rut_inv = st.text_input("🆔 RUT Chofer").strip()
        
        if st.form_submit_button("💾 Registrar Llegada"):
            rut_l = formatear_rut(rut_inv)
            if not patente_inv or not empresa_inv or not chofer_inv or not rut_l:
                st.error("❌ Faltan datos obligatorios.")
            elif patente_inv in st.session_state.df_activas["Patente"].values:
                st.warning("⚠️ Patente activa en patio.")
            else:
                nuevo = pd.DataFrame([{
                    "Patente": patente_inv, "Empresa": empresa_inv, "Chofer": chofer_inv, "RUT": rut_l, 
                    "H1_Llegada_Inversa": ahora_actual.strftime('%Y-%m-%d %H:%M:%S'), "Estado": "En Logística Inversa"
                }])
                st.session_state.df_activas = pd.concat([st.session_state.df_activas, nuevo], ignore_index=True)
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                st.session_state.limpiar_inversa += 1
                st.rerun()

# =====================================================================
# PESTAÑA 2
# =====================================================================
with tab2:
    st.header("📤 Registro de Salida de Inversa")
    lista_inv = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "En Logística Inversa"]["Patente"].tolist()
    sel_inv = st.selectbox("Patente:", [""] + lista_inv)
    if st.button("📤 Confirmar Salida Inversa"):
        idx = st.session_state.df_activas[st.session_state.df_activas["Patente"] == sel_inv].index[0]
        st.session_state.df_activas.at[idx, "H2_Salida_Inversa"] = ahora_actual.strftime('%Y-%m-%d %H:%M:%S')
        st.session_state.df_activas.at[idx, "Estado"] = "Esperando Despacho"
        guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
        st.rerun()

# =====================================================================
# PESTAÑA 3
# =====================================================================
with tab3:
    st.header("📦 Registro de Ingreso a Despacho")
    p_d = st.text_input("🚚 Patente Despacho:", key="txt_d").upper().strip()
    if len(p_d) == 6 and p_d in st.session_state.df_activas["Patente"].values:
        fila = st.session_state.df_activas[st.session_state.df_activas["Patente"] == p_d].iloc[0]
        if fila["Estado"] == "En Logística Inversa": st.error("⛔ Debe salir de Inversa primero.")
        else:
            with st.form("form_despacho"):
                ch_f = st.text_input("👤 Chofer:", value=fila["Chofer"]).upper().strip()
                rt_f = st.text_input("🆔 RUT:", value=fila["RUT"]).strip()
                if st.form_submit_button("📥 Ingresar"):
                    rt_n = formatear_rut(rt_f)
                    idx = st.session_state.df_activas[st.session_state.df_activas["Patente"] == p_d].index[0]
                    c_orig = str(fila["Chofer"]).upper().strip()
                    r_orig = formatear_rut(fila["RUT"])
                    
                    if ch_f != c_orig or rt_n != r_orig:
                        h1 = parse_fecha(fila["H1_Llegada_Inversa"])
                        h2 = parse_fecha(fila["H2_Salida_Inversa"])
                        t_ret = (h2 - h1).total_seconds() / 60 if h1 and h2 else 0.0
                        
                        hist = {
                            "Fecha": ahora_actual.strftime('%d-%m-%Y'),
                            "Patente": p_d, "Chofer": c_orig, "RUT": r_orig,
                            "Ruta Auditada": f"CAMBIO A {ch_f}",
                            "T. Retorno (Descarga)": formatear_a_cronometro(t_ret),
                            "Tipo de Cierre": "Cambio Conductor",
                            "Chofer 2": ch_f, "RUT Chofer 2": rt_n
                        }
                        agregar_fila_historial_rapido(hist)
                        st.session_state.df_activas.at[idx, "Chofer_2"] = c_orig
                        st.session_state.df_activas.at[idx, "RUT_2"] = r_orig
                    
                    st.session_state.df_activas.at[idx, "Chofer"] = ch_f
                    st.session_state.df_activas.at[idx, "RUT"] = rt_n
                    st.session_state.df_activas.at[idx, "H3_Llegada_Despacho"] = ahora_actual.strftime('%Y-%m-%d %H:%M:%S')
                    st.session_state.df_activas.at[idx, "Estado"] = "En Despacho (Cargando)"
                    guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                    st.rerun()

# =====================================================================
# PESTAÑA 4
# =====================================================================
with tab4:
    st.header("🚪 Salida Despacho")
    lista_c = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "En Despacho (Cargando)"]["Patente"].tolist()
    with st.form("form_salida"):
        p_f = st.selectbox("Patente:", [""] + lista_c)
        ruta = st.text_input("📋 Ruta:").upper()
        if st.form_submit_button("🏁 Confirmar"):
            fila = st.session_state.df_activas[st.session_state.df_activas["Patente"] == p_f].iloc[0]
            h4 = ahora_actual
            h3 = parse_fecha(fila["H3_Llegada_Despacho"])
            t_carg = (h4 - h3).total_seconds() / 60 if h3 else 0.0
            
            hist = {
                "Fecha": h4.strftime('%d-%m-%Y'), "Patente": p_f, "Chofer": fila["Chofer"],
                "RUT": formatear_rut(fila["RUT"]), "Ruta Auditada": ruta,
                "Salida Despacho": h4.strftime('%H:%M:%S'),
                "T. Despacho (Carga)": formatear_a_cronometro(t_carg),
                "Tipo de Cierre": "Normal"
            }
            agregar_fila_historial_rapido(hist)
            st.session_state.df_activas = st.session_state.df_activas[st.session_state.df_activas["Patente"] != p_f]
            guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
            st.rerun()

# =====================================================================
# PESTAÑA 5
# =====================================================================
with tab5:
    st.header("📊 Monitor")
    st.dataframe(st.session_state.df_activas, use_container_width=True)
    st.subheader("📋 Historial")
    st.dataframe(st.session_state.df_historial.iloc[::-1], use_container_width=True)
