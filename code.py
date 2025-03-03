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

# Actualizar celdas (incluye actualización de cada proceso)
def update_steps(rows, steps_updates, consultoria_value, comentarios_value):
    now = get_chile_timestamp()
    cells_to_update = []

    # Actualizar Consultoría (columna 3)
    consultoria_col = 3
    update_consultoria = "" if consultoria_value == "Vacío" else consultoria_value
    for row in rows:
        cells_to_update.append(Cell(row, consultoria_col, update_consultoria))

    # Actualizar cada proceso (valor, observación y fecha)
    for step in steps_updates:
        selected_option = step["value"]
        update_value = "" if selected_option == "Vacío" else selected_option
        step_col = step["step_col"]
        date_col = step["date_col"]
        obs_col = step.get("obs_col")
        for row in rows:
            cells_to_update.append(Cell(row, step_col, update_value))
            if obs_col is not None:
                cells_to_update.append(Cell(row, obs_col, step["obs_value"]))
            if update_value in ['Sí', 'Programado', 'Sí (DropControl)', 'Sí (CDTEC IF)']:
                cells_to_update.append(Cell(row, date_col, now))
            else:
                cells_to_update.append(Cell(row, date_col, ''))

    # Actualizar Comentarios generales (columna 31)
    comentarios_col = 31
    for row in rows:
        cells_to_update.append(Cell(row, comentarios_col, comentarios_value))

    # Actualizar fecha de última modificación (columna 32)
    ultima_actualizacion_col = 32
    for row in rows:
        cells_to_update.append(Cell(row, ultima_actualizacion_col, now))

    try:
        sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        st.success("✅ Cambios guardados.")
        st.cache_data.clear()
        return True
    except Exception as e:
        handle_quota_error(e)
        st.error(f"❌ Error: {e}")
        return False

# Obtener color según estado
def get_state_color(state):
    colors = {
        'Sí': '#4CAF50',          # Verde
        'No': '#F44336',          # Rojo
        'Programado': '#FFC107',  # Amarillo
        'No aplica': '#9E9E9E',   # Gris
        'Sí (DropControl)': '#2196F3',   # Azul
        'Sí (CDTEC IF)': '#673AB7',      # Morado
        'Vacío': '#E0E0E0',       # Gris claro
    }
    return colors.get(state, '#E0E0E0')

# Definición centralizada de procesos.
# Cada proceso ocupa 3 columnas: valor, observación y fecha.
# La estructura de la hoja es:
#   1. Cuenta  
#   2. Sector  
#   3. Consultoría  
#   4-6. Proceso Nuevo 1  
#   7-9. Proceso Nuevo 2  
#   10-12. Ingreso a Planilla Clientes Nuevos  
#   13-15. Correo Presentación y Solicitud Información  
#   16-18. Agregar Puntos Críticos  
#   19-21. Generar Capacitación Plataforma  
#   22-24. Generar Documento Power BI  
#   25-27. Generar Capacitación Power BI  
#   28-30. Generar Estrategia de Riego  
#   31. Comentarios generales  
#   32. Última Actualización
processes = [
    {"name": "Proceso Nuevo 1", "step_col": 4, "obs_col": 5, "date_col": 6, "options": ['Sí', 'No']},
    {"name": "Proceso Nuevo 2", "step_col": 7, "obs_col": 8, "date_col": 9, "options": ['Sí', 'No', 'Programado']},
    {"name": "Ingreso a Planilla Clientes Nuevos", "step_col": 10, "obs_col": 11, "date_col": 12, "options": ['Sí', 'No']},
    {"name": "Correo Presentación y Solicitud Información", "step_col": 13, "obs_col": 14, "date_col": 15, "options": ['Sí', 'No', 'Programado']},
    {"name": "Agregar Puntos Críticos", "step_col": 16, "obs_col": 17, "date_col": 18, "options": ['Sí', 'No']},
    {"name": "Generar Capacitación Plataforma", "step_col": 19, "obs_col": 20, "date_col": 21, "options": ['Sí (DropControl)', 'Sí (CDTEC IF)', 'No', 'Programado']},
    {"name": "Generar Documento Power BI", "step_col": 22, "obs_col": 23, "date_col": 24, "options": ['Sí', 'No', 'Programado', 'No aplica']},
    {"name": "Generar Capacitación Power BI", "step_col": 25, "obs_col": 26, "date_col": 27, "options": ['Sí', 'No', 'Programado', 'No aplica']},
    {"name": "Generar Estrategia de Riego", "step_col": 28, "obs_col": 29, "date_col": 30, "options": ['Sí', 'No', 'Programado', 'No aplica']}
]

def main():
    st.title("📌 Estado de Clientes")
    
    # Botón para abrir la planilla de Google
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

    # Cargar datos (se recargan si hubo una actualización exitosa)
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

    # Botón para buscar el registro
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

    # Pestañas para "Estado Actual" y "Actualizar Registro"
    if st.session_state.rows is not None:
        tab1, tab2 = st.tabs(["📊 Estado Actual", "📝 Actualizar Registro"])
        
        with tab1:
            st.header("Procesos")
            headers = ["Cuenta", "Sector", "Consultoría"] + [p["name"] for p in processes] + ["Última Actualización"]
            table_data = []
            for row_index in st.session_state.rows:
                row = data[row_index - 1]
                row_data = [row[0], row[1], row[2]]
                for proc in processes:
                    cell_val = row[proc["step_col"] - 1] if len(row) >= proc["step_col"] else ""
                    row_data.append(cell_val)
                row_data.append(row[31] if len(row) > 31 else "")
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

            st.subheader("Observaciones")
            sectores_para_cuenta = [row[1] for row in data[1:] if row[0] == selected_cuenta]
            unique_sectores_cuenta = sorted(set(sectores_para_cuenta))
            if (len(st.session_state.selected_sectores) != 1) and (len(unique_sectores_cuenta) != 1):
                st.info("⚠️ Solo se mostrarán las observaciones cuando se seleccione un único sector.")
            else:
                fila_datos = data[st.session_state.rows[0] - 1]
                general_comment = fila_datos[30] if len(fila_datos) > 30 and fila_datos[30].strip() != "" else "Vacío"
                with st.expander("Comentarios Generales", expanded=True):
                    st.write(general_comment)
                for proc in processes:
                    obs_index = proc["obs_col"] - 1
                    obs_value = fila_datos[obs_index] if len(fila_datos) > obs_index and fila_datos[obs_index].strip() != "" else "Vacío"
                    with st.expander(proc["name"], expanded=True):
                        st.write(obs_value)
        
        with tab2:
            with st.form("update_form"):
                st.header("Actualizar Registro")
                fila_index = st.session_state.rows[0] - 1
                fila_datos = data[fila_index]
                
                # Dividir el formulario en dos columnas
                col1, col2 = st.columns(2)
                
                with col1:
                    # Campo de Consultoría
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
                    
                    # Campos dinámicos para los valores de cada proceso
                    process_values = {}
                    for i, proc in enumerate(processes):
                        default_val = fila_datos[proc["step_col"] - 1] if len(fila_datos) >= proc["step_col"] else ""
                        display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                        options_for_select = proc["options"].copy()
                        if display_val not in options_for_select:
                            options_for_select = [display_val] + options_for_select
                        default_index = options_for_select.index(display_val)
                        process_values[proc["name"]] = st.selectbox(proc["name"], options=options_for_select, index=default_index, key=f"process_{i}_update")
                
                with col2:
                    # Campos dinámicos para las observaciones de cada proceso
                    process_obs_values = {}
                    for i, proc in enumerate(processes):
                        default_obs = fila_datos[proc["obs_col"] - 1] if len(fila_datos) >= proc["obs_col"] else ""
                        process_obs_values[proc["name"]] = st.text_area(f"Observaciones - {proc['name']}", value=default_obs, height=68, key=f"obs_{i}_update")
                    
                    # Comentarios generales
                    comentarios_generales = st.text_area("Comentarios generales", value="", height=68, key="comentarios_generales_update")
                
                submitted = st.form_submit_button("Guardar Cambios")
                if submitted:
                    steps_updates = []
                    for proc in processes:
                        steps_updates.append({
                            "step_label": proc["name"],
                            "step_col": proc["step_col"],
                            "obs_col": proc["obs_col"],
                            "date_col": proc["date_col"],
                            "value": process_values[proc["name"]],
                            "obs_value": process_obs_values[proc["name"]]
                        })
                    comentarios_generales_value = st.session_state.get("comentarios_generales_update", "")
                    success = update_steps(st.session_state.rows, steps_updates, consultoria_value, comentarios_generales_value)
                    if success:
                        st.session_state.update_successful = True
                        st.rerun()

if __name__ == "__main__":
    main()
