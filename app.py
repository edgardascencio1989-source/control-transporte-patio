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
# MOTOR DE CONEXIÓN CON GOOGLE SHEETS (CON PARCHE PARA ERROR PEM)
# =====================================================================
def conectar_google_sheets(pestaña_nombre):
    """Establece conexión segura usando los Secrets de Streamlit en formato JSON"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        if "json_data" not in st.secrets:
            return None
            
        creds_dict = json.loads(st.secrets["json_data"])
        
        # Parche para el error InvalidByte (PEM): arregla los saltos de línea
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
    
    if sheet:
        try:
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            df.to_csv(archivo_local, index=False)
            return df
        except:
            pass
            
    if os.path.exists(archivo_local):
        try:
            return pd.read_csv(archivo_local)
        except:
            pass
        
    if pestaña_nombre == "patentes_activas":
        return pd.DataFrame(columns=[
            "Patente", "Empresa", "Chofer", "RUT", "H1_Llegada_Inversa", 
            "H2_Salida_Inversa", "H3_Llegada_Despacho", "H4_Salida_Despacho", 
            "Ruta_Auditada", "Estado"
        ])
    else:
        return pd.DataFrame(columns=[
            "Fecha", "Semana", "Mes", "Empresa", "Patente", "Chofer", "RUT", "Ruta Auditada",
            "Ingreso Inversa", "Salida Inversa", "Ingreso Despacho", "Salida Despacho",
            "T. Retorno (Descarga)", "T. Despacho (Carga)"
        ])

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

# Inicialización del estado en memoria
if "df_activas" not in st.session_state:
    st.session_state.df_activas = cargar_datos_cloud("patentes_activas")
if "df_historial" not in st.session_state:
    st.session_state.df_historial = cargar_datos_cloud("historial_final")
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
# INTERFAZ GRÁFICA PRINCIPAL
# =====================================================================
st.title("🚚 Control de salidas e ingresos Transporte")

# VISTA DE PESTAÑAS HORIZONTALES (Diseño original)
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 1. Ingreso Logística Inversa", 
    "📤 2. Salida de Inversa", 
    "📦 3. Ingreso a despacho", 
    "🚪 4. Salida Despacho",
    "📊 5. Monitoreo y KPIS"
])

ahora_actual = datetime.datetime.now(zona_local)

# =====================================================================
# PESTAÑA 1: INGRESO INVERSA
# =====================================================================
with tab1:
    st.header("📥 Registro de Ingreso a Logística Inversa")
    with st.form("form_ingreso_inversa", clear_on_submit=True):
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
                time.sleep(1)
                st.rerun()

# =====================================================================
# PESTAÑA 2: SALIDA INVERSA
# =====================================================================
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
with tab3:
    st.header("📦 Registro de Ingreso a Despacho")
    lista_espera = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "Esperando Despacho"]["Patente"].tolist() if not st.session_state.df_activas.empty else []
    
    patente_desp = st.selectbox("Buscar Patente en Espera:", [""] + lista_espera).upper().strip()
    
    if patente_desp:
        fila = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_desp].iloc[0]
        with st.form(f"form_despacho_{st.session_state.limpiar_despacho}"):
            empresa_f = st.text_input("🏢 Empresa", value=fila["Empresa"]).upper().strip()
            chofer_f = st.text_input("👤 Nombre y apellido del Chofer", value=fila["Chofer"]).upper().strip()
            rut_f = st.text_input("🆔 RUT", value=fila["RUT"], max_chars=10).upper().strip()
            
            if st.form_submit_button("📥 Registrar Entrada a Carga"):
                if len(rut_f) < 9 or len(rut_f) > 10:
                    st.error(f"❌ El RUT debe tener entre 9 y 10 caracteres (Tiene {len(rut_f)}).")
                else:
                    idx = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_desp].index[0]
                    st.session_state.df_activas.at[idx, "Empresa"] = empresa_f
                    st.session_state.df_activas.at[idx, "Chofer"] = chofer_f
                    st.session_state.df_activas.at[idx, "RUT"] = rut_f
                    st.session_state.df_activas.at[idx, "H3_Llegada_Despacho"] = ahora_actual.isoformat()
                    st.session_state.df_activas.at[idx, "Estado"] = "En Despacho (Cargando)"
                    guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                    st.success("✅ Posicionado en Despacho.")
                    st.session_state.limpiar_despacho += 1
                    time.sleep(1)
                    st.rerun()

# =====================================================================
# PESTAÑA 4: SALIDA DESPACHO
# =====================================================================
with tab4:
    st.header("🚪 Control de Salida Despacho")
    lista_cargando = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "En Despacho (Cargando)"]["Patente"].tolist() if not st.session_state.df_activas.empty else []
    
    with st.form(f"form_salida_{st.session_state.limpiar_salida}"):
        patente_final = st.selectbox("Patente que termina Carga:", [""] + lista_cargando)
        ruta_aud = st.text_input("📋 Ruta Auditada:").upper().strip()
        
        if st.form_submit_button("🏁 Confirmar Salida y Archivar"):
            if patente_final and ruta_aud:
                fila_viaje = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_final].iloc[0].copy()
                st.session_state.df_activas = st.session_state.df_activas[st.session_state.df_activas["Patente"] != patente_final]
                
                h1 = datetime.datetime.fromisoformat(fila_viaje["H1_Llegada_Inversa"]) if pd.notna(fila_viaje["H1_Llegada_Inversa"]) and fila_viaje["H1_Llegada_Inversa"] else None
                h2 = datetime.datetime.fromisoformat(fila_viaje["H2_Salida_Inversa"]) if pd.notna(fila_viaje["H2_Salida_Inversa"]) and fila_viaje["H2_Salida_Inversa"] else None
                h3 = datetime.datetime.fromisoformat(fila_viaje["H3_Llegada_Despacho"])
                h4 = ahora_actual
                
                t_retorno = (h2 - h1).total_seconds() / 60 if h1 and h2 else None
                t_carga = (h4 - h3).total_seconds() / 60
                
                nuevo_hist = pd.DataFrame([{
                    "Fecha": h3.strftime('%d-%m-%Y'), "Semana": f"Semana {h3.isocalendar()[1]}",
                    "Mes": ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][h3.month],
                    "Empresa": fila_viaje["Empresa"], "Patente": patente_final, "Chofer": fila_viaje["Chofer"], 
                    "RUT": fila_viaje["RUT"], "Ruta Auditada": ruta_aud,
                    "Ingreso Inversa": h1.strftime('%H:%M:%S') if h1 else "N/A",
                    "Salida Inversa": h2.strftime('%H:%M:%S') if h2 else "N/A",
                    "Ingreso Despacho": h3.strftime('%H:%M:%S'), "Salida Despacho": h4.strftime('%H:%M:%S'),
                    "T. Retorno (Descarga)": formatear_a_cronometro(t_retorno) if t_retorno is not None else "N/A",
                    "T. Despacho (Carga)": formatear_a_cronometro(t_carga),
                    "Minutos_Carga_Raw": t_carga
                }])
                
                st.session_state.df_historial = pd.concat([st.session_state.df_historial, nuevo_hist], ignore_index=True)
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                
                df_guardar_hist = st.session_state.df_historial.drop(columns=["Minutos_Carga_Raw"], errors='ignore')
                guardar_datos_cloud(df_guardar_hist, "historial_final")
                
                st.success("✅ Viaje archivado.")
                st.session_state.limpiar_salida += 1
                time.sleep(1)
                st.rerun()
            else:
                st.error("Rellene todos los campos.")

# =====================================================================
# PESTAÑA 5: MONITOREO Y KPIS
# =====================================================================
with tab5:
    st.header("📊 Monitor de Patio y Estadísticas")
    
    # Cambio 2: Texto modificado a "Vehículos en CD"
    st.subheader("🚚 Vehículos en CD")
    if not st.session_state.df_activas.empty:
        st.dataframe(st.session_state.df_activas[["Patente", "Empresa", "Chofer", "Estado"]], use_container_width=True)
    else:
        st.info("No hay vehículos en CD.")
        
    st.markdown("---")
    
    # Cambio 1: Inyección de Bloque de Filtros de Reportería
    st.subheader("🔍 Filtros de Reportería")
    if not st.session_state.df_historial.empty:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            lista_fechas = ["Todos"] + sorted(list(st.session_state.df_historial["Fecha"].dropna().unique()))
            filtro_fecha = st.selectbox("Filtrar por Fecha:", lista_fechas)
        with col_f2:
            lista_semanas = ["Todos"] + sorted(list(st.session_state.df_historial["Semana"].dropna().unique()))
            filtro_semana = st.selectbox("Filtrar por Semana:", lista_semanas)
        with col_f3:
            lista_meses = ["Todos"] + sorted(list(st.session_state.df_historial["Mes"].dropna().unique()))
            filtro_mes = st.selectbox("Filtrar por Mes:", lista_meses)
            
        # Lógica de Filtrado unificado para las tablas inferiores
        df_filtrado_kpis = st.session_state.df_historial.copy()
        if filtro_fecha != "Todos":
            df_filtrado_kpis = df_filtrado_kpis[df_filtrado_kpis["Fecha"] == filtro_fecha]
        if filtro_semana != "Todos":
            df_filtrado_kpis = df_filtrado_kpis[df_filtrado_kpis["Semana"] == filtro_semana]
        if filtro_mes != "Todos":
            df_filtrado_kpis = df_filtrado_kpis[df_filtrado_kpis["Mes"] == filtro_mes]
            
        # Cambio 3: Tabla "Consolidado Histórico" se despliega PRIMERO
        st.subheader("📋 Consolidado Histórico")
        df_mostrar = df_filtrado_kpis.drop(columns=["Minutos_Carga_Raw"], errors='ignore')
        st.dataframe(df_mostrar, use_container_width=True)
        
        st.markdown("---")
        
        # Cambio 2 y 3: Se cambia el título a "Estadía Promedio CD" y se posiciona ABAJO
        st.subheader("📈 Estadía Promedio CD")
        if "Minutos_Carga_Raw" in df_filtrado_kpis.columns:
            df_stats = df_filtrado_kpis.copy()
            df_stats['Minutos_Carga_Raw'] = pd.to_numeric(df_stats['Minutos_Carga_Raw'], errors='coerce')
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Por Empresa**")
                st.dataframe(df_stats.groupby("Empresa")["Minutos_Carga_Raw"].mean().round(1).reset_index().rename(columns={"Minutos_Carga_Raw": "Minutos Promedio"}), use_container_width=True)
            with c2:
                st.markdown("**Por Chofer**")
                st.dataframe(df_stats.groupby("Chofer")["Minutos_Carga_Raw"].mean().round(1).reset_index().rename(columns={"Minutos_Carga_Raw": "Minutos Promedio"}), use_container_width=True)
            with c3:
                st.markdown("**Por Patente**")
                st.dataframe(df_stats.groupby("Patente")["Minutos_Carga_Raw"].mean().round(1).reset_index().rename(columns={"Minutos_Carga_Raw": "Minutos Promedio"}), use_container_width=True)
        else:
            st.info("Falta procesar datos numéricos para calcular promedios.")
    else:
        st.info("No hay datos históricos registrados en la planilla para aplicar filtros.")
