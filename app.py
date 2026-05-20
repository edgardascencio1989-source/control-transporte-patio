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
        
        # 1. Verificar si existen los secretos en Streamlit
        if "json_data" not in st.secrets:
            st.error("❌ ERROR CRÍTICO: No se encontró la variable 'json_data' en los Secrets de Streamlit. Revisa la pestaña Ajustes de tu App.")
            st.stop()
            return None
            
        # 2. Intentar decodificar el JSON guardado en Secrets
        try:
            creds_dict = json.loads(st.secrets["json_data"])
        except Exception as json_err:
            st.error(f"❌ ERROR DE FORMATO JSON: El texto guardado en Secrets no es válido. Detalles: {str(json_err)}")
            st.stop()
            return None
        
        # Corrección interna obligatoria para la clave privada
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Conexión nativa y segura usando la memoria interna protegida de Streamlit
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        try:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
        except Exception as spread_err:
            st.error(f"❌ ERROR DE ACCESO: El bot ({creds_dict.get('client_email')}) no pudo entrar a la planilla. Detalles: {str(spread_err)}")
            st.stop()
            return None
            
        try:
            sheet = spreadsheet.worksheet(pestaña_nombre)
            return sheet
        except Exception as work_err:
            st.error(f"❌ ERROR DE PESTAÑA: Archivo abierto, pero no existe la pestaña '{pestaña_nombre}'. Detalles: {str(work_err)}")
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
            # SOLUCIÓN INT64: Se convierte todo el Dataframe a texto antes de enviar
            df_enviar = df.fillna("").astype(str)
            valores_enviar = [df_enviar.columns.values.tolist()] + df_enviar.values.tolist()
            sheet.update(valores_enviar)
            return True
        except Exception as e:
            st.error(f"❌ Error crítico de Google Sheets al intentar guardar en '{pestaña_nombre}': {str(e)}")
            st.stop()
            return False
    return False

# SOLUCIÓN DE VELOCIDAD: Añadir una fila al historial en vez de recargar toda la base de datos
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
    subtitulo_pantalla = "🖥️ Módulo de Visualización: EQUIPO MONITORES"
else:
    mostrar_tab1, mostrar_tab2, mostrar_tab3, mostrar_tab4, mostrar_tab5 = True, True, True, True, True
    titulos_pestañas = [
        "📥 1. Ingreso Logística Inversa", "📤 2. Salida de Inversa", 
        "📦 3. Ingreso a despacho", "🚪 4. Salida Despacho", "📊 5. Monitoreo y KPIS"
    ]
    subtitulo_pantalla = "👑 Módulo Global: ADMINISTRACIÓN"

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
                        "Ruta_Auditada": "", "Estado": "En Logística Inversa", "Chofer_2": "", "RUT_2": ""
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
# PESTAÑA 3: INGRESO DESPACHO (CON FILTRADO ANTI-DUPLICADOS)
# =====================================================================
if tab3:
    with tab3:
        st.header("📦 Registro de Ingreso a Despacho")
        
        patente_desp = st.text_input("🚚 Digite Patente para Despacho:", max_chars=6, key=f"txt_desp_{st.session_state.limpiar_despacho}").upper().strip()
        
        if len(patente_desp) == 6:
            # SOLUCIÓN DE SINTAXIS: Operador 'and' en lugar de '&&'
            if not st.session_state.df_activas.empty and patente_desp in st.session_state.df_activas["Patente"].values:
                fila = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_desp].iloc[0]
                
                if fila["Estado"] == "En Logística Inversa":
                    st.error(
                        "⛔ RESTRICCIÓN ACTIVA: Este vehículo no ha registrado su SALIDA desde Logística "
                        "Inversa (Módulo 2). El registro en Despacho está completamente bloqueado."
                    )
                elif fila["Estado"] == "En Despacho (Cargando)":
                    st.info(f"✅ La patente {patente_desp} ya fue ingresada a Despacho exitosamente. Está en proceso de carga.")
                else:
                    with st.form("form_despacho_inner"):
                        st.write("### Datos de Vehículo Habilitado")
                        empresa_f = st.text_input("🏢 Empresa", value=fila["Empresa"]).upper().strip()
                        st.caption(f"👤 Conductor Original de Inversa: {fila['Chofer']} | RUT: {fila['RUT']}")
                        
                        chofer_f = st.text_input("👤 Nombre del Conductor en Despacho:", value=fila["Chofer"]).upper().strip()
                        rut_f = st.text_input("🆔 RUT del Conductor en Despacho:", value=fila["RUT"], max_chars=10).upper().strip()
                        
                        if st.form_submit_button("📥 Registrar Entrada a Carga"):
                            if len(rut_f) < 9 or len(rut_f) > 10:
                               st.error("❌ El RUT debe tener entre 9 y 10 caracteres.")
                            else:
                                idx = st.session_state.df_activas[st.session_state.df_activas["Patente"] == patente_desp].index[0]
                                st.session_state.df_activas.at[idx, "Empresa"] = empresa_f
                                
                                # SOLUCIÓN DUPLICADOS: Limpieza estricta antes de comparar
                                c_original = str(fila["Chofer"]).upper().strip()
                                r_original = str(fila["RUT"]).upper().strip()
                                c_nuevo = chofer_f.upper().strip()
                                r_nuevo = rut_f.upper().strip()

                                if c_nuevo != c_original or r_nuevo != r_original:
                                    h1_str = fila["H1_Llegada_Inversa"]
                                    h2_str = fila["H2_Salida_Inversa"]
                                    h1 = datetime.datetime.fromisoformat(h1_str) if pd.notna(h1_str) and h1_str else None
                                    h2 = datetime.datetime.fromisoformat(h2_str) if pd.notna(h2_str) and h2_str else None
                                    t_retorno = (h2 - h1).total_seconds() / 60 if h1 and h2 else 0.0

                                    dict_hist_c1 = {
                                        "Fecha": ahora_actual.strftime('%d-%m-%Y'),
                                        "Semana": f"Semana {ahora_actual.isocalendar()[1]}",
                                        "Mes": ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][ahora_actual.month],
                                        "Empresa": empresa_f, "Patente": patente_desp, "Chofer": fila["Chofer"], "RUT": fila["RUT"],
                                        "Ruta Auditada": f"CAMBIO CONDUCTOR (ENTREGA A {chofer_f})",
                                        "Ingreso Inversa": h1.strftime('%H:%M:%S') if h1 else "N/A",
                                        "Salida Inversa": h2.strftime('%H:%M:%S') if h2 else "N/A",
                                        "Ingreso Despacho": "N/A", "Salida Despacho": "N/A",
                                        "T. Retorno (Descarga)": formatear_a_cronometro(t_retorno) if h1 else "N/A",
                                        "T. Despacho (Carga)": "N/A",
                                        "Minutos_Carga_Raw": round(t_retorno, 1),
                                        "Tipo de Cierre": "Cambio Conductor",
                                        "Chofer 2": chofer_f, "RUT Chofer 2": rut_f
                                    }
                                    agregar_fila_historial_rapido(dict_hist_c1)

                                    st.session_state.df_activas.at[idx, "Chofer_2"] = fila["Chofer"]
                                    st.session_state.df_activas.at[idx, "RUT_2"] = fila["RUT"]
                                
                                st.session_state.df_activas.at[idx, "Chofer"] = chofer_f
                                st.session_state.df_activas.at[idx, "RUT"] = rut_f
                                st.session_state.df_activas.at[idx, "H3_Llegada_Despacho"] = ahora_actual.isoformat()
                                st.session_state.df_activas.at[idx, "Estado"] = "En Despacho (Cargando)"
                                
                                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                                st.success("✅ Posicionado en Despacho con éxito.")
                                st.session_state.limpiar_despacho += 1
                                time.sleep(1)
                                st.rerun()
            else:
                st.warning("⚠️ Esta patente no registra ingreso previo en Logística Inversa. Se abrirá el formulario de registro obligatorio.")
                with st.form("form_ingreso_directo_contingencia"):
                    st.write("### 🚨 Formulario de Ingreso Directo a Patio")
                    empresa_directa = st.text_input("🏢 Empresa de Transporte").upper().strip()
                    chofer_directo = st.text_input("👤 Nombre y apellido del Chofer").upper().strip()
                    rut_directo = st.text_input("🆔 RUT del Chofer", max_chars=10).upper().strip()
                    
                    if st.form_submit_button("💾 Registrar Ingreso Completo Directo"):
                        if not empresa_directa or not chofer_directo or not rut_directo:
                            st.error("❌ Todos los campos son obligatorios.")
                        elif len(rut_directo) < 9 or len(rut_directo) > 10:
                            st.error("❌ El RUT debe tener entre 9 y 10 caracteres.")
                        else:
                            nuevo_registro = pd.DataFrame([{
                                "Patente": patente_desp, "Empresa": empresa_directa, "Chofer": chofer_directo, "RUT": rut_directo,
                                "H1_Llegada_Inversa": "", "H2_Salida_Inversa": "",
                                "H3_Llegada_Despacho": "", "H4_Salida_Despacho": "",
                                "Ruta_Auditada": "", "Estado": "Esperando Despacho", "Chofer_2": "", "RUT_2": ""
                            }])
                            st.session_state.df_activas = pd.concat([st.session_state.df_activas, nuevo_registro], ignore_index=True)
                            guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                            st.success("✅ Vehículo ingresado al sistema. Digite de nuevo la patente para posicionar en Despacho.")
                            time.sleep(1)
                            st.rerun()
        elif len(patente_desp) > 0:
            st.caption("Escriba el largo exacto de la patente (6 dígitos).")

# =====================================================================
# PESTAÑA 4: SALIDA DESPACHO
# =====================================================================
if tab4:
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
                    h3 = datetime.datetime.fromisoformat(fila_viaje["H3_Llegada_Despacho"]) if pd.notna(fila_viaje["H3_Llegada_Despacho"]) and fila_viaje["H3_Llegada_Despacho"] else ahora_actual
                    h4 = ahora_actual
                    
                    t_retorno = (h2 - h1).total_seconds() / 60 if h1 and h2 else 0.0
                    t_carga = (h4 - h3).total_seconds() / 60
                    
                    dict_hist_final = {
                        "Fecha": h4.strftime('%d-%m-%Y'), "Semana": f"Semana {h4.isocalendar()[1]}",
                        "Mes": ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][h4.month],
                        "Empresa": fila_viaje["Empresa"], "Patente": patente_final, "Chofer": fila_viaje["Chofer"], 
                        "RUT": fila_viaje["RUT"], "Ruta Auditada": ruta_aud,
                        "Ingreso Inversa": h1.strftime('%H:%M:%S') if h1 else "N/A",
                        "Salida Inversa": h2.strftime('%H:%M:%S') if h2 else "N/A",
                        "Ingreso Despacho": h3.strftime('%H:%M:%S') if fila_viaje["H3_Llegada_Despacho"] else "N/A", 
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
            st.subheader("🚚 Vehículos en CD")
        with col_btn_mon:
            if st.button("🔄 Actualizar Tiempos en Vivo"):
                st.rerun()
                
        if not st.session_state.df_activas.empty:
            df_en_patio = st.session_state.df_activas.copy()
            ahora_actual_calc = datetime.datetime.now(zona_local)
            
            ingresos_inv, salidas_inv, ingresos_desp, salidas_desp = [], [], [], []
            t_retornos, t_cargas = [], []
            
            for _, row in df_en_patio.iterrows():
                h1 = datetime.datetime.fromisoformat(row["H1_Llegada_Inversa"]) if pd.notna(row["H1_Llegada_Inversa"]) and row["H1_Llegada_Inversa"] else None
                h2 = datetime.datetime.fromisoformat(row["H2_Salida_Inversa"]) if pd.notna(row["H2_Salida_Inversa"]) and row["H2_Salida_Inversa"] else None
                h3 = datetime.datetime.fromisoformat(row["H3_Llegada_Despacho"]) if pd.notna(row["H3_Llegada_Despacho"]) and row["H3_Llegada_Despacho"] else None
                h4 = datetime.datetime.fromisoformat(row["H4_Salida_Despacho"]) if pd.notna(row["H4_Salida_Despacho"]) and row["H4_Salida_Despacho"] else None
                
                # SOLUCIÓN SINTAXIS: Formato correcto del condicional en Python
                ingresos_inv.append(h1.strftime('%H:%M:%S') if h1 else "N/A")
                salidas_inv.append(h2.strftime('%H:%M:%S') if h2 else "N/A")
                ingresos_desp.append(h3.strftime('%H:%M:%S') if h3 else "N/A")
                salidas_desp.append(h4.strftime('%H:%M:%S') if h4 else "N/A")
                
                if h1 and h2:
                    t_retorno_min = (h2 - h1).total_seconds() / 60
                elif h1 and not h2:
                    t_retorno_min = (ahora_actual_calc - h1).total_seconds() / 60
                else:
                    t_retorno_min = None
                t_retornos.append(formatear_a_cronometro(t_retorno_min) if t_retorno_min is not None else "N/A")
                
                if h3 and h4:
                    t_carga_min = (h4 - h3).total_seconds() / 60
                elif h3 and not h4:
                    t_carga_min = (ahora_actual_calc - h3).total_seconds() / 60
                else:
                    t_carga_min = None
                t_cargas.append(formatear_a_cronometro(t_carga_min) if t_carga_min is not None else "N/A")
            
            df_en_patio["Ingreso Inversa"] = ingresos_inv
            df_en_patio["Salida Inversa"] = salidas_inv
            df_en_patio["T. Retorno (Descarga)"] = t_retornos
            df_en_patio["Ingreso Despacho"] = ingresos_desp
            df_en_patio["Salida Despacho"] = salidas_desp
            df_en_patio["T. Despacho (Carga)"] = t_cargas
            
            columnas_mostrar = [
                "Patente", "Empresa", "Chofer", "Estado", 
                "Ingreso Inversa", "Salida Inversa", "T. Retorno (Descarga)",
                "Ingreso Despacho", "Salida Despacho", "T. Despacho (Carga)"
            ]
            st.dataframe(df_en_patio[columnas_mostrar], use_container_width=True)
        else:
            st.info("No hay vehículos en CD.")
            
        st.markdown("---")
        
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
                
            df_filtrado_kpis = st.session_state.df_historial.copy()
            if filtro_fecha != "Todos":
                df_filtrado_kpis = df_filtrado_kpis[df_filtrado_kpis["Fecha"] == filtro_fecha]
            if filtro_semana != "Todos":
                df_filtrado_kpis = df_filtrado_kpis[df_filtrado_kpis["Semana"] == filtro_semana]
            if filtro_mes != "Todos":
                df_filtrado_kpis = df_filtrado_kpis[df_filtrado_kpis["Mes"] == filtro_mes]
                
            if df_filtrado_kpis.empty:
                st.warning("⚠️ No hay datos registrados en el historial que coincidan con la combinación de filtros seleccionada.")
            else:
                st.subheader("📋 Consolidado Histórico")
                st.dataframe(df_filtrado_kpis.drop(columns=["Minutos_Carga_Raw"], errors='ignore'), use_container_width=True)
                
                st.markdown("---")
                st.subheader("📈 Estadía Promedio CD")
                
                if "T. Retorno (Descarga)" in df_filtrado_kpis.columns and "T. Despacho (Carga)" in df_filtrado_kpis.columns:
                    df_stats = df_filtrado_kpis.copy()
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
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    st.markdown("#### 👨‍✈️ Promedio Por Chofer")
                    df_chof = df_stats.groupby("Chofer")[["Min_Inv", "Min_Desp", "Min_Total"]].mean().reset_index()
                    df_chof["Promedio Inversa"] = df_chof["Min_Inv"].apply(formatear_a_cronometro)
                    df_chof["Promedio Despacho"] = df_chof["Min_Desp"].apply(formatear_a_cronometro)
                    df_chof["Promedio Total CD"] = df_chof["Min_Total"].apply(formatear_a_cronometro)
                    st.dataframe(df_chof[["Chofer", "Promedio Inversa", "Promedio Despacho", "Promedio Total CD"]], use_container_width=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    st.markdown("#### 📇 Promedio Por Patente")
                    df_pat = df_vehiculos.groupby("Patente")[["Min_Inv", "Min_Desp", "Min_Total"]].mean().reset_index()
                    df_pat["Promedio Inversa"] = df_pat["Min_Inv"].apply(formatear_a_cronometro)
                    df_pat["Promedio Despacho"] = df_pat["Min_Desp"].apply(formatear_a_cronometro)
                    df_pat["Promedio Total CD"] = df_pat["Min_Total"].apply(formatear_a_cronometro)
                    st.dataframe(df_pat[["Patente", "Promedio Inversa", "Promedio Despacho", "Promedio Total CD"]], use_container_width=True)
                else:
                    st.info("No hay suficientes datos de tiempo registrados para calcular promedios.")
        else:
            st.info("No hay datos históricos registrados en la planilla para aplicar filtros.")

# =====================================================================
# PANEL GENERADOR DE URLS (ACCESIBLE EXCLUSIVAMENTE PARA EL ADMINISTRADOR)
# =====================================================================
if vista_url == "admin":
    st.markdown("---")
    with st.expander("🔗 PANEL SUPERVISOR: Configuración y Gestión de Patio", expanded=True):
        st.write("### 🚨 Panel de Limpieza de Fin de Jornada")
        st.write("Si quedan vehículos abiertos en el patio al terminar el turno, presiona este botón para cerrarlos en masa y limpiar el monitor para el día siguiente:")
        
        if st.button("⚠️ Forzar Cierre y Archivar Procesos Inconclusos", type="primary"):
            if not st.session_state.df_activas.empty:
                ahora_forzado = datetime.datetime.now(zona_local)
                
                for _, fila_viaje in st.session_state.df_activas.iterrows():
                    h1 = datetime.datetime.fromisoformat(fila_viaje["H1_Llegada_Inversa"]) if pd.notna(fila_viaje["H1_Llegada_Inversa"]) and fila_viaje["H1_Llegada_Inversa"] else None
                    h2 = datetime.datetime.fromisoformat(fila_viaje["H2_Salida_Inversa"]) if pd.notna(fila_viaje["H2_Salida_Inversa"]) and fila_viaje["H2_Salida_Inversa"] else None
                    h3 = datetime.datetime.fromisoformat(fila_viaje["H3_Llegada_Despacho"]) if pd.notna(fila_viaje["H3_Llegada_Despacho"]) and fila_viaje["H3_Llegada_Despacho"] else None
                    h4 = ahora_forzado
                    
                    t_retorno = (h2 - h1).total_seconds() / 60 if h1 and h2 else 0.0
                    t_carga = (h4 - h3).total_seconds() / 60 if h3 else 0.0
                    
                    base_date = h3 if h3 else (h1 if h1 else ahora_forzado)
                    
                    dict_forzado = {
                        "Fecha": base_date.strftime('%d-%m-%Y'),
                        "Semana": f"Semana {base_date.isocalendar()[1]}",
                        "Mes": ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][base_date.month],
                        "Empresa": fila_viaje["Empresa"], "Patente": fila_viaje["Patente"], "Chofer": fila_viaje["Chofer"], "RUT": fila_viaje["RUT"],
                        "Ruta Auditada": "CIERRE FORZADO ADMINISTRATIVO",
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
                
                st.session_state.df_activas = pd.DataFrame(columns=[
                    "Patente", "Empresa", "Chofer", "RUT", "H1_Llegada_Inversa", 
                    "H2_Salida_Inversa", "H3_Llegada_Despacho", "H4_Salida_Despacho", "Ruta_Auditada", "Estado", "Chofer_2", "RUT_2"
                ])
                guardar_datos_cloud(st.session_state.df_activas, "patentes_activas")
                
                st.success("🚨 Se han cerrado de forma forzada todos los procesos activos y se han archivado correctamente.")
                time.sleep(1.5)
                st.rerun()
            else:
                st.warning("No hay procesos activos en patio para cerrar.")
                
        st.markdown("---")
        st.write("### 🔗 Enlaces directos para compartir con el personal:")
        base_url = "https://control-transporte-patio-cyzw3qqhshcvvji8p7fsft.streamlit.app/"
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**🔄 Logística Inversa**")
            st.code(f"{base_url}?vista=inversa", language="text")
        with col2:
            st.success("**📦 Equipo Despacho**")
            st.code(f"{base_url}?vista=despacho", language="text")
        with col3:
            st.warning("**🖥️ Equipo Monitores**")
            st.code(f"{base_url}?vista=monitoreo", language="text")
