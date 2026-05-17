import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# ==============================================================================
# CONFIGURACIÓN DE LA PÁGINA Y CONEXIÓN DIRECTA A GOOGLE SHEETS
# ==============================================================================
st.set_page_config(page_title="Control de Transportes - Patio", layout="wide", page_icon="🚛")

# ID de tu planilla suministrada
SPREADSHEET_ID = "19K8Mn8EGn06i1RXhTkOJrCGvVm8nriWOEbV6TT-uYeg"
zona_local = pytz.timezone('America/Santiago')

# Función para conectar de forma segura usando los Secrets de Streamlit
@st.cache_resource(ttl=600)
def conectar_google_sheets():
    try:
        # Convertimos a diccionario para poder manipular el texto de la clave de forma segura
        credentials_info = dict(st.secrets["gspread"])
        
        # SOLUCIÓN AL ERROR PEM: Corrige automáticamente los saltos de línea mal formateados en la nube
        if "private_key" in credentials_info:
            credentials_info["private_key"] = credentials_info["private_key"].replace("\\n", "\n")
            
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(credentials_info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).get_worksheet(0) # Abre la primera pestaña
        return sheet
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return None

sheet_conexion = conectar_google_sheets()

# Cargar los datos directo desde la nube a un DataFrame de Pandas
def cargar_datos():
    if sheet_conexion:
        try:
            records = sheet_conexion.get_all_records()
            if records:
                df = pd.DataFrame(records)
                # Asegurar columnas mínimas obligatorias
                columnas_necesarias = ['Fecha/Hora', 'Modulo', 'Patente', 'Chofer', 'Empresa', 'Tiempo_Estadia_Min', 'Estado', 'Rol_Registrador']
                for col in columnas_necesarias:
                    if col not in df.columns:
                        df[col] = ""
                return df
            else:
                return pd.DataFrame(columns=['Fecha/Hora', 'Modulo', 'Patente', 'Chofer', 'Empresa', 'Tiempo_Estadia_Min', 'Estado', 'Rol_Registrador'])
        except Exception as e:
            st.warning(f"No se pudieron leer registros nuevos, iniciando tabla vacía: {e}")
    return pd.DataFrame(columns=['Fecha/Hora', 'Modulo', 'Patente', 'Chofer', 'Empresa', 'Tiempo_Estadia_Min', 'Estado', 'Rol_Registrador'])

df_global = cargar_datos()

# ==============================================================================
# NAVEGACIÓN EN EL CUERPO PRINCIPAL (SIN BARRA LATERAL)
# ==============================================================================
st.title("🏢 Sistema de Control de Transportes - Patio")

# Detectar si vienen parámetros desde el enlace para cambiar de módulo automáticamente
query_params = st.query_params
modulo_defecto = "Monitoreo General"

if "modulo" in query_params:
    param_val = query_params["modulo"].lower()
    if "logistica" in param_val:
        modulo_defecto = "Logística Inversa"
    elif "despacho" in param_val:
        modulo_defecto = "Despacho"
    elif "admin" in param_val:
        modulo_defecto = "Administrador / Estadísticas"

# Selector de módulos principal centrado arriba
opciones_modulos = ["Monitoreo General", "Logística Inversa", "Despacho", "Administrador / Estadísticas"]
modulo_seleccionado = st.selectbox(
    "📂 Seleccione el Módulo de Trabajo Actual:",
    opciones_modulos,
    index=opciones_modulos.index(modulo_defecto)
)

st.markdown("---")

# ==============================================================================
# DESARROLLO DE LOS MÓDULOS DE REGISTRO
# ==============================================================================
if modulo_seleccionado in ["Logística Inversa", "Despacho"]:
    st.subheader(f"Formulario de Registro de Movimiento - {modulo_seleccionado}")
    
    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            patente = st.text_input("Patente del Vehículo:", max_chars=8).upper().strip()
            chofer = st.text_input("Nombre del Chofer:").title().strip()
        with col2:
            empresa = st.text_input("Empresa de Transporte:").upper().strip()
            tiempo_estimado = st.number_input("Tiempo de Estadía Estimado (Minutos):", min_value=1, value=30)
            
        estado_unid = st.selectbox("Estado Inicial:", ["En Espera", "En Andén", "Completado"])
        submit_btn = st.form_submit_button("Guardar Registro en Google Sheets")
        
        if submit_btn:
            if patente and chofer and empresa:
                ahora_santiago = datetime.now(zona_local).strftime("%Y-%m-%d %H:%M:%S")
                nuevo_registro = [
                    ahora_santiago,
                    modulo_seleccionado,
                    patente,
                    chofer,
                    empresa,
                    int(tiempo_estimado),
                    estado_unid,
                    "Administrador" if modulo_seleccionado == "Logística Inversa" else "Operador"
                ]
                
                # CAÍDA DE DATOS REAL A GOOGLE SHEETS
                if sheet_conexion:
                    try:
                        sheet_conexion.append_row(nuevo_registro)
                        st.success(f"✅ ¡Registro guardado exitosamente en Google Sheets! Patente: {patente}")
                        st.rerun() 
                    except Exception as ex:
                        st.error(f"No se pudo guardar en la nube de Google: {ex}")
                else:
                    st.error("Error: Conexión con Google Sheets no disponible.")
            else:
                st.warning("⚠️ Por favor rellene todos los campos obligatorios (Patente, Chofer y Empresa).")

# ==============================================================================
# MÓDULO MONITOREO GENERAL (Vistas de datos unificados)
# ==============================================================================
elif modulo_seleccionado == "Monitoreo General":
    st.subheader("📋 Panel de Control de Patio en Tiempo Real")
    st.write("Esta tabla sincroniza en tiempo real los datos ingresados desde cualquier dispositivo.")
    
    if not df_global.empty:
        st.dataframe(df_global, use_container_width=True)
    else:
        st.info("No hay registros guardados en la planilla aún.")

# ==============================================================================
# MÓDULO ADMINISTRADOR Y TABLAS DE PROMEDIOS (Punto 1)
# ==============================================================================
elif modulo_seleccionado == "Administrador / Estadísticas":
    st.subheader("📊 Cuadro de Mando: Análisis de Promedios de Estadía")
    
    if not df_global.empty:
        # Asegurarse de que el tiempo de estadía sea numérico para sacar promedios exactos
        df_global['Tiempo_Estadia_Min'] = pd.to_numeric(df_global['Tiempo_Estadia_Min'], errors='coerce').fillna(0)
        
        # FILTROS RÁPIDOS MÓDULO
        mod_filtro = st.multiselect("Filtrar por Módulo de origen:", options=df_global['Modulo'].unique(), default=df_global['Modulo'].unique())
        df_filtrado = df_global[df_global['Modulo'].isin(mod_filtro)]
        
        # DISEÑO DE TABLAS DE PROMEDIOS SOLICITADAS
        tab1, tab2, tab3 = st.tabs(["📈 Promedio por Empresa", "👨‍✈️ Promedio por Chofer", "📇 Promedio por Patente"])
        
        with tab1:
            st.markdown("#### Tiempo Promedio de Estadía por Empresa de Transporte")
            prom_empresa = df_filtrado.groupby('Empresa')['Tiempo_Estadia_Min'].agg(['mean', 'count']).reset_index()
            prom_empresa.columns = ['Empresa de Transporte', 'Tiempo Promedio (Minutos)', 'Cantidad de Viajes']
            prom_empresa['Tiempo Promedio (Minutos)'] = prom_empresa['Tiempo Promedio (Minutos)'].round(1)
            st.dataframe(prom_empresa.sort_values(by='Tiempo Promedio (Minutos)', ascending=False), use_container_width=True)
            
        with tab2:
            st.markdown("#### Tiempo Promedio de Estadía por Chofer")
            prom_chofer = df_filtrado.groupby('Chofer')['Tiempo_Estadia_Min'].agg(['mean', 'count']).reset_index()
            prom_chofer.columns = ['Nombre del Chofer', 'Tiempo Promedio (Minutos)', 'Cantidad de Viajes']
            prom_chofer['Tiempo Promedio (Minutos)'] = prom_chofer['Tiempo Promedio (Minutos)'].round(1)
            st.dataframe(prom_chofer.sort_values(by='Tiempo Promedio (Minutos)', ascending=False), use_container_width=True)
            
        with tab3:
            st.markdown("#### Tiempo Promedio de Estadía por Patente")
            prom_patente = df_filtrado.groupby('Patente')['Tiempo_Estadia_Min'].agg(['mean', 'count']).reset_index()
            prom_patente.columns = ['Patente del Vehículo', 'Tiempo Promedio (Minutos)', 'Cantidad de Viajes']
            prom_patente['Tiempo Promedio (Minutos)'] = prom_patente['Tiempo Promedio (Minutos)'].round(1)
            st.dataframe(prom_patente.sort_values(by='Tiempo Promedio (Minutos)', ascending=False), use_container_width=True)
            
        # Vista Completa de Auditoría
        st.markdown("---")
        st.markdown("#### 🔍 Historial Completo de Auditoría de Administrador")
        st.dataframe(df_filtrado, use_container_width=True)
    else:
        st.info("No hay datos suficientes en Google Sheets para calcular promedios estadísticos.")

# ==============================================================================
# CONTENEDOR DE ENLACES COMPARTIBLES AL FINAL DE LA PÁGINA
# ==============================================================================
st.markdown("---")
with st.expander("🔗 Enlaces directos para compartir con otros PC"):
    url_base = "https://control-transporte-patio-cyzw3qqhshcvvji8p7fsft.streamlit.app" # Tu URL actual de producción
    st.write(f"Puedes copiar y enviar estos enlaces para que entren directamente al módulo correspondiente desde cualquier computador:")
    st.code(f"Módulo Logística Inversa: {url_base}/?modulo=Logistica")
    st.code(f"Módulo Despacho:           {url_base}/?modulo=Despacho")
    st.code(f"Módulo Administrador:       {url_base}/?modulo=Admin")
