import streamlit as st
import gspread
from google.auth import default
import pandas as pd
from typing import List, Tuple, Optional, Dict

# ------------------------------
# 1. Autenticación y Conexión con Google Sheets
# ------------------------------

# Para Streamlit se recomienda usar credenciales de servicio o configurar la autenticación
# Por simplicidad usaremos las credenciales por defecto (asegúrate de tener configurada la variable de entorno
# o de usar st.secrets en Streamlit Cloud)
creds, _ = default()
client = gspread.authorize(creds)

# ------------------------------
# 2. Clase para gestionar la Hoja
# ------------------------------
class SheetManager:
    def __init__(self, spreadsheet_url: str):
        self.sheet = client.open_by_url(spreadsheet_url).sheet1
        self.cached_data = None
        self.cached_metadata = None
        self.df = None
        self.refresh_cache()

    def refresh_cache(self):
        """Actualiza el caché de datos y metadata."""
        self.cached_data = self.sheet.get_all_values()
        self.cached_metadata = self.sheet.spreadsheet.fetch_sheet_metadata(
            params={'includeGridData': True}
        )
        # La primera fila es el header
        self.df = pd.DataFrame(self.cached_data[1:], columns=self.cached_data[0])
        
    def get_filtered_rows(self, filter_text: str) -> List[Tuple[str, int]]:
        """Obtiene las filas filtradas usando el DataFrame en memoria.
           Se filtra sobre la columna AF (índice 31, ya que es la 32ª columna)."""
        if not filter_text:
            return []
        
        mask = self.df.iloc[:, 31].str.lower().str.contains(filter_text.lower())
        filtered_df = self.df[mask]
        
        return [
            (f"Fila {idx + 2} - AF: {row.iloc[31]}", idx + 2)
            for idx, row in filtered_df.iterrows()
        ]

    def get_cell_data(self, row: int, col: int) -> Tuple[Optional[str], Optional[str]]:
        """Obtiene el texto y el hipervínculo de una celda desde el caché."""
        sheet_id = self.sheet.id
        grid_data = None
        
        # Buscar en el caché de metadata
        for s in self.cached_metadata.get('sheets', []):
            if s.get('properties', {}).get('sheetId') == sheet_id:
                grid_data = s.get('data', [{}])[0].get('rowData', [])
                break
                
        if not grid_data or len(grid_data) < row:
            return None, None
            
        row_data = grid_data[row - 1]
        if not row_data or 'values' not in row_data:
            return None, None
            
        cell_data = row_data['values'][col - 1] if len(row_data['values']) >= col else {}
        text = cell_data.get('formattedValue', '')
        
        hyperlink = cell_data.get('hyperlink', None)
        if not hyperlink and 'textFormatRuns' in cell_data:
            runs = cell_data['textFormatRuns']
            if runs and isinstance(runs, list):
                first_run = runs[0]
                hyperlink = first_run.get('format', {}).get('link', {}).get('uri', None)
        
        return text, hyperlink

    def update_cell(self, cell_label: str, value: str, color_hex: str):
        """Actualiza una celda y su formato en batch."""
        # Actualizar el valor de la celda
        self.sheet.update_acell(cell_label, value)
        
        # Actualizar el color de fondo
        color_dict = self._hex_to_rgb_dict(color_hex)
        self.sheet.format(cell_label, {"backgroundColor": color_dict})
        
        # Actualizar el caché local
        row, col = self._parse_cell_label(cell_label)
        if len(self.cached_data) >= row:
            row_list = self.cached_data[row - 1]
            if len(row_list) < col:
                row_list.extend([''] * (col - len(row_list)))
            row_list[col - 1] = value

    @staticmethod
    def _hex_to_rgb_dict(hex_color: str) -> Dict[str, float]:
        """Convierte un color hexadecimal a RGB."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        return {"red": r, "green": g, "blue": b}

    @staticmethod
    def _parse_cell_label(cell_label: str) -> Tuple[int, int]:
        """Convierte una etiqueta de celda (ej: 'A1') a coordenadas (fila, columna)."""
        column_str = ''.join(filter(str.isalpha, cell_label))
        row = int(''.join(filter(str.isdigit, cell_label)))
        
        col = 0
        for char in column_str:
            col = col * 26 + (ord(char.upper()) - ord('A') + 1)
        
        return row, col

# ------------------------------
# 3. Inicialización del Manejador de Hojas
# ------------------------------
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Pf8jVE6pK9_qpe2QR6tH-dmKfCvtaObDOMpG7Jddmno/edit?gid=0#gid=0"
sheet_manager = SheetManager(SPREADSHEET_URL)

# ------------------------------
# 4. Interfaz en Streamlit
# ------------------------------

st.title("Editor de Google Sheets")

st.markdown("### Filtrar filas por Encargado (columna AF)")
filter_text = st.text_input("Buscar (Encargado):", value="")

# Obtener las filas filtradas
filtered_rows = sheet_manager.get_filtered_rows(filter_text)

if not filtered_rows:
    st.info("No se encontraron filas con ese filtro.")
else:
    # Se utiliza un selectbox para elegir la fila; se muestran las opciones con su descripción
    # Usamos una key para poder actualizar el valor en session_state si es necesario
    selected_option = st.selectbox("Fila:", options=filtered_rows, format_func=lambda x: x[0], key="selected_option")
    selected_row = selected_option[1]

    # Obtener la información de la fila completa (recordar que la primera fila es el header)
    row_data = sheet_manager.cached_data[selected_row - 1]

    st.markdown("### Vista Previa de Datos del Cliente")
    # Vista previa del Equipo (columna E)
    text_equipo, hyperlink_equipo = sheet_manager.get_cell_data(selected_row, 5)
    if hyperlink_equipo and text_equipo:
        st.markdown(f'<b>Equipo:</b> <a href="{hyperlink_equipo}" target="_blank">{text_equipo}</a>', unsafe_allow_html=True)
    else:
        st.markdown(f"<b>Equipo:</b> {text_equipo or 'No disponible'}", unsafe_allow_html=True)
    
    # Vista previa de la Cuenta (columna B)
    marca = row_data[1] if len(row_data) > 1 else "No disponible"
    st.markdown(f"<b>Cuenta:</b> {marca}", unsafe_allow_html=True)
    
    # Vista previa del Campo (nombre del cliente, columna C)
    nombre = row_data[2] if len(row_data) > 2 else "No disponible"
    st.markdown(f"<b>Campo:</b> {nombre}", unsafe_allow_html=True)

    st.markdown("### Comentarios")
    # Campo para definir la columna de revisión (por defecto "DJ")
    col_letter = st.text_input("Columna:", value="DJ")
    
    # Determinar el índice de la columna basado en la etiqueta
    col_index = sheet_manager._parse_cell_label(f"{col_letter}1")[1]
    
    # Comentario actual (valor en la celda de la fila seleccionada y columna especificada)
    current_comment = row_data[col_index - 1] if len(row_data) >= col_index else ""
    new_comment = st.text_input("Comentario:", value=current_comment, key="comment_input")
    
    # Comentario anterior: se toma de la columna anterior a la de revisión
    prev_col_index = col_index - 1
    prev_comment = (
        row_data[prev_col_index - 1]
        if prev_col_index > 0 and len(row_data) >= prev_col_index
        else "Sin comentario anterior."
    )
    st.markdown(f"<b>Comentario anterior:</b> {prev_comment}", unsafe_allow_html=True)
    
    st.markdown("### Selección de Formato")
    # Dropdown para elegir el color de fondo a aplicar en la celda actualizada
    color_options = {
        'Verde claro (#b6d7a8)': '#b6d7a8',
        'Rojo (#ff0000)': '#ff0000',
        'Amarillo (#ffff00)': '#ffff00'
    }
    selected_color_label = st.selectbox("Color:", list(color_options.keys()))
    selected_color = color_options[selected_color_label]
    
    st.markdown("---")
    if st.button("Guardar cambios"):
        # Construir la etiqueta de la celda (ej: "DJ5")
        cell_label = f"{col_letter}{selected_row}"
        try:
            sheet_manager.update_cell(cell_label, new_comment, selected_color)
            st.success(f"Celda {cell_label} actualizada exitosamente.")
            
            # Refrescar el caché para actualizar la información
            sheet_manager.refresh_cache()
            
            # Intentar avanzar a la siguiente fila dentro de las filas filtradas
            current_index = next((i for i, opt in enumerate(filtered_rows) if opt[1] == selected_row), None)
            if current_index is not None and current_index < len(filtered_rows) - 1:
                next_option = filtered_rows[current_index + 1]
                st.session_state.selected_option = next_option
                st.info("Avanzando a la siguiente fila.")
                # Se recomienda recargar la página para ver la fila actualizada
                st.experimental_rerun()
            else:
                st.info("Esta es la última fila disponible.")
        except Exception as e:
            st.error(f"Error al actualizar la celda: {e}")
