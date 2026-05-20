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
        if not df_act.empty:
            lista_inv = df_act[df_act["Estado"] == "En Logística Inversa"]["Patente"].tolist()
        else:
            lista_inv = []
            
        patente_salida_inv = st.selectbox("Seleccione Patente:", [""] + lista_inv, key="sel_salida_inv")
        if st.button("📤 Confirmar Salida"):
            if patente_salida_inv:
                idx = df_act[df_act["Patente"] == patente_salida_inv].index[0]
                df_act.at[idx, "H2_Salida_Inversa"] = ahora_actual.strftime('%Y-%m-%d %H:%M:%S')
                df_act.at[idx, "Estado"] = "Esperando Despacho"
                guardar_datos_cloud(df_act, "patentes_activas")
                st.success("✅ Salida confirmada.")
                time.sleep(1)
                st.rerun()

# =====================================================================
# PESTAÑA 3: INGRESO DESPACHO
# =====================================================================
if tab3:
    with tab3:
        st.header("📦 Registro de Ingreso a Despacho")
        patente_desp = st.text_input(
            "🚚 Digite Patente para Despacho:", 
            max_chars=6, 
            key=f"txt_desp_{st.session_state.limpiar_despacho}"
        ).upper().strip()
        
        df_act = st.session_state.df_activas
        
        if len(patente_desp) == 6:
            if not df_act.empty and patente_desp in df_act["Patente"].values:
                fila = df_act[df_act["Patente"] == patente_desp].iloc[0]
                
                if fila["Estado"] == "En Logística Inversa":
                    st.error("⛔ RESTRICCIÓN: Este vehículo no ha salido de Inversa.")
                elif fila["Estado"] == "En Despacho (Cargando)":
                    st.info("✅ Esta patente ya está en proceso de carga.")
                else:
                    with st.form("form_despacho_inner"):
                        st.write("### Datos de Vehículo Habilitado")
                        empresa_f = st.text_input("🏢 Empresa", value=fila["Empresa"]).upper().strip()
                        st.caption(f"👤 Conductor Original Inversa: {fila['Chofer']} | RUT: {fila['RUT']}")
                        
                        chofer_f = st.text_input("👤 Conductor Despacho:", value=fila["Chofer"]).upper().strip()
                        rut_f = st.text_input("🆔 RUT Despacho:", value=fila["RUT"]).strip()
                        
                        if st.form_submit_button("📥 Registrar Entrada a Carga"):
                            rut_nuevo_limpio = formatear_rut(rut_f)
                            if len(rut_nuevo_limpio) < 9:
                               st.error("❌ El RUT no es válido.")
                            else:
                                idx = df_act[df_act["Patente"] == patente_desp].index[0]
                                df_act.at[idx, "Empresa"] = empresa_f
                                
                                c_original = str(fila["Chofer"]).upper().strip()
                                r_original = formatear_rut(fila["RUT"])
                                
                                if chofer_f != c_original or rut_nuevo_limpio != r_original:
                                    h1 = parse_fecha(fila["H1_Llegada_Inversa"])
                                    h2 = parse_fecha(fila["H2_Salida_Inversa"])
                                    if h1 and h2:
                                        t_retorno = (h2 - h1).total_seconds() / 60
                                    else:
                                        t_retorno = 0.0
                                    
                                    meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                                             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

                                    dict_hist_c1 = {
                                        "Fecha": ahora_actual.strftime('%d-%m-%Y'),
                                        "Semana": f"Semana {ahora_actual.isocalendar()[1]}",
                                        "Mes": meses[ahora_actual.month],
                                        "Empresa": empresa_f,
                                        "Patente": patente_desp,
                                        "Chofer": c_original,
                                        "RUT": r_original,
                                        "Ruta Auditada": f"CAMBIO CONDUCTOR A {chofer_f}",
                                        "Ingreso Inversa": h1.strftime('%H:%M:%S') if h1 else "N/A",
                                        "Salida Inversa": h2.strftime('%H:%M:%S') if h2 else "N/A",
                                        "Ingreso Despacho": "N/A",
                                        "Salida Despacho": "N/A",
                                        "T. Retorno (Descarga)": formatear_a_cronometro(t_retorno) if h1 else "N/A",
                                        "T. Despacho (Carga)": "N/A",
                                        "Minutos_Carga_Raw": round(t_retorno, 1),
                                        "Tipo de Cierre": "Cambio Conductor",
                                        "Chofer 2": chofer_f,
                                        "RUT Chofer 2": rut_nuevo_limpio
                                    }
                                    agregar_fila_historial_rapido(dict_hist_c1)
                                    df_act.at[idx, "Chofer_2"] = c_original
                                    df_act.at[idx, "RUT_2"] = r_original
                                
                                df_act.at[idx, "Chofer"] = chofer_f
                                df_act.at[idx, "RUT"] = rut_nuevo_limpio
                                df_act.at[idx, "H3_Llegada_Despacho"] = ahora_actual.strftime('%Y-%m-%d %H:%M:%S')
                                df_act.at[idx, "Estado"] = "En Despacho (Cargando)"
                                
                                guardar_datos_cloud(df_act, "patentes_activas")
                                st.success("✅ Posicionado en Despacho con éxito.")
                                st.session_state.limpiar_despacho += 1
                                time.sleep(1)
                                st.rerun()
            else:
                st.warning("⚠️ Patente sin registro previo en Inversa.")
                with st.form("form_ingreso_directo"):
                    st.write("### 🚨 Ingreso Directo a Patio")
                    empresa_directa = st.text_input("🏢 Empresa").upper().strip()
                    chofer_directo = st.text_input("👤 Chofer").upper().strip()
                    rut_directo = st.text_input("🆔 RUT").strip()
                    
                    if st.form_submit_button("💾 Ingreso Directo"):
                        rut_d_limpio = formatear_rut(rut_directo)
                        if not empresa_directa or not chofer_directo or not rut_d_limpio:
                            st.error("❌ Todos los campos obligatorios.")
                        else:
                            nuevo_registro = pd.DataFrame([{
                                "Patente": patente_desp, 
                                "Empresa": empresa_directa, 
                                "Chofer": chofer_directo, 
                                "RUT": rut_d_limpio,
                                "H1_Llegada_Inversa": "", 
                                "H2_Salida_Inversa": "",
                                "H3_Llegada_Despacho": "", 
                                "H4_Salida_Despacho": "",
                                "Ruta_Auditada": "", 
                                "Estado": "Esperando Despacho", 
                                "Chofer_2": "", 
                                "RUT_2": ""
                            }])
                            st.session_state.df_activas = pd.concat([df_act, nuevo_registro], ignore_index=True)
                            guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                            st.success("✅ Ingresado. Digite patente de nuevo.")
                            time.sleep(1)
                            st.rerun()

# =====================================================================
# PESTAÑA 4: SALIDA DESPACHO
# =====================================================================
if tab4:
    with tab4:
        st.header("🚪 Control de Salida Despacho")
        df_act = st.session_state.df_activas
        if not df_act.empty:
            lista_cargando = df_act[df_act["Estado"] == "En Despacho (Cargando)"]["Patente"].tolist()
        else:
            lista_cargando = []
            
        with st.form(f"form_salida_{st.session_state.limpiar_salida}"):
            patente_final = st.selectbox("Patente que termina Carga:", [""] + lista_cargando)
            ruta_aud = st.text_input("📋 Ruta Auditada:").upper().strip()
            
            if st.form_submit_button("🏁 Confirmar Salida y Archivar"):
                if patente_final and ruta_aud:
                    fila_viaje = df_act[df_act["Patente"] == patente_final].iloc[0].copy()
                    st.session_state.df_activas = df_act[df_act["Patente"] != patente_final]
                    
                    h1 = parse_fecha(fila_viaje["H1_Llegada_Inversa"])
                    h2 = parse_fecha(fila_viaje["H2_Salida_Inversa"])
                    h3 = parse_fecha(fila_viaje["H3_Llegada_Despacho"])
                    h4 = ahora_actual
                    
                    t_retorno = (h2 - h1).total_seconds() / 60 if h1 and h2 else 0.0
                    t_carga = (h4 - h3).total_seconds() / 60 if h3 else 0.0
                    
                    meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    
                    dict_hist_final = {
                        "Fecha": h4.strftime('%d-%m-%Y'),
                        "Semana": f"Semana {h4.isocalendar()[1]}",
                        "Mes": meses[h4.month],
                        "Empresa": fila_viaje["Empresa"],
                        "Patente": patente_final,
                        "Chofer": fila_viaje["Chofer"],
                        "RUT": formatear_rut(fila_viaje["RUT"]),
                        "Ruta Auditada": ruta_aud,
                        "Ingreso Inversa": h1.strftime('%H:%M:%S') if h1 else "N/A",
                        "Salida Inversa": h2.strftime('%H:%M:%S') if h2 else "N/A",
                        "Ingreso Despacho": h3.strftime('%H:%M:%S') if h3 else "N/A",
                        "Salida Despacho": h4.strftime('%H:%M:%S'),
                        "T. Retorno (Descarga)": formatear_a_cronometro(t_retorno) if h1 else "N/A",
                        "T. Despacho (Carga)": formatear_a_cronometro(t_carga),
                        "Minutos_Carga_Raw": round(t_retorno + t_carga, 1),
                        "Tipo de Cierre": "Normal",
                        "Chofer 2": fila_viaje["Chofer_2"],
                        "RUT Chofer 2": fila_viaje["RUT_2"]
                    }
                    
                    agregar_fila_historial_rapido(dict_hist_final)
                    guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                    
                    st.success("✅ Viaje archivado exitosamente.")
                    st.session_state.limpiar_salida += 1
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Rellene todos los campos.")

# =====================================================================
# PESTAÑA 5: MONITOREO Y KPIS
# =====================================================================
if tab5:
    with tab5:
        st.header("📊 Monitor de Patio y Estadísticas")
        col_tit_mon, col_btn_mon = st.columns([8, 2])
        with col_tit_mon: 
            st.subheader("🚚 Vehículos en CD (Activos)")
        with col_btn_mon:
            if st.button("🔄 Actualizar Tiempos"): 
                st.rerun()
                
        df_act = st.session_state.df_activas
        if not df_act.empty:
            df_en_patio = df_act.copy()
            ing_inv, sal_inv, ing_desp, sal_desp = [], [], [], []
            t_retornos, t_cargas = [], []
            
            for _, row in df_en_patio.iterrows():
                h1 = parse_fecha(row["H1_Llegada_Inversa"])
                h2 = parse_fecha(row["H2_Salida_Inversa"])
                h3 = parse_fecha(row["H3_Llegada_Despacho"])
                h4 = parse_fecha(row["H4_Salida_Despacho"])
                
                ing_inv.append(h1.strftime('%H:%M:%S') if h1 else "N/A")
                sal_inv.append(h2.strftime('%H:%M:%S') if h2 else "N/A")
                ing_desp.append(h3.strftime('%H:%M:%S') if h3 else "N/A")
                sal_desp.append(h4.strftime('%H:%M:%S') if h4 else "N/A")
                
                if h1 and h2: t_ret = (h2 - h1).total_seconds() / 60
                elif h1: t_ret = (ahora_actual - h1).total_seconds() / 60
                else: t_ret = None
                t_retornos.append(formatear_a_cronometro(t_ret) if t_ret is not None else "N/A")
                
                if h3 and h4: t_carg = (h4 - h3).total_seconds() / 60
                elif h3: t_carg = (ahora_actual - h3).total_seconds() / 60
                else: t_carg = None
                t_cargas.append(formatear_a_cronometro(t_carg) if t_carg is not None else "N/A")
            
            df_en_patio["Ingreso Inversa"] = ing_inv
            df_en_patio["Salida Inversa"] = sal_inv
            df_en_patio["T. Retorno (Descarga)"] = t_retornos
            df_en_patio["Ingreso Despacho"] = ing_desp
            df_en_patio["Salida Despacho"] = sal_desp
            df_en_patio["T. Despacho (Carga)"] = t_cargas
            
            cols_mostrar = [
                "Patente", "Empresa", "Chofer", "Estado", 
                "Ingreso Inversa", "Salida Inversa", "T. Retorno (Descarga)", 
                "Ingreso Despacho", "Salida Despacho", "T. Despacho (Carga)"
            ]
            st.dataframe(df_en_patio[cols_mostrar], use_container_width=True)
        else:
            st.info("No hay vehículos en CD.")
            
        st.markdown("---")
        st.subheader("🔍 Historial y Reportería")
        
        df_hist = st.session_state.df_historial
        if not df_hist.empty:
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                lista_fechas = ["Todos"] + sorted(list(df_hist["Fecha"].dropna().unique()))
                filtro_fecha = st.selectbox("Filtrar por Fecha:", lista_fechas)
            with col_f2:
                lista_semanas = ["Todos"] + sorted(list(df_hist["Semana"].dropna().unique()))
                filtro_semana = st.selectbox("Filtrar por Semana:", lista_semanas)
            with col_f3:
                lista_meses = ["Todos"] + sorted(list(df_hist["Mes"].dropna().unique()))
                filtro_mes = st.selectbox("Filtrar por Mes:", lista_meses)
                
            df_filtrado = df_hist.copy()
            if filtro_fecha != "Todos": 
                df_filtrado = df_filtrado[df_filtrado["Fecha"] == filtro_fecha]
            if filtro_semana != "Todos": 
                df_filtrado = df_filtrado[df_filtrado["Semana"] == filtro_semana]
            if filtro_mes != "Todos": 
                df_filtrado = df_filtrado[df_filtrado["Mes"] == filtro_mes]
                
            if df_filtrado.empty:
                st.warning("⚠️ No hay datos con esos filtros.")
            else:
                st.subheader("📋 Consolidado Histórico")
                df_mostrar = df_filtrado.iloc[::-1].drop(columns=["Minutos_Carga_Raw"], errors='ignore')
                st.dataframe(df_mostrar, use_container_width=True)
                
                st.markdown("---")
                st.subheader("📈 Estadía Promedio CD")
                if "T. Retorno (Descarga)" in df_filtrado.columns and "T. Despacho (Carga)" in df_filtrado.columns:
                    df_stats = df_filtrado.copy()
                    df_stats['Min_Inv'] = df_stats['T. Retorno (Descarga)'].apply(cronometro_a_minutos)
                    df_stats['Min_Desp'] = df_stats['T. Despacho (Carga)'].apply(cronometro_a_minutos)
                    df_stats['Min_Total'] = df_stats['Min_Inv'] + df_stats['Min_Desp']
                    df_vehiculos = df_stats[df_stats["Tipo de Cierre"] != "Cambio Conductor"]
                    
                    st.markdown("#### 🏢 Promedio Por Empresa")
                    df_emp = df_vehiculos.groupby("Empresa")[["Min_Inv", "Min_Desp", "Min_Total"]].mean().reset_index()
                    df_emp["Promedio Inversa"] = df_emp["Min_Inv"].apply(formatear_a_cronometro)
                    df_emp["Promedio Despacho"] = df_emp["Min_Desp"].apply(formatear_a_cronometro)
                    df_emp["Promedio Total CD"] = df_emp["Min_Total"].apply(formatear_a_cronometro)
                    st.dataframe(df_emp[["Empresa", "Promedio Inversa", "Promedio Despacho", "Promedio Total CD"]], use_container_width=True)
                    
                    st.markdown("#### 👨‍✈️ Promedio Por Chofer")
                    df_chof = df_stats.groupby("Chofer")[["Min_Inv", "Min_Desp", "Min_Total"]].mean().reset_index()
                    df_chof["Promedio Inversa"] = df_chof["Min_Inv"].apply(formatear_a_cronometro)
                    df_chof["Promedio Despacho"] = df_chof["Min_Desp"].apply(formatear_a_cronometro)
                    df_chof["Promedio Total CD"] = df_chof["Min_Total"].apply(formatear_a_cronometro)
                    st.dataframe(df_chof[["Chofer", "Promedio Inversa", "Promedio Despacho", "Promedio Total CD"]], use_container_width=True)
        else:
            st.info("No hay datos históricos.")

# =====================================================================
# PANEL ADMINISTRADOR
# =====================================================================
if vista_url == "admin":
    st.markdown("---")
    with st.expander("🔗 PANEL SUPERVISOR", expanded=True):
        if st.button("⚠️ Forzar Cierre de Procesos Inconclusos", type="primary"):
            df_act = st.session_state.df_activas
            if not df_act.empty:
                for _, fila_viaje in df_act.iterrows():
                    h1 = parse_fecha(fila_viaje["H1_Llegada_Inversa"])
                    h2 = parse_fecha(fila_viaje["H2_Salida_Inversa"])
                    h3 = parse_fecha(fila_viaje["H3_Llegada_Despacho"])
                    h4 = ahora_actual
                    t_retorno = (h2 - h1).total_seconds() / 60 if h1 and h2 else 0.0
                    t_carga = (h4 - h3).total_seconds() / 60 if h3 else 0.0
                    base_date = h3 if h3 else (h1 if h1 else ahora_actual)
                    
                    meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    
                    dict_forzado = {
                        "Fecha": base_date.strftime('%d-%m-%Y'),
                        "Semana": f"Semana {base_date.isocalendar()[1]}",
                        "Mes": meses[base_date.month],
                        "Empresa": fila_viaje["Empresa"],
                        "Patente": fila_viaje["Patente"],
                        "Chofer": fila_viaje["Chofer"],
                        "RUT": fila_viaje["RUT"],
                        "Ruta Auditada": "CIERRE FORZADO",
                        "Ingreso Inversa": h1.strftime('%H:%M:%S') if h1 else "N/A",
                        "Salida Inversa": h2.strftime('%H:%M:%S') if h2 else "N/A",
                        "Ingreso Despacho": h3.strftime('%H:%M:%S') if h3 else "N/A",
                        "Salida Despacho": h4.strftime('%H:%M:%S'),
                        "T. Retorno (Descarga)": formatear_a_cronometro(t_retorno) if h1 and h2 else "N/A",
                        "T. Despacho (Carga)": formatear_a_cronometro(t_carga) if h3 else "N/A",
                        "Minutos_Carga_Raw": round(t_retorno + t_carga, 1),
                        "Tipo de Cierre": "Forzado",
                        "Chofer 2": fila_viaje["Chofer_2"],
                        "RUT Chofer 2": fila_viaje["RUT_2"]
                    }
                    agregar_fila_historial_rapido(dict_forzado)
                
                st.session_state.df_activas = pd.DataFrame(columns=df_act.columns)
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                st.success("🚨 Cerrados de forma forzada.")
                time.sleep(1.5)
                st.rerun()
            else: 
                st.warning("No hay procesos en patio.")
