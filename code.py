import streamlit as st
import gspread
from google.oauth2 import service_account
import re

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

# ----------------------------
# Inicio de la aplicación
# ----------------------------
st.header("Aplicación de edición de planilla")

client = init_connection()
if client:
    sheet = load_sheet(client)
    if sheet:
        # Obtiene todos los datos de la hoja
        all_data = sheet.get_all_values()
        
        st.subheader("Búsqueda por columna AF")
        filter_text = st.text_input("Ingrese el texto de búsqueda para la columna AF:")

        if filter_text:
            # Filtra las filas que tengan coincidencia en la columna AF (AF es la columna 32, índice 31)
            matching_rows = []
            for idx, row in enumerate(all_data, start=1):
                # Verifica que la fila tenga al menos 32 columnas
                if len(row) >= 32 and filter_text.lower() in row[31].lower():
                    matching_rows.append((idx, row))
            
            if matching_rows:
                # Permite elegir la fila deseada (se muestra el valor de la columna AF para identificarla)
                opciones = {f"Fila {fila} - AF: {fila_data[31]}": (fila, fila_data) 
                            for fila, fila_data in matching_rows}
                opcion_seleccionada = st.selectbox("Seleccione la fila a editar:", list(opciones.keys()))
                selected_row, selected_row_data = opciones[opcion_seleccionada]
                
                st.markdown("---")
                st.subheader("Vista previa de la columna E")
                # Columna E es la columna 5 (índice 4)
                if len(selected_row_data) >= 5:
                    col_e_value = selected_row_data[4]
                    # Si el valor de la columna E parece una URL, se muestra como hipervínculo
                    if re.match(r'https?://', col_e_value):
                        link_html = f'<a href="{col_e_value}" target="_blank">{col_e_value}</a>'
                        st.markdown(link_html, unsafe_allow_html=True)
                    else:
                        st.write(col_e_value)
                else:
                    st.write("La fila seleccionada no contiene datos en la columna E.")
                
                st.markdown("---")
                st.subheader("Editar celda de la fila seleccionada")
                st.info(f"Fila seleccionada: **{selected_row}**")
                
                # Selección de la columna a editar (por ejemplo: "DJ")
                col_letter = st.text_input("Ingrese la letra de la columna a editar (ej: DJ):", value="DJ")
                
                # Intenta obtener el valor actual de la celda a editar
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
