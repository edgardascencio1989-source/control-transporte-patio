import streamlit as st
import pandas as pd
import datetime
import pytz
import os
import time

# Configuración de la página web
st.set_page_config(page_title="Control Transportes", layout="wide", page_icon="🚚")
zona_local = pytz.timezone('America/Santiago')

# ID de tu planilla de Google Sheets suministrada
SPREADSHEET_ID = "19K8Mn8EGn06i1RXhTkOXrCGvVm8nriWOEbV6TT-uYEg"

# Archivos de respaldo local para garantizar operación 24/7 sin internet
BACKUP_ACTIVAS = "backup_patentes_activas.csv"
BACKUP_HISTORIAL = "backup_historial_final.csv"

# =====================================================================
# MOTOR DE CONEXIÓN CON GOOGLE SHEETS Y RESPALDO (ESTABILIDAD)
# =====================================================================
def conectar_google_sheets(pestaña_nombre):
    """Establece conexión segura usando el archivo JSON de credenciales de la cuenta de servicio"""
    CREDS_FILE = "secreto_google.json"
    
    if not os.path.exists(CREDS_FILE):
        return None # Si no encuentra el archivo JSON, opera en modo local transparente
        
    try:
        from oauth2client.service_account import ServiceAccountCredentials
        import gspread
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(pestaña_nombre)
        return sheet
    except Exception as e:
        return None

def cargar_datos_cloud(pestaña_nombre):
    """Lee datos desde Google Sheets con caídas automáticas a respaldo local si falla internet"""
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
            
    # Si la nube no responde, levanta el respaldo local de la PC inmediatamente
    if os.path.exists(archivo_local):
        try:
            return pd.read_csv(archivo_local)
        except:
            pass
        
    # Estructuras vacías por defecto si es la primera vez que inicia el sistema sin red
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
    """Guarda inmediatamente en el disco de la PC y sincroniza de forma limpia en la nube"""
    archivo_local = BACKUP_ACTIVAS if pestaña_nombre == "patentes_activas" else BACKUP_HISTORIAL
    
    # 1. Asegurar persistencia local inmediata (Dato protegido contra cortes de energía)
    df.to_csv(archivo_local, index=False)
    
    # 2. Sincronización con la planilla de Google Sheets
    sheet = conectar_google_sheets(pestaña_nombre)
    if sheet:
        try:
            import gspread
            sheet.clear()
            # Se inyectan encabezados y el contenido convirtiendo nulos a texto vacío
            sheet.update([df.columns.values.tolist()] + df.fillna("").values.tolist())
            return True
        except Exception as e:
            pass
    return False

# Inicialización del estado de la aplicación en memoria
if "df_activas" not in st.session_state:
    st.session_state.df_activas = cargar_datos_cloud("patentes_activas")
if "df_historial" not in st.session_state:
    st.session_state.df_historial = cargar_datos_cloud("historial_final")

if "limpiar_despacho" not in st.session_state:
    st.session_state.limpiar_despacho = 0
if "limpiar_salida" not in st.session_state:
    st.session_state.limpiar_salida = 0

# Función para formatear minutos a formato Cronómetro (HH:MM:SS)
def formatear_a_cronometro(minutos_decimales):
    if pd.isna(minutos_decimales) or minutos_decimales < 0:
        return "00:00:00"
    total_segundos = int(round(minutos_decimales * 60))
    horas = total_segundos // 3600
    minutos = (total_segundos % 3600) // 60
    segundos = total_segundos % 60
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"

# =====================================================================
# DETECCIÓN DE ROL POR LINK (URL)
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
        "📥 1. Ingreso Logística Inversa", 
        "📤 2. Salida de Inversa", 
        "📦 3. Ingreso a despacho", 
        "🚪 4. Salida Despacho",
        "📊 5. Monitoreo y KPIS"
    ]
    subtitulo_pantalla = "👑 Módulo Global: ADMINISTRACIÓN"

# Renderizado de Encabezados principales
st.title("🚚 Control de salidas e ingresos Transporte")
st.caption(subtitulo_pantalla)

# Crear dinámicamente las pestañas autorizadas según la URL
pestañas_creadas = st.tabs(titulos_pestañas)

indice = 0
tab1 = pestañas_creadas[indice] if mostrar_tab1 else None
if mostrar_tab1: indice += 1

tab2 = pestañas_creadas[indice] if mostrar_tab2 else None
if mostrar_tab2: indice += 1

tab3 = pestañas_creadas[indice] if mostrar_tab3 else None
if mostrar_tab3: indice += 1

tab4 = pestañas_creadas[indice] if mostrar_tab4 else None
if mostrar_tab4: indice += 1

tab5 = pestañas_creadas[indice] if mostrar_tab5 else None

ahora_actual = datetime.datetime.now(zona_local)

# =====================================================================
# PESTAÑA 1: INGRESO LOGÍSTICA INVERSA
# =====================================================================
if tab1:
    with tab1:
        st.header("📥 Registro de Ingreso a Logística Inversa")
        
        with st.form("form_ingreso_inversa", clear_on_submit=True):
            patente_inv = st.text_input("🚚 Patente del Camión", max_chars=6, help="Debe contener exactamente 6 caracteres").upper().strip()
            empresa_inv = st.text_input("🏢 Empresa de Transporte").upper().strip()
            chofer_inv = st.text_input("👤 Nombre y apellido del Chofer").upper().strip()
            rut_inv = st.text_input("🆔 RUT del Chofer (ej: 12345678K)", max_chars=10, help="Largo permitido entre 9 y 10 caracteres").upper().strip()
            
            btn_ingreso_inv = st.form_submit_button("💾 Registrar Llegada a Inversa")
            
        if btn_ingreso_inv:
            if not patente_inv or not empresa_inv or not chofer_inv or not rut_inv:
                st.error("❌ Todos los campos son obligatorios.")
            elif len(patente_inv) != 6:
                st.error(f"❌ La patente ingresada tiene {len(patente_inv)} caracteres. Debe tener exactamente 6 caracteres.")
            elif len(rut_inv) < 9 or len(rut_inv) > 10:
                st.error(f"❌ El RUT ingresado tiene {len(rut_inv)} caracteres. Debe tener entre 9 y 10 caracteres.")
            elif not st.session_state.df_activas.empty and patente_inv in st.session_state.df_activas["Patente"].values:
                st.warning(f"⚠️ La patente {patente_inv} ya registra una operación activa en patio.")
            else:
                nuevo_registro = pd.DataFrame([{
                    "Patente": patente_inv, "Empresa": empresa_inv, "Chofer": chofer_inv, "RUT": rut_inv,
                    "H1_Llegada_Inversa": ahora_actual.isoformat(), "H2_Salida_Inversa": "",
                    "H3_Llegada_Despacho": "", "H4_Salida_Despacho": "",
                    "Ruta_Auditada": "", "Estado": "En Logística Inversa"
                }])
                st.session_state.df_activas = pd.concat([st.session_state.df_activas, nuevo_registro], ignore_index=True)
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                st.success(f"✅ Patente {patente_inv} registrada en Inversa con éxito.")
                time.sleep(1.5)
                st.rerun()

# =====================================================================
# PESTAÑA 2: SALIDA DE INVERSA
# =====================================================================
if tab2:
    with tab2:
        st.header("📤 Registro de Salida de Logística Inversa")
        
        lista_inv = []
        if not st.session_state.df_activas.empty:
            lista_inv = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "En Logística Inversa"]["Patente"].tolist()
        
        patente_salida_inv = st.selectbox("Seleccione la Patente que se retira de Inversa:", [""] + lista_inv, key="sel_salida_inv")
        btn_salida_inv = st.button("📤 Confirmar Salida de Inversa")
        
        if btn_salida_inv:
            if not patente_salida_inv:
                st.error("❌ Seleccione una patente válida de la lista.")
            else:
                idx = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_salida_inv].index[0]
                st.session_state.df_activas.at[idx, "H2_Salida_Inversa"] = ahora_actual.isoformat()
                st.session_state.df_activas.at[idx, "Estado"] = "Esperando Despacho"
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                st.success(f"✅ Patente {patente_salida_inv} liberada de Inversa.")
                time.sleep(1.5)
                st.rerun()

# =====================================================================
# PESTAÑA 3: INGRESO A DESPACHO
# =====================================================================
if tab3:
    with tab3:
        st.header("📦 Registro de Ingreso a Despacho")
        st.write("Seleccione una patente de la lista de espera o digite una patente directa en la barra de búsqueda:")
        
        lista_espera_despacho = []
        if not st.session_state.df_activas.empty:
            lista_espera_despacho = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "Esperando Despacho"]["Patente"].tolist()
            
        patente_desp = st.selectbox("Buscar / Digitar Patente para Despacho:", [""] + lista_espera_despacho, key="patente_unificada").upper().strip()
        
        if patente_desp:
            if len(patente_desp) != 6:
                st.error("❌ La patente debe poseer exactamente 6 caracteres.")
            else:
                existe_en_sistema = patente_desp in st.session_state.df_activas["Patente"].values if not st.session_state.df_activas.empty else False
                
                if existe_en_sistema:
                    st.info("💡 Datos detectados en el sistema. Modifique si cambió el chofer:")
                    fila_previo = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_desp].iloc[0]
                    empresa_def = fila_previo["Empresa"]
                    chofer_def = fila_previo["Chofer"]
                    rut_def = fila_previo["RUT"]
                else:
                    st.warning("⚠️ Patente Directa (No registra paso por Inversa). Ingrese datos completos:")
                    empresa_def, chofer_def, rut_def = "", "", ""
                    
                with st.form(f"form_despacho_ingreso_{st.session_state.limpiar_despacho}"):
                    empresa_f = st.text_input("🏢 Empresa de Transporte", value=empresa_def).upper().strip()
                    chofer_f = st.text_input("👤 Nombre y apellido del Chofer", value=chofer_def).upper().strip()
                    rut_f = st.text_input("🆔 RUT del Chofer", value=rut_def, max_chars=10, help="Largo permitido entre 9 y 10 caracteres").upper().strip()
                    
                    btn_confirmar_despacho = st.form_submit_button("📥 Registrar Entrada a Carga")
                    
                if btn_confirmar_despacho:
                    if not empresa_f or not chofer_f or not rut_f:
                        st.error("❌ Todos los campos son mandatorios.")
                    elif len(rut_f) < 9 or len(rut_f) > 10:
                        st.error(f"❌ El RUT ingresado tiene {len(rut_f)} caracteres. Debe tener entre 9 y 10 caracteres.")
                    else:
                        if not existe_en_sistema:
                            nuevo_reg_dir = pd.DataFrame([{
                                "Patente": patente_desp, "Empresa": empresa_f, "Chofer": chofer_f, "RUT": rut_f,
                                "H1_Llegada_Inversa": "", "H2_Salida_Inversa": "",
                                "H3_Llegada_Despacho": ahora_actual.isoformat(), "H4_Salida_Despacho": "",
                                "Ruta_Auditada": "", "Estado": "En Despacho (Cargando)"
                            }])
                            st.session_state.df_activas = pd.concat([st.session_state.df_activas, nuevo_reg_dir], ignore_index=True)
                        else:
                            idx = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_desp].index[0]
                            st.session_state.df_activas.at[idx, "Empresa"] = empresa_f
                            st.session_state.df_activas.at[idx, "Chofer"] = chofer_f
                            st.session_state.df_activas.at[idx, "RUT"] = rut_f
                            st.session_state.df_activas.at[idx, "H3_Llegada_Despacho"] = ahora_actual.isoformat()
                            st.session_state.df_activas.at[idx, "Estado"] = "En Despacho (Cargando)"
                        
                        guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                        st.success(f"✅ Camión {patente_desp} posicionado en Despacho.")
                        st.session_state.limpiar_despacho += 1
                        time.sleep(1.5)
                        st.rerun()

# =====================================================================
# PESTAÑA 4: SALIDA DESPACHO
# =====================================================================
if tab4:
    with tab4:
        st.header("🚪 Control de Salida Despacho")
        
        lista_cargando = []
        if not st.session_state.df_activas.empty:
            lista_cargando = st.session_state.df_activas[st.session_state.df_activas["Estado"] == "En Despacho (Cargando)"]["Patente"].tolist()
        
        with st.form(f"form_salida_final_{st.session_state.limpiar_salida}"):
            patente_salida_final = st.selectbox("Seleccione Patente que termina Carga:", [""] + lista_cargando)
            ruta_aud = st.text_input("📋 Ingrese Número de Ruta Auditada:").upper().strip()
            
            btn_finalizar_viaje = st.form_submit_button("🏁 Confirmar Salida y Archivar Viaje")
            
        if btn_finalizar_viaje:
            if not patente_salida_final:
                st.error("❌ Seleccione una patente de la lista.")
            elif not ruta_aud:
                st.error("❌ Ingrese el número de la ruta auditada corporativa.")
            else:
                # Procesar y archivar
                fila_viaje = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_salida_final].iloc[0].copy()
                st.session_state.df_activas = st.session_state.df_activas[st.session_state.df_activas["Patente"] != patente_salida_final]
                
                h1 = datetime.datetime.fromisoformat(fila_viaje["H1_Llegada_Inversa"]) if pd.notna(fila_viaje["H1_Llegada_Inversa"]) and fila_viaje["H1_Llegada_Inversa"] != "" else None
                h2 = datetime.datetime.fromisoformat(fila_viaje["H2_Salida_Inversa"]) if pd.notna(fila_viaje["H2_Salida_Inversa"]) and fila_viaje["H2_Salida_Inversa"] != "" else None
                h3 = datetime.datetime.fromisoformat(fila_viaje["H3_Llegada_Despacho"])
                h4 = ahora_actual
                
                t_retorno = (h2 - h1).total_seconds() / 60 if h1 and h2 else None
                t_carga = (h4 - h3).total_seconds() / 60
                
                num_semana = h3.isocalendar()[1]
                meses_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                nombre_mes = meses_es[h3.month]
                
                nuevo_historial = pd.DataFrame([{
                    "Fecha": h3.strftime('%d-%m-%Y'),
                    "Semana": f"Semana {num_semana}",
                    "Mes": nombre_mes,
                    "Empresa": fila_viaje["Empresa"], "Patente": patente_salida_final,
                    "Chofer": fila_viaje["Chofer"], "RUT": fila_viaje["RUT"], "Ruta Auditada": ruta_aud,
                    "Ingreso Inversa": h1.strftime('%H:%M:%S') if h1 else "N/A",
                    "Salida Inversa": h2.strftime('%H:%M:%S') if h2 else "N/A",
                    "Ingreso Despacho": h3.strftime('%H:%M:%S'),
                    "Salida Despacho": h4.strftime('%H:%M:%S'),
                    "T. Retorno (Descarga)": formatear_a_cronometro(t_retorno) if t_retorno is not None else "No registra",
                    "T. Despacho (Carga)": formatear_a_cronometro(t_carga)
                }])
                
                st.session_state.df_historial = pd.concat([st.session_state.df_historial, nuevo_historial], ignore_index=True)
                
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                guardar_datos_cloud(st.session_state.df_historial, "historial_final")
                
                st.success(f"✅ Registro de la patente {patente_salida_final} completado con éxito.")
                st.session_state.limpiar_salida += 1
                time.sleep(1.5)
                st.rerun()

# =====================================================================
# PESTAÑA 5: MONITOREO Y KPIS
# =====================================================================
if tab5:
    with tab5:
        st.header("📊 Monitor Flujo de Ingresos y Salidas")
        
        st.subheader("🚚 Vehículos registrados actualmente en patio")
        if not st.session_state.df_activas.empty:
            datos_tabla_activas = []
            for _, fila in st.session_state.df_activas.iterrows():
                h1_str = fila["H1_Llegada_Inversa"]
                h2_str = fila["H2_Salida_Inversa"]
                h3_str = fila["H3_Llegada_Despacho"]
                
                if pd.notna(h1_str) and h1_str != "":
                    h1_dt = datetime.datetime.fromisoformat(h1_str)
                    h_ingreso_inv = h1_dt.strftime('%H:%M:%S')
                    fin_inv = datetime.datetime.fromisoformat(h2_str) if (pd.notna(h2_str) and h2_str != "") else ahora_actual
                    str_inversa = formatear_a_cronometro((fin_inv - h1_dt).total_seconds() / 60)
                else:
                    h_ingreso_inv = "N/A"
                    str_inversa = "No pasó por Inv."
                    
                if pd.notna(h2_str) and h2_str != "":
                    h2_dt = datetime.datetime.fromisoformat(h2_str)
                    fin_espera = datetime.datetime.fromisoformat(h3_str) if (pd.notna(h3_str) and h3_str != "") else ahora_actual
                    str_espera = formatear_a_cronometro((fin_espera - h2_dt).total_seconds() / 60)
                else:
                    str_espera = "En proceso Inversa"
                    
                if pd.notna(h3_str) and h3_str != "":
                    h3_dt = datetime.datetime.fromisoformat(h3_str)
                    h_ingreso_desp = h3_dt.strftime('%H:%M:%S')
                    str_despacho = formatear_a_cronometro((ahora_actual - h3_dt).total_seconds() / 60)
                else:
                    h_ingreso_desp = "Pendiente"
                    str_despacho = "Esperando andén..."
                    
                datos_tabla_activas.append({
                    "Patente": fila["Patente"], "Empresa": fila["Empresa"], "Chofer": fila["Chofer"], "Estado Actual": fila["Estado"],
                    "H. Ingreso Inversa": h_ingreso_inv, "Tiempo en Log. Inversa": str_inversa,
                    "Tiempo Espera Despacho": str_espera,
                    "H. Ingreso Despacho": h_ingreso_desp, "Tiempo en Despacho": str_despacho
                })
            st.dataframe(pd.DataFrame(datos_tabla_activas), use_container_width=True)
        else:
            st.info("No hay vehículos operando en el patio en este instante.")
            
        st.markdown("---")
        
        st.subheader("📋 Consolidado Histórico de Viajes (Archivados)")
        if not st.session_state.df_historial.empty:
            st.session_state.df_historial["Mes"] = st.session_state.df_historial["Mes"].replace(["Mayonesa", "mayonesa"], "Mayo")
            
            st.write("🔍 **Herramientas de Filtrado de Reportería**")
            col_f1, col_f2, col_f3 = st.columns(3)
            
            with col_f1:
                filtro_fecha = st.selectbox("Filtrar por Fecha:", ["Todos"] + sorted(list(st.session_state.df_historial["Fecha"].unique())))
            with col_f2:
                filtro_semana = st.selectbox("Filtrar por Semana:", ["Todos"] + sorted(list(st.session_state.df_historial["Semana"].unique())))
            with col_f3:
                filtro_mes = st.selectbox("Filtrar por Mes:", ["Todos"] + sorted(list(st.session_state.df_historial["Mes"].unique())))
                
            df_filtrado = st.session_state.df_historial.copy()
            if filtro_fecha != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Fecha"] == filtro_fecha]
            if filtro_semana != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Semana"] == filtro_semana]
            if filtro_mes != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Mes"] == filtro_mes]
                
            st.dataframe(df_filtrado, use_container_width=True)
        else:
            st.info("Los KPIs e historial se activarán cuando un camión complete su ciclo de salida en el andén.")

# =====================================================================
# PANEL GENERADOR DE URLS (ACCESIBLE EXCLUSIVAMENTE PARA EL ADMINISTRADOR)
# =====================================================================
if vista_url == "admin":
    st.markdown("---")
    with st.expander("🔗 PANEL SUPERVISOR: Generador de Enlaces para Equipos", expanded=True):
        st.write("Copia los enlaces completos para compartirlos con el personal o guardarlos en sus favoritos:")
        
        base_ip = "http://10.239.71.178:8501/"
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**🔄 Logística Inversa**")
            st.code(f"{base_ip}?vista=inversa", language="text")
            st.caption("Muestra pestañas: 1, 2 y 5")
        with col2:
            st.success("**📦 Equipo Despacho**")
            st.code(f"{base_ip}?vista=despacho", language="text")
            st.caption("Muestra pestañas: 3, 4 y 5")
        with col3:
            st.warning("**🖥️ Equipo Monitores**")
            st.code(f"{base_ip}?vista=monitoreo", language="text")
            st.caption("Muestra pestaña: 5 sola")