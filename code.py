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

@st.cache_resource
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

@st.cache_data(show_spinner=False)
def load_all_data(spreadsheet_url):
    """Carga y cachea todos los datos de la hoja."""
    client = init_connection()
    sheet = client.open_by_url(spreadsheet_url).sheet1
    return sheet.get_all_values()

@st.cache_data(show_spinner=False)
def get_sheet_metadata(spreadsheet_url):
    """Carga y cachea la metadata de la hoja (incluyendo grid data)."""
    client = init_connection()
    sheet = client.open_by_url(spreadsheet_url).sheet1
    return sheet.spreadsheet.fetch_sheet_metadata(params={'includeGridData': True})

def get_cell_data_with_hyperlink(worksheet, row, col, metadata=None):
    """
    Obtiene el texto formateado y el hipervínculo (si existe) de una celda
    usando la API de Google Sheets con includeGridData=True.

    Args:
        worksheet: Objeto Worksheet de gspread.
        row (int): Número de fila (1-indexado).
        col (int): Número de columna (1-indexado).
        metadata (dict, optional): Metadata pre-cargada de la hoja. Si no se proporciona,
                                   se hará una llamada a fetch_sheet_metadata.

    Returns:
        tuple: (texto, hyperlink) donde texto es el valor formateado y 
               hyperlink es el vínculo asociado (o None si no existe).
    """
    try:
        if metadata is None:
            metadata = worksheet.spreadsheet.fetch_sheet_metadata(params={'includeGridData': True})
        sheet_id = worksheet.id
        grid_data = None
        for s in metadata.get('sheets', []):
            if s.get('properties', {}).get('sheetId') == sheet_id:
                grid_data = s.get('data', [{}])[0].get('rowData', [])
                break
        if grid_data is None or len(grid_data) < row:
            return None, None

        row_data = grid_data[row - 1]
        if not row_data or 'values' not in row_data:
            return None, None

        cell_data = row_data['values'][col - 1] if len(row_data['values']) >= col else {}
        text = cell_data.get('formattedValue', '')

        # Buscamos el vínculo directo
        hyperlink = cell_data.get('hyperlink', None)

        # Si no se encontró, revisamos en textFormatRuns (texto enriquecido)
        if not hyperlink and 'textFormatRuns' in cell_data:
            runs = cell_data['textFormatRuns']
            if runs and isinstance(runs, list):
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
        spreadsheet_url = st.secrets["spreadsheet_url"]
        # Precargamos los datos y la metadata en caché
        all_data = load_all_data(spreadsheet_url)
        metadata = get_sheet_metadata(spreadsheet_url)

        st.subheader("Búsqueda por columna AF")
        filter_text = st.text_input("Ingrese el texto de búsqueda para la columna AF:")

        if filter_text:
            matching_rows = []
            # La columna AF es la 32 (1-indexado) -> índice 31 en la lista
            for idx, row in enumerate(all_data, start=1):
                if len(row) >= 32 and filter_text.lower() in row[31].lower():
                    matching_rows.append((idx, row))

            if matching_rows:
                # Permite seleccionar la fila mostrando el contenido de la columna AF
                opciones = {
                    f"Fila {fila} - AF: {fila_data[31]}": (fila, fila_data)
                    for fila, fila_data in matching_rows
                }
                opcion_seleccionada = st.selectbox("Seleccione la fila a editar:", list(opciones.keys()))
                selected_row, selected_row_data = opciones[opcion_seleccionada]

                st.markdown("---")
                st.subheader("Vista previa de la columna E")
                # La columna E es la 5 (1-indexado)
                text, hyperlink = get_cell_data_with_hyperlink(sheet, selected_row, 5, metadata=metadata)
                if text is None:
                    st.write("No se pudo obtener el contenido de la celda.")
                else:
                    if hyperlink:
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
                        # Limpiar caché para recargar la información actualizada
                        load_all_data.clear()
                        get_sheet_metadata.clear()
                        st.success(f"La celda {cell_label} se actualizó correctamente.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar la celda: {e}")
            else:
                st.warning("No se encontraron filas que coincidan con el filtro en la columna AF.")
    else:
        st.error("No se pudo cargar la planilla.")
else:
    st.error("No se pudo establecer la conexión con Google Sheets.")
