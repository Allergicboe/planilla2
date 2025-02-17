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

def parse_hyperlink_formula(formula):
    """
    Dado una fórmula HYPERLINK del tipo:
      =HYPERLINK("https://ejemplo.com", "Texto")
    retorna una tupla (url, texto). Si no es una fórmula de hipervínculo, retorna (None, None).
    """
    match = re.match(r'=HYPERLINK\("([^"]+)"\s*,\s*"([^"]+)"\)', formula)
    if match:
        return match.group(1), match.group(2)
    return None, None

# ----------------------------
# Inicio de la aplicación
# ----------------------------
st.header("Aplicación de edición de planilla")

client = init_connection()
if client:
    sheet = load_sheet(client)
    if sheet:
        # Se obtienen todos los datos para el filtrado (pero para la columna E se usará la celda con value_render_option=FORMULA)
        all_data = sheet.get_all_values()
        
        st.subheader("Búsqueda por columna AF")
        filter_text = st.text_input("Ingrese el texto de búsqueda para la columna AF:")

        if filter_text:
            # Filtra las filas que tengan coincidencia en la columna AF (columna AF es la 32, índice 31)
            matching_rows = []
            for idx, row in enumerate(all_data, start=1):
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
                # Usamos la celda de la columna E (índice 5, ya que la numeración en Sheets es 1-indexada)
                try:
                    # Solicitamos la fórmula de la celda (si tiene HYPERLINK se verá)
                    cell_e = sheet.cell(selected_row, 5, value_render_option="FORMULA")
                    cell_e_value = cell_e.value if cell_e.value else ""
                    
                    # Si es una fórmula HYPERLINK, extraemos el URL y el texto
                    if cell_e_value.startswith("=HYPERLINK"):
                        url, text_link = parse_hyperlink_formula(cell_e_value)
                        if url and text_link:
                            link_html = f'<a href="{url}" target="_blank">{text_link}</a>'
                            st.markdown(link_html, unsafe_allow_html=True)
                        else:
                            st.write("Formato de HYPERLINK no reconocido:", cell_e_value)
                    # Si no es una fórmula, pero parece un URL, lo mostramos como enlace
                    elif re.match(r'https?://', cell_e_value):
                        link_html = f'<a href="{cell_e_value}" target="_blank">{cell_e_value}</a>'
                        st.markdown(link_html, unsafe_allow_html=True)
                    else:
                        st.write(cell_e_value)
                except Exception as e:
                    st.error(f"Error al obtener el valor de la columna E: {e}")
                
                st.markdown("---")
                st.subheader("Editar celda de la fila seleccionada")
                st.info(f"Fila seleccionada: **{selected_row}**")
                
                # Selección de la columna a editar (por ejemplo: "DJ")
                col_letter = st.text_input("Ingrese la letra de la columna a editar (ej: DJ):", value="DJ")
                
                # Obtener el valor actual de la celda a editar (con valor renderizado normal)
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
