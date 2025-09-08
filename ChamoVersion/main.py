import streamlit as st
from db import test_connection, get_session, User, Product, Store, init_db

# Inicializa la base de datos si la conexión es válida
if test_connection():
    init_db()  # Esto crea las tablas si no existen
    session = get_session()
    users = session.query(User).count()
    print(f"Usuarios en la base: {users}")
else:
    print("No se pudo conectar a la base de datos")

st.set_page_config(page_title="Sistema Panadería", layout="centered")

st.title("🍞 Sistema de Panadería con Aiven")

# Verificar conexión
st.subheader("🔄 Verificando conexión a Aiven...")
if test_connection():
    st.success("Conexión a Aiven exitosa")

    session = get_session()
    try:
        users = session.query(User).count()
        products = session.query(Product).count()
        stores = session.query(Store).count()

        st.subheader("📊 Estado actual:")
        st.write(f"👥 Usuarios: {users}")
        st.write(f"🛒 Productos: {products}")
        st.write(f"🏪 Tiendas: {stores}")
    finally:
        session.close()
else:
    st.error("Error de conexión - verifica credenciales de Aiven")

st.info("Login: admin / admin123")



