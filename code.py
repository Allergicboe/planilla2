import streamlit as st
import streamlit.components.v1 as components
import gspread
from gspread import Cell
from datetime import datetime
from google.oauth2.service_account import Credentials
import time
import pandas as pd
from zoneinfo import ZoneInfo

def get_chile_timestamp():
    """
    Retorna la fecha y hora actual en la zona horaria de Chile con el formato deseado.
    """
    return datetime.now(ZoneInfo("America/Santiago")).strftime('%d-%m-%y %H:%M')

# Configuración de la página
st.set_page_config(
    page_title="Estado de Clientes",
    page_icon="👥",
    layout="wide"
)

# Configuración: URL de la hoja de cálculo
SPREADSHEET_URL = st.secrets["spreadsheet_url"]

# Función para reiniciar la búsqueda
def reset_search():
    st.session_state.rows = None

# Configuración de credenciales
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope
)
gc = gspread.authorize(credentials)
sheet = gc.open_by_url(SPREADSHEET_URL).sheet1

# Manejo de errores de API
def handle_quota_error(e):
    error_str = str(e).lower()
    if "quota" in error_str or "limit" in error_str:
        st.error("❌ Límite de API alcanzado. Reiniciando...")
        time.sleep(1)
        st.rerun()

# Obtener datos con caché
@st.cache_data(ttl=60)
def get_data():
    try:
        return sheet.get_all_values()
    except Exception as e:
        handle_quota_error(e)
        st.error(f"❌ Error: {e}")
        return None

# Buscar filas según cuenta y sectores seleccionados
def find_rows(selected_cuenta, selected_sectores, data):
    rows = []
    for i, row in enumerate(data[1:]):
        match_cuenta = (row[0] == selected_cuenta)
        match_sector = (len(selected_sectores) == 0 or row[1] in selected_sectores)
        if match_cuenta and match_sector:
            rows.append(i + 2)
    return rows

# Actualizar celdas (incluye actualización de observaciones para cada proceso)
def update_steps(rows, steps_updates, consultoria_value, comentarios_value):
    now = get_chile_timestamp()
    cells_to_update = []

    # Actualizar Consultoría
    consultoria_col = 3
    update_consultoria = "" if consultoria_value == "Vacío" else consultoria_value
    for row in rows:
        cells_to_update.append(Cell(row, consultoria_col, update_consultoria))

    # Actualizar pasos (valor, observaciones y fecha)
    for step in steps_updates:
        selected_option = step["value"]
        update_value = "" if selected_option == "Vacío" else selected_option
        step_col = step["step_col"]
        date_col = step["date_col"]
        obs_col = step.get("obs_col")
        for row in rows:
            # Actualizar valor del paso
            cells_to_update.append(Cell(row, step_col, update_value))
            # Actualizar observación del paso (si corresponde)
            if obs_col is not None:
                cells_to_update.append(Cell(row, obs_col, step["obs_value"]))
            # Actualizar fecha si hay avance
            if update_value in ['Sí', 'Programado', 'Sí (DropControl)', 'Sí (CDTEC IF)']:
                cells_to_update.append(Cell(row, date_col, now))
            else:
                cells_to_update.append(Cell(row, date_col, ''))

    # Actualizar Comentarios (columna Y)
    comentarios_col = 25
    for row in rows:
        cells_to_update.append(Cell(row, comentarios_col, comentarios_value))

    # Actualizar fecha de última modificación (columna Z)
    ultima_actualizacion_col = 26
    for row in rows:
        cells_to_update.append(Cell(row, ultima_actualizacion_col, now))

    try:
        sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        st.success("✅ Cambios guardados.")
        # Invalidar caché para forzar la recarga de datos
        st.cache_data.clear()
        return True
    except Exception as e:
        handle_quota_error(e)
        st.error(f"❌ Error: {e}")
        return False

# Obtener color según estado
def get_state_color(state):
    colors = {
        'Sí': '#4CAF50',  # Verde
        'No': '#F44336',  # Rojo
        'Programado': '#FFC107',  # Amarillo
        'No aplica': '#9E9E9E',  # Gris
        'Sí (DropControl)': '#2196F3',  # Azul
        'Sí (CDTEC IF)': '#673AB7',  # Morado
        'Vacío': '#E0E0E0',  # Gris claro
    }
    return colors.get(state, '#E0E0E0')

# Función principal
def main():
    st.title("📌 Estado de Clientes")
    
    # Botón para abrir planilla
    html_button = f"""
    <div style="text-align: left; margin-bottom: 10px;">
        <a href="{SPREADSHEET_URL}" target="_blank">
            <button style="
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
                border-radius: 5px;
                cursor: pointer;">
                Abrir Planilla de Google
            </button>
        </a>
    </div>
    """
    components.html(html_button, height=50)

    # Inicializar estado de actualizaciones
    if "update_successful" not in st.session_state:
        st.session_state.update_successful = False

    # Cargar datos - siempre cargar datos frescos si hubo una actualización exitosa
    if "data" not in st.session_state or st.session_state.update_successful:
        st.session_state.data = get_data()
        st.session_state.update_successful = False
    data = st.session_state.data

    if data is None:
        st.stop()

    # Extraer cuentas únicas
    unique_cuentas = sorted(set(row[0] for row in data[1:]))

    st.header("Buscar Registro")
    
    # Selección de Cuenta
    cuentas_options = ["Seleccione una cuenta"] + unique_cuentas
    selected_cuenta = st.selectbox("Cuenta", cuentas_options, key="cuenta", on_change=reset_search)
    
    # Selección múltiple de Sectores
    if selected_cuenta != "Seleccione una cuenta":
        sectores_para_cuenta = [row[1] for row in data[1:] if row[0] == selected_cuenta]
        unique_sectores = sorted(set(sectores_para_cuenta))
        
        if "selected_sectores" not in st.session_state:
            st.session_state.selected_sectores = []
            
        st.write("Sectores de Riego (seleccione uno o varios):")
        checkbox_container = st.container()

        if st.button("Seleccionar Todos", use_container_width=True):
            st.session_state.selected_sectores = unique_sectores.copy()
            st.rerun()
        
        with checkbox_container:
            for sector in unique_sectores:
                sector_checked = st.checkbox(sector, key=f"sector_{sector}", 
                                             value=sector in st.session_state.selected_sectores)
                if sector_checked and sector not in st.session_state.selected_sectores:
                    st.session_state.selected_sectores.append(sector)
                elif not sector_checked and sector in st.session_state.selected_sectores:
                    st.session_state.selected_sectores.remove(sector)
        
        if st.button("Deseleccionar Todos", use_container_width=True):
            st.session_state.selected_sectores = []
            st.rerun()
    else:
        st.session_state.selected_sectores = []

    if st.button("Buscar Registro", type="primary", use_container_width=True):
        if selected_cuenta == "Seleccione una cuenta":
            st.error("❌ Seleccione una cuenta válida.")
            st.session_state.rows = None
        elif not st.session_state.selected_sectores:
            st.warning("⚠️ No hay sectores seleccionados. Se mostrarán todos los sectores para esta cuenta.")
            rows = find_rows(selected_cuenta, [], data)
            if not rows:
                st.error("❌ No se encontraron registros.")
                st.session_state.rows = None
            else:
                st.session_state.rows = rows
                st.success(f"Se actualizarán {len(rows)} sector(es).")
        else:
            rows = find_rows(selected_cuenta, st.session_state.selected_sectores, data)
            if not rows:
                st.error("❌ No se encontraron registros.")
                st.session_state.rows = None
            else:
                st.session_state.rows = rows
                st.success(f"Se actualizarán {len(rows)} sector(es).")

    if "rows" not in st.session_state:
        st.session_state.rows = None

    # Mostrar tabla dinámica con colores (Estado Actual)
    if st.session_state.rows is not None:
        st.header("Estado Actual")
        
        # Preparar datos para la tabla (se muestran algunas columnas relevantes)
        table_data = []
        headers = ["Cuenta", "Sector", "Consultoría", 
                   "Ingreso a Planilla", "Correo Presentación", 
                   "Puntos Críticos", "Capacitación Plataforma", 
                   "Documento Power BI", "Capacitación Power BI", 
                   "Estrategia de Riego", "Última Actualización"]
        
        for row_index in st.session_state.rows:
            row = data[row_index - 1]  # Ajuste de índice
            row_data = [
                row[0],  # Cuenta
                row[1],  # Sector
                row[2],  # Consultoría
                row[3],  # Ingreso a Planilla
                row[6],  # Correo Presentación
                row[9],  # Puntos Críticos
                row[12], # Capacitación Plataforma
                row[15], # Documento Power BI
                row[18], # Capacitación Power BI
                row[21], # Estrategia de Riego
                row[25] if len(row) > 25 else "",  # Última Actualización
            ]
            table_data.append(row_data)
        
        n_rows = len(table_data)
        if n_rows <= 3:
            estado_height = 230
        elif n_rows <= 10:
            estado_height = 285
        else:
            estado_height = 500
        
        df = pd.DataFrame(table_data, columns=headers)
        
        html_table = f"""
        <style>
        .status-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        .status-table th, .status-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }}
        .status-table th {{
            background-color: #f2f2f2;
            position: sticky;
            top: 0;
        }}
        .status-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .status-cell {{
            border-radius: 4px;
            color: white;
            padding: 4px 8px;
            display: inline-block;
            width: 90%;
            text-align: center;
        }}
        .date-cell {{
            font-size: 0.85em;
            color: #333;
        }}
        </style>
        <div style="height: {estado_height}px; overflow-y: auto;">
        <table class="status-table">
            <thead>
                <tr>
        """
        for header in headers:
            html_table += f"<th>{header}</th>"
        html_table += """
                </tr>
            </thead>
            <tbody>
        """
        for _, row in df.iterrows():
            html_table += "<tr>"
            for i, cell in enumerate(row):
                if i <= 1:
                    html_table += f"<td>{cell}</td>"
                elif i == len(row) - 1:
                    html_table += f'<td><div class="date-cell">{cell}</div></td>'
                else:
                    cell_value = cell if cell and cell.strip() != "" else "Vacío"
                    color = get_state_color(cell_value)
                    html_table += f"""
                    <td>
                        <div class="status-cell" style="background-color: {color};">
                            {cell_value}
                        </div>
                    </td>
                    """
            html_table += "</tr>"
        html_table += """
            </tbody>
        </table>
        </div>
        """
        st.components.v1.html(html_table, height=estado_height)
        
        # Bloque de Observaciones:
        # Se muestra solo si se ha seleccionado un único sector de riego
        if len(st.session_state.selected_sectores) == 1:
            fila_datos = data[st.session_state.rows[0] - 1]
            process_obs = [
                ("Ingreso a Planilla Clientes Nuevos", fila_datos[4] if len(fila_datos) > 4 and fila_datos[4].strip() != "" else "Vacío"),
                ("Correo Presentación y Solicitud Información", fila_datos[7] if len(fila_datos) > 7 and fila_datos[7].strip() != "" else "Vacío"),
                ("Agregar Puntos Críticos", fila_datos[10] if len(fila_datos) > 10 and fila_datos[10].strip() != "" else "Vacío"),
                ("Generar Capacitación Plataforma", fila_datos[13] if len(fila_datos) > 13 and fila_datos[13].strip() != "" else "Vacío"),
                ("Generar Documento Power BI", fila_datos[16] if len(fila_datos) > 16 and fila_datos[16].strip() != "" else "Vacío"),
                ("Generar Capacitación Power BI", fila_datos[19] if len(fila_datos) > 19 and fila_datos[19].strip() != "" else "Vacío"),
                ("Generar Estrategia de Riego", fila_datos[22] if len(fila_datos) > 22 and fila_datos[22].strip() != "" else "Vacío"),
            ]
            
            # Título y estilo mejorado
            html_obs_table = """
            <style>
              .comments-table {
                 width: 100%;
                 border-collapse: collapse;
                 font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                 margin-top: 20px;
              }
              .comments-table td {
                 border: 1px solid #ddd;
                 padding: 12px;
              }
              .comments-table td:first-child {
                 font-weight: bold;
                 text-align: left;
                 width: 50%;
                 background-color: #ddd; /* Color de fondo para la primera columna */
              }
              .comments-table td:last-child {
                 text-align: left;
                 width: 50%;
              }
              .table-title {
                 font-size: 18px;
                 font-weight: bold;
                 color: #0b5394;
                 margin-bottom: 15px;
              }
            </style>
            <div class="table-title">Observaciones de Procesos</div>
            <table class="comments-table">
            """
            
            # Agregar los procesos y observaciones
            for process, obs in process_obs:
                html_obs_table += f"<tr><td>{process}</td><td>{obs}</td></tr>"
            
            html_obs_table += "</table>"
            
            # Mostrar la tabla con observaciones
            st.components.v1.html(html_obs_table, height=220)
        
        # Sección: Tabla de Comentarios por Sector
        st.subheader("Comentarios por Sector")
        comentarios_data = {}
        sectores_encontrados = []
        
        for row_index in st.session_state.rows:
            row = data[row_index - 1]
            sector = row[1]
            comentario = row[24] if len(row) > 24 and row[24] else "Sin comentarios"
            sectores_encontrados.append(sector)
            comentarios_data[sector] = comentario
        
        sectores_encontrados = sorted(set(sectores_encontrados))
        comentarios_height = 130 if len(sectores_encontrados) <= 10 else 180
        
        # Estilo para la tabla de comentarios
        html_comentarios = f"""
        <style>
        .comments-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin-top: 15px;
        }}
        .comments-table th, .comments-table td {{
            border: 1px solid #ddd;
            padding: 12px;
        }}
        .comments-table th {{
            background-color: #f2f2f2;
            text-align: center;
            font-weight: bold;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        .comments-table td {{
            text-align: left;
            vertical-align: top;
            background-color: #f9f9f9;
        }}
        </style>
        <div style="height: {comentarios_height}px; overflow-y: auto;">
        <table class="comments-table">
            <thead>
                <tr>
        """
        # Crear las cabeceras de la tabla con los sectores
        for sector in sectores_encontrados:
            html_comentarios += f"<th>{sector}</th>"
        
        html_comentarios += """
                </tr>
            </thead>
            <tbody>
                <tr>
        """
        # Rellenar los comentarios por sector
        for sector in sectores_encontrados:
            comentario = comentarios_data.get(sector, "Sin comentarios")
            html_comentarios += f"<td>{comentario}</td>"
            
        html_comentarios += """
                </tr>
            </tbody>
        </table>
        </div>
        """
        
        # Mostrar la tabla con comentarios
        st.components.v1.html(html_comentarios, height=comentarios_height)

        st.header("Actualizar Registro")
        fila_index = st.session_state.rows[0] - 1
        fila_datos = data[fila_index]
        
        # Opciones para cada paso
        step_options = {
            "Ingreso a Planilla Clientes Nuevos": ['Sí', 'No'],
            "Correo Presentación y Solicitud Información": ['Sí', 'No', 'Programado'],
            "Agregar Puntos Críticos": ['Sí', 'No'],
            "Generar Capacitación Plataforma": ['Sí (DropControl)', 'Sí (CDTEC IF)', 'No', 'Programado'],
            "Generar Documento Power BI": ['Sí', 'No', 'Programado', 'No aplica'],
            "Generar Capacitación Power BI": ['Sí', 'No', 'Programado', 'No aplica'],
            "Generar Estrategia de Riego": ['Sí', 'No', 'Programado', 'No aplica']
        }
        
        with st.form("update_form"):
            col1, col2 = st.columns(2)
            
            # Columna 1: Procesos (selectboxes)
            with col1:
                # Consultoría (sin observaciones)
                consultoria_default = fila_datos[2] if len(fila_datos) >= 3 else ""
                display_consultoria = consultoria_default.strip() if consultoria_default and consultoria_default.strip() != "" else "Vacío"
                consultoria_options = ["Sí", "No"]
                if display_consultoria not in consultoria_options:
                    consultoria_options = [display_consultoria] + consultoria_options
                try:
                    consultoria_index = consultoria_options.index(display_consultoria)
                except ValueError:
                    consultoria_index = 0
                consultoria_value = st.selectbox("Consultoría", options=consultoria_options, index=consultoria_index, key="consultoria_update")
                
                # Proceso 1: Ingreso a Planilla Clientes Nuevos
                step1 = {"step_label": "Ingreso a Planilla Clientes Nuevos", "step_col": 4, "obs_col": 5, "date_col": 6}
                default_val = fila_datos[step1["step_col"] - 1] if len(fila_datos) > step1["step_col"] - 1 else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                options_for_select = step_options[step1["step_label"]].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                step1_value = st.selectbox(step1["step_label"], options=options_for_select, index=default_index, key="step_0_update")
                
                # Proceso 2: Correo Presentación y Solicitud Información
                step2 = {"step_label": "Correo Presentación y Solicitud Información", "step_col": 7, "obs_col": 8, "date_col": 9}
                default_val = fila_datos[step2["step_col"] - 1] if len(fila_datos) > step2["step_col"] - 1 else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                options_for_select = step_options[step2["step_label"]].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                step2_value = st.selectbox(step2["step_label"], options=options_for_select, index=default_index, key="step_1_update")
                
                # Proceso 3: Agregar Puntos Críticos
                step3 = {"step_label": "Agregar Puntos Críticos", "step_col": 10, "obs_col": 11, "date_col": 12}
                default_val = fila_datos[step3["step_col"] - 1] if len(fila_datos) > step3["step_col"] - 1 else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                options_for_select = step_options[step3["step_label"]].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                step3_value = st.selectbox(step3["step_label"], options=options_for_select, index=default_index, key="step_2_update")
                
                # Proceso 4: Generar Capacitación Plataforma
                step4 = {"step_label": "Generar Capacitación Plataforma", "step_col": 13, "obs_col": 14, "date_col": 15}
                default_val = fila_datos[step4["step_col"] - 1] if len(fila_datos) > step4["step_col"] - 1 else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                options_for_select = step_options[step4["step_label"]].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                step4_value = st.selectbox(step4["step_label"], options=options_for_select, index=default_index, key="step_3_update")
                
                # Proceso 5: Generar Documento Power BI
                step5 = {"step_label": "Generar Documento Power BI", "step_col": 16, "obs_col": 17, "date_col": 18}
                default_val = fila_datos[step5["step_col"] - 1] if len(fila_datos) > step5["step_col"] - 1 else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                options_for_select = step_options[step5["step_label"]].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                step5_value = st.selectbox(step5["step_label"], options=options_for_select, index=default_index, key="step_4_update")
                
                # Proceso 6: Generar Capacitación Power BI
                step6 = {"step_label": "Generar Capacitación Power BI", "step_col": 19, "obs_col": 20, "date_col": 21}
                default_val = fila_datos[step6["step_col"] - 1] if len(fila_datos) > step6["step_col"] - 1 else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                options_for_select = step_options[step6["step_label"]].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                step6_value = st.selectbox(step6["step_label"], options=options_for_select, index=default_index, key="step_5_update")
                
                # Proceso 7: Generar Estrategia de Riego
                step7 = {"step_label": "Generar Estrategia de Riego", "step_col": 22, "obs_col": 23, "date_col": 24}
                default_val = fila_datos[step7["step_col"] - 1] if len(fila_datos) > step7["step_col"] - 1 else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                options_for_select = step_options[step7["step_label"]].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                step7_value = st.selectbox(step7["step_label"], options=options_for_select, index=default_index, key="step_6_update")
            
            # Columna 2: Campos de observaciones y, al final, "Comentarios generales"
            with col2:
                default_obs = fila_datos[step1["obs_col"] - 1] if len(fila_datos) > step1["obs_col"] - 1 else ""
                step1_obs_value = st.text_area("Observaciones - Ingreso a Planilla", value=default_obs, height=68, key="obs_0_update")
                
                default_obs = fila_datos[step2["obs_col"] - 1] if len(fila_datos) > step2["obs_col"] - 1 else ""
                step2_obs_value = st.text_area("Observaciones - Correo Presentación", value=default_obs, height=68, key="obs_1_update")
                
                default_obs = fila_datos[step3["obs_col"] - 1] if len(fila_datos) > step3["obs_col"] - 1 else ""
                step3_obs_value = st.text_area("Observaciones - Puntos Críticos", value=default_obs, height=68, key="obs_2_update")
                
                default_obs = fila_datos[step4["obs_col"] - 1] if len(fila_datos) > step4["obs_col"] - 1 else ""
                step4_obs_value = st.text_area("Observaciones - Capacitación Plataforma", value=default_obs, height=68, key="obs_3_update")
                
                default_obs = fila_datos[step5["obs_col"] - 1] if len(fila_datos) > step5["obs_col"] - 1 else ""
                step5_obs_value = st.text_area("Observaciones - Documento Power BI", value=default_obs, height=68, key="obs_4_update")
                
                default_obs = fila_datos[step6["obs_col"] - 1] if len(fila_datos) > step6["obs_col"] - 1 else ""
                step6_obs_value = st.text_area("Observaciones - Capacitación Power BI", value=default_obs, height=68, key="obs_5_update")
                
                default_obs = fila_datos[step7["obs_col"] - 1] if len(fila_datos) > step7["obs_col"] - 1 else ""
                step7_obs_value = st.text_area("Observaciones - Estrategia de Riego", value=default_obs, height=68, key="obs_6_update")
                
                # Al final de la columna 2 se agrega el campo "Comentarios generales" con altura 68px
                comentarios_generales = st.text_area("Comentarios generales", value="", height=68, key="comentarios_generales_update")
            
            submitted = st.form_submit_button("Guardar Cambios", type="primary", use_container_width=True)
            if submitted:
                steps_updates = [
                    {"step_label": step1["step_label"], "step_col": step1["step_col"], "obs_col": step1["obs_col"], "date_col": step1["date_col"],
                     "value": step1_value, "obs_value": step1_obs_value},
                    {"step_label": step2["step_label"], "step_col": step2["step_col"], "obs_col": step2["obs_col"], "date_col": step2["date_col"],
                     "value": step2_value, "obs_value": step2_obs_value},
                    {"step_label": step3["step_label"], "step_col": step3["step_col"], "obs_col": step3["obs_col"], "date_col": step3["date_col"],
                     "value": step3_value, "obs_value": step3_obs_value},
                    {"step_label": step4["step_label"], "step_col": step4["step_col"], "obs_col": step4["obs_col"], "date_col": step4["date_col"],
                     "value": step4_value, "obs_value": step4_obs_value},
                    {"step_label": step5["step_label"], "step_col": step5["step_col"], "obs_col": step5["obs_col"], "date_col": step5["date_col"],
                     "value": step5_value, "obs_value": step5_obs_value},
                    {"step_label": step6["step_label"], "step_col": step6["step_col"], "obs_col": step6["obs_col"], "date_col": step6["date_col"],
                     "value": step6_value, "obs_value": step6_obs_value},
                    {"step_label": step7["step_label"], "step_col": step7["step_col"], "obs_col": step7["obs_col"], "date_col": step7["date_col"],
                     "value": step7_value, "obs_value": step7_obs_value},
                ]
                # Se obtiene el valor del campo "Comentarios generales" de la columna 2
                comentarios_generales_value = st.session_state.get("comentarios_generales_update", "")
                success = update_steps(st.session_state.rows, steps_updates, consultoria_value, comentarios_generales_value)
                if success:
                    st.session_state.update_successful = True
                    st.rerun()


if __name__ == "__main__":
    main()
