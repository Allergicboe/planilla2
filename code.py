import streamlit as st
import gspread
from google.oauth2 import service_account

# Configuración de la página
st.set_page_config(
    page_title="Formulario de Planilla",
    page_icon="📄",
    layout="wide"
)

# ----------------------------
# Funciones de conexión y carga
# ----------------------------
def init_connection():
    """Inicializa la conexión con Google Sheets."""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error en la conexión: {str(e)}")
        return None

def load_sheet(client):
    """Carga la hoja de trabajo de Google Sheets."""
    try:
        return client.open_by_url(st.secrets["spreadsheet_url"]).sheet1
    except Exception as e:
        st.error(f"Error al cargar la planilla: {str(e)}")
        return None

def get_cell_data_with_hyperlink(worksheet, row, col):
    """
    Obtiene el texto formateado y el hipervínculo (si existe) de una celda
    usando la API de Google Sheets con includeGridData=True.

    Args:
        worksheet: Objeto Worksheet de gspread.
        row (int): Número de fila (1-indexado).
        col (int): Número de columna (1-indexado).

    Returns:
        tuple: (texto, hyperlink) donde texto es el valor formateado y 
               hyperlink es el vínculo asociado (o None si no existe).
    """
    try:
        # Obtener la metadata de la hoja incluyendo la grid data
        metadata = worksheet.spreadsheet.fetch_sheet_metadata(params={'includeGridData': True})
        sheet_id = worksheet.id
        grid_data = None
        for s in metadata.get('sheets', []):
            if s.get('properties', {}).get('sheetId') == sheet_id:
                # Usamos el primer bloque de datos (en caso de que haya más de uno)
                grid_data = s.get('data', [{}])[0].get('rowData', [])
                break
        if grid_data is None or len(grid_data) < row:
            return None, None

        # Accedemos a la fila correspondiente (recordar que grid_data es 0-indexado)
        row_data = grid_data[row - 1]
        if not row_data or 'values' not in row_data:
            return None, None

        # Nos aseguramos de que la fila tenga suficientes columnas
        cell_data = row_data['values'][col - 1] if len(row_data['values']) >= col else {}
        text = cell_data.get('formattedValue', '')

        # Primero, intentamos obtener el vínculo directamente (si está definido en la propiedad "hyperlink")
        hyperlink = cell_data.get('hyperlink', None)

        # Si no se encontró, revisamos los textFormatRuns (en caso de texto enriquecido)
        if not hyperlink and 'textFormatRuns' in cell_data:
            runs = cell_data['textFormatRuns']
            if runs and isinstance(runs, list):
                # Suponemos que toda la celda está enlazada y usamos el primer bloque
                first_run = runs[0]
                hyperlink = first_run.get('format', {}).get('link', {}).get('uri', None)

        return text, hyperlink
    except Exception as e:
        st.error(f"Error al obtener datos de la celda: {e}")
        return None, None

# ----------------------------
# Inicio de la aplicación
# ----------------------------
st.header("Aplicación de edición de planilla")

client = init_connection()
if client:
    sheet = load_sheet(client)
    if sheet:
        # Obtenemos todos los datos para filtrar (la columna AF es la 32, índice 31)
        all_data = sheet.get_all_values()

        st.subheader("Búsqueda por columna AF")
        filter_text = st.text_input("Ingrese el texto de búsqueda para la columna AF:")

        if filter_text:
            matching_rows = []
            for idx, row in enumerate(all_data, start=1):
                if len(row) >= 32 and filter_text.lower() in row[31].lower():
                    matching_rows.append((idx, row))

            if matching_rows:
                # Permite seleccionar la fila; se muestra el contenido de la columna AF para identificarla
                opciones = {f"Fila {fila} - AF: {fila_data[31]}": (fila, fila_data)
                            for fila, fila_data in matching_rows}
                opcion_seleccionada = st.selectbox("Seleccione la fila a editar:", list(opciones.keys()))
                selected_row, selected_row_data = opciones[opcion_seleccionada]

                st.markdown("---")
                st.subheader("Vista previa de la columna E")
                # Columna E es la 5 (1-indexado)
                text, hyperlink = get_cell_data_with_hyperlink(sheet, selected_row, 5)
                if text is None:
                    st.write("No se pudo obtener el contenido de la celda.")
                else:
                    if hyperlink:
                        # Se renderiza el enlace usando HTML
                        link_html = f'<a href="{hyperlink}" target="_blank">{text}</a>'
                        st.markdown(link_html, unsafe_allow_html=True)
                    else:
                        st.write(text)

                st.markdown("---")
                st.subheader("Editar celda de la fila seleccionada")
                st.info(f"Fila seleccionada: **{selected_row}**")

                # Selección de la columna a editar (por ejemplo: "DJ")
                col_letter = st.text_input("Ingrese la letra de la columna a editar (ej: DJ):", value="DJ")
                cell_label = f"{col_letter}{selected_row}"

                try:
                    current_value = sheet.acell(cell_label).value
                except Exception as e:
                    current_value = ""
                new_value = st.text_input(f"Valor actual en {cell_label} (editar):", value=current_value, key="edit_val")

                if st.button("Guardar cambios"):
                    try:
                        sheet.update_acell(cell_label, new_value)
                        st.success(f"La celda {cell_label} se actualizó correctamente.")
                    except Exception as e:
                        st.error(f"Error al actualizar la celda: {e}")
            else:
                st.warning("No se encontraron filas que coincidan con el filtro en la columna AF.")
    else:
        st.error("No se pudo cargar la planilla.")
else:
    st.error("No se pudo establecer la conexión con Google Sheets.")
