import os
import sqlite3
import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu

# Configuración de la aplicación
st.set_page_config(page_title="Dashboard Multi-Excel con Anotaciones y Estados", layout="wide")
st.title("Dashboard Judicial")

# Ruta principal donde están las carpetas
BASE_FOLDER_PATH = r"C:\\Users\\Marketing\\Documents\\Informes"

# Rutas dinámicas de carpetas por sección (se detectan automáticamente las carpetas principales)
def obtener_carpetas_principales(base_path):
    try:
        return {folder: os.path.join(base_path, folder) for folder in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, folder))}
    except Exception as e:
        st.error(f"Error al obtener carpetas principales: {e}")
        return {}

CARPETAS = obtener_carpetas_principales(BASE_FOLDER_PATH)

# Ruta de la base de datos SQLite
DB_PATH = "anotaciones.db"

# Crear conexión a la base de datos
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Crear tabla para almacenar anotaciones
c.execute('''
CREATE TABLE IF NOT EXISTS anotaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo TEXT,
    hoja TEXT,
    fila INTEGER,
    columna TEXT,
    anotacion TEXT,
    estado TEXT,
    seccion TEXT
)
''')
conn.commit()

# Crear tabla para almacenar usuarios
c.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    rol TEXT
)
''')
conn.commit()

# Agregar usuarios predefinidos
usuarios_predefinidos = [
    ("admin", "admin123", "admin"),
    ("usuario", "usuario123", "usuario")
]
for username, password, rol in usuarios_predefinidos:
    try:
        c.execute("INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)", (username, password, rol))
    except sqlite3.IntegrityError:
        pass  # Ignorar si el usuario ya existe
conn.commit()

# Función para autenticar usuarios
def autenticar_usuario(username, password):
    query = "SELECT rol FROM usuarios WHERE username = ? AND password = ?"
    result = c.execute(query, (username, password)).fetchone()
    return result[0] if result else None

# Función para crear usuarios
def crear_usuario(username, password, rol):
    try:
        query = "INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)"
        c.execute(query, (username, password, rol))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# Función para obtener anotaciones desde la base de datos por sección
def obtener_anotaciones(archivo, hoja, seccion):
    query = "SELECT * FROM anotaciones WHERE archivo = ? AND hoja = ? AND seccion = ?"
    return pd.read_sql_query(query, conn, params=(archivo, hoja, seccion))

# Función para agregar una anotación a la base de datos
def agregar_anotacion(archivo, hoja, fila, columna, anotacion, estado, seccion):
    query = "INSERT INTO anotaciones (archivo, hoja, fila, columna, anotacion, estado, seccion) VALUES (?, ?, ?, ?, ?, ?, ?)"
    c.execute(query, (archivo, hoja, fila, columna, anotacion, estado, seccion))
    conn.commit()

# Función para actualizar el estado de una anotación en la base de datos
def actualizar_estado_anotacion(id_anotacion, nuevo_estado):
    query = "UPDATE anotaciones SET estado = ? WHERE id = ?"
    c.execute(query, (nuevo_estado, id_anotacion))
    conn.commit()

# Función para eliminar una anotación de la base de datos
def eliminar_anotacion(id_anotacion):
    query = "DELETE FROM anotaciones WHERE id = ?"
    c.execute(query, (id_anotacion,))
    conn.commit()

# Obtener archivos Excel desde una carpeta específica
@st.cache_data
def get_excel_files(folder_path):
    try:
        return [f for f in os.listdir(folder_path) if f.endswith(".xlsx")]
    except Exception as e:
        st.error(f"Error al acceder a la carpeta: {e}")
        return []

# Interfaz de inicio de sesión
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['rol'] = None

def login():
    st.sidebar.title("Inicio de sesión")
    username = st.sidebar.text_input("Usuario")
    password = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Iniciar sesión"):
        rol = autenticar_usuario(username, password)
        if rol:
            st.session_state['logged_in'] = True
            st.session_state['rol'] = rol
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

if not st.session_state['logged_in']:
    login()
else:
    # Mostrar interfaz principal después de iniciar sesión
    st.sidebar.title("Menú Principal")

    # Navbar (barra de navegación)
    selected_section = option_menu(
        menu_title=None,
        options=list(CARPETAS.keys()),
        icons=["shield-lock", "house", "briefcase"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
    )

    # Procesar la sección seleccionada
    folder_path = CARPETAS[selected_section]

    # Botón para refrescar la lista de archivos
    if st.sidebar.button("Actualizar Archivos"):
        get_excel_files.clear()
        st.sidebar.success("Archivos actualizados correctamente.")

    # Funcionalidad adicional para el administrador
    if st.session_state['rol'] == 'admin':
        st.sidebar.title("Administración de Usuarios")
        with st.sidebar.form("Crear Usuario"):
            nuevo_usuario = st.text_input("Nuevo Usuario")
            nueva_contraseña = st.text_input("Contraseña", type="password")
            nuevo_rol = st.selectbox("Rol", ["admin", "usuario"])
            crear_usuario_submit = st.form_submit_button("Crear Usuario")

            if crear_usuario_submit:
                if crear_usuario(nuevo_usuario, nueva_contraseña, nuevo_rol):
                    st.sidebar.success("Usuario creado exitosamente.")
                else:
                    st.sidebar.error("El usuario ya existe.")

    # Detectar archivos Excel en la carpeta seleccionada
    excel_files = get_excel_files(folder_path)
    if not excel_files:
        st.info(f"No se encontraron archivos Excel en la carpeta: {folder_path}")
    else:
        # Opciones en la barra lateral
        st.sidebar.title("Opciones")
        view_option = st.sidebar.radio(
            "Selecciona una vista:",
            ["Por Archivo y Hoja", "Resumen de Anotaciones Global"]
        )

        if view_option == "Por Archivo y Hoja":
            # Selección de archivo
            selected_file = st.sidebar.radio("Selecciona un archivo:", excel_files)

            # Ruta completa del archivo seleccionado
            file_path = os.path.join(folder_path, selected_file)

            # Cargar las hojas del archivo seleccionado
            try:
                data = pd.ExcelFile(file_path)
                sheet_names = data.sheet_names

                st.sidebar.markdown(f"**Hojas de {selected_file}:**")
                selected_sheet = st.sidebar.radio("Selecciona una hoja:", sheet_names)

                # Mostrar datos de la hoja seleccionada
                st.write(f"### Datos de la hoja: {selected_sheet}")
                df = data.parse(selected_sheet)
                st.dataframe(df)

                # Obtener anotaciones existentes desde la base de datos
                anotaciones_df = obtener_anotaciones(selected_file, selected_sheet, selected_section)
                st.write("### Anotaciones Guardadas para esta Hoja")
                st.dataframe(anotaciones_df)

                # Formulario para agregar anotaciones
                st.write("### Agregar Anotaciones")
                with st.form("Agregar Anotación"):
                    fila = st.number_input("Número de fila:", min_value=0, max_value=len(df) - 1, step=1)
                    columna = st.selectbox("Columna:", df.columns)
                    comentario = st.text_area("Anotación:")
                    estado = st.selectbox("Estado:", ["Pendiente", "Solucionado", "En Revisión"])
                    submit = st.form_submit_button("Guardar Anotación")

                    if submit:
                        agregar_anotacion(selected_file, selected_sheet, fila, columna, comentario, estado, selected_section)
                        st.success("Anotación guardada.")

                if st.session_state['rol'] == 'admin':
                    # Formulario para editar estado de anotaciones
                    st.write("### Editar Estado de una Anotación")
                    if anotaciones_df.empty:
                        st.warning("No hay data para editar.")
                    else:
                        with st.form("Editar Estado"):
                            id_anotacion = st.selectbox("Seleccione la anotación:", anotaciones_df["id"])
                            nuevo_estado = st.selectbox("Nuevo Estado:", ["Pendiente", "Solucionado", "En Revisión"])
                            submit_editar = st.form_submit_button("Actualizar Estado")

                            if submit_editar:
                                actualizar_estado_anotacion(id_anotacion, nuevo_estado)
                                st.success("Estado actualizado.")

                    # Formulario para eliminar anotaciones
                    st.write("### Eliminar una Anotación")
                    if anotaciones_df.empty:
                        st.warning("No hay data para eliminar.")
                    else:
                        with st.form("Eliminar Anotación"):
                            id_anotacion_eliminar = st.selectbox("Seleccione la anotación a eliminar:", anotaciones_df["id"])
                            submit_eliminar = st.form_submit_button("Eliminar Anotación")

                            if submit_eliminar:
                                eliminar_anotacion(id_anotacion_eliminar)
                                st.success("Anotación eliminada.")

                                # Recargar anotaciones después de eliminar
                                anotaciones_df = obtener_anotaciones(selected_file, selected_sheet, selected_section)
                                st.write("### Anotaciones Actualizadas para esta Hoja")
                                st.dataframe(anotaciones_df)

            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

        elif view_option == "Resumen de Anotaciones Global":
            # Resumen global de anotaciones por sección
            st.write(f"### Resumen de Anotaciones en la Sección: {selected_section}")
            query = "SELECT * FROM anotaciones WHERE seccion = ?"
            resumen_df = pd.read_sql_query(query, conn, params=(selected_section,))
            st.dataframe(resumen_df)