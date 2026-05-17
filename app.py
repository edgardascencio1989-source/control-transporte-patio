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
# MOTOR DE CONEXIÓN CON GOOGLE SHEETS
# =====================================================================
def conectar_google_sheets(pestaña_nombre):
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
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(pestaña_nombre)
        return sheet
    except Exception as e:
        return None

def cargar_datos_cloud(pestaña_nombre):
    archivo_local = BACKUP_ACTIVAS if pestaña_nombre == "patentes_activas" else BACKUP_HISTORIAL
    sheet = conectar_google_sheets(pestaña_nombre)
    
    cols_activas = [
        "Patente", "Empresa", "Chofer", "RUT", "H1_Llegada_Inversa", 
        "H2_Salida_Inversa", "H3_Llegada_Despacho", "H4_Salida_Despacho", 
        "Ruta_Auditada", "Estado"
    ]
    cols_hist = [
        "Fecha", "Semana", "Mes", "Empresa", "Patente", "Chofer", "RUT", "Ruta Auditada",
        "Ingreso Inversa", "Salida Inversa", "Ingreso Despacho", "Salida Despacho",
        "T. Retorno (Descarga)", "T. Despacho (Carga)", "Minutos_Carga_Raw"
    ]
    columnas_requeridas = cols_activas if pestaña_nombre == "patentes_activas" else cols_hist

    df = None
    
    if sheet:
        try:
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
        except Exception:
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

def guardar_datos_cloud(df, pestaña_nombre):
    archivo_local = BACKUP_ACTIVAS if pestaña_nombre == "patentes_activas" else BACKUP_HISTORIAL
    df.to_csv(archivo_local, index=False)
    
    sheet = conectar_google_sheets(pestaña_nombre)
    if sheet:
        try:
            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.fillna("").values.tolist())
            return True
        except Exception as e:
            pass
    return False

# =====================================================================
# ACTUALIZACIÓN SILENCIOSA Y LLAVES DE LIMPIEZA INTELIGENTE
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
    subtitulo_pantalla = "🖥️ Módulo de Visualización: EQUIPO MONITORES"
else:
    mostrar_tab1, mostrar_tab2, mostrar_tab3, mostrar_tab4, mostrar_tab5 = True, True, True, True, True
    titulos_pestañas = [
        "📥 1. Ingreso Logística Inversa", "📤 2. Salida de Inversa", 
        "📦 3. Ingreso a despacho", "🚪 4. Salida Despacho", "📊 5. Monitoreo y KPIS"
    ]
    subtitulo_pantalla = "👑 Módulo Global: ADMINISTRACIÓN"

# ENCABEZADO PRINCIPAL
st.title("🚚 Control de salidas e ingresos Transporte")
st.caption(subtitulo_pantalla)

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

ahora_actual = datetime.datetime.now(zona_local)

# =====================================================================
# PESTAÑA 1: INGRESO INVERSA
# =====================================================================
if tab1:
    with tab1:
        st.header("📥 Registro de Ingreso a Logística Inversa")
        with st.form(f"form_ingreso_inversa_{st.session_state.limpiar_inversa}"):
            patente_inv = st.text_input("🚚 Patente del Camión", max_chars=6, help="Largo exacto de 6 caracteres").upper().strip()
            empresa_inv = st.text_input("🏢 Empresa de Transporte").upper().strip()
            chofer_inv = st.text_input("👤 Nombre y apellido del Chofer").upper().strip()
            rut_inv = st.text_input("🆔 RUT del Chofer", max_chars=10, help="Mínimo 9 y máximo 10 caracteres").upper().strip()
            
            if st.form_submit_button("💾 Registrar Llegada a Inversa"):
                if not patente_inv or not empresa_inv or not chofer_inv or not rut_inv:
                    st.error("❌ Todos los campos son obligatorios.")
                elif len(patente_inv) != 6:
                    st.error(f"❌ La patente ingresada tiene {len(patente_inv)} caracteres. Debe tener exactamente 6 caracteres.")
                elif len(rut_inv) < 9 or len(rut_inv) > 10:
                    st.error(f"❌ El RUT ingresado tiene {len(rut_inv)} caracteres. Debe tener un mínimo de 9 y un máximo de 10 caracteres.")
                elif not st.session_state.df_activas.empty and patente_inv in st.session_state.df_activas["Patente"].values:
                    st.warning("⚠️ Esta patente ya registra una operación activa en patio.")
                else:
                    nuevo_registro = pd.DataFrame([{
                        "Patente": patente_inv, "Empresa": empresa_inv, "Chofer": chofer_inv, "RUT": rut_inv,
                        "H1_Llegada_Inversa": ahora_actual.isoformat(), "H2_Salida_Inversa": "",
                        "H3_Llegada_Despacho": "", "H4_Salida_Despacho": "",
                        "Ruta_Auditada": "", "Estado": "En Logística Inversa"
                    }])
                    st.session_state.df_activas = pd.concat([st.session_state.df_activas, nuevo_registro], ignore_index=True)
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
        lista_inv = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "En Logística Inversa"]["Patente"].tolist() if not st.session_state.df_activas.empty else []
        
        patente_salida_inv = st.selectbox("Seleccione Patente:", [""] + lista_inv, key="sel_salida_inv")
        if st.button("📤 Confirmar Salida de Inversa"):
            if patente_salida_inv:
                idx = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_salida_inv].index[0]
                st.session_state.df_activas.at[idx, "H2_Salida_Inversa"] = ahora_actual.isoformat()
                st.session_state.df_activas.at[idx, "Estado"] = "Esperando Despacho"
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                st.success("✅ Salida confirmada.")
                time.sleep(1)
                st.rerun()

# =====================================================================
# PESTAÑA 3: INGRESO DESPACHO
# =====================================================================
if tab3:
    with tab3:
        st.header("📦 Registro de Ingreso a Despacho")
        lista_totales = st.session_state.df_activas["Patente"].tolist() if not st.session_state.df_activas.empty else []
        
        patente_desp = st.selectbox("Buscar o Seleccionar Patente para Despacho:", [""] + lista_totales, key=f"sel_desp_{st.session_state.limpiar_despacho}").upper().strip()
        
        if patente_desp:
            fila = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_desp].iloc[0]
            
            if fila["Estado"] == "En Logística Inversa":
                # Alerta larga separada en líneas seguras para evitar SyntaxError
                st.error(
                    "⛔ RESTRICCIÓN ACTIVA: Este vehículo no ha registrado su SALIDA desde Logística "
                    "Inversa (Módulo 2). El registro en Despacho está completamente bloqueado. "
                    "(Si el equipo de Inversa ya le dio salida, actualiza la página o vuelve a seleccionarlo)."
                )
            
            elif fila["Estado"] == "En Despacho (Cargando)":
                st.info(f"✅ La patente {patente_desp} ya fue ingresada a Despacho exitosamente. Está en proceso de carga.")
            
            else:
                with st.form("form_despacho_inner"):
                    empresa_f = st.text_input("🏢 Empresa", value=fila["Empresa"]).upper().strip()
                    chofer_f = st.text_input("👤 Nombre y apellido del Chofer", value=fila["Chofer"]).upper().strip()
                    rut_f = st.text_input("🆔 RUT", value=fila["RUT"], max_chars=10).upper().strip()
                    
                    if st.form_submit_button("
