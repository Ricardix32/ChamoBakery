# ===================================================
# EJECUCIÓN FINAL - SISTEMA PANADERÍA CON AIVEN
# ===================================================

# PASO 1: Verificar que tienes los archivos
import os

print("📁 Verificando archivos...")
if os.path.exists('db.py'):
    print("✅ db.py encontrado")
else:
    print("❌ db.py no encontrado - debes ejecutar el código anterior primero")

if os.path.exists('app.py'):
    print("✅ app.py encontrado")
else:
    print("❌ app.py no encontrado - crea el archivo con el código que tienes")

# PASO 2: Verificar conexión a base de datos
try:
    print("\n🔄 Verificando conexión a Aiven...")
    from db import test_connection, get_session, User, Product, Store

    if test_connection():
        print("✅ Conexión a Aiven exitosa")

        # Verificar datos
        session = get_session()
        try:
            users = session.query(User).count()
            products = session.query(Product).count()
            stores = session.query(Store).count()

            print(f"\n📊 Estado actual:")
            print(f"  👥 Usuarios: {users}")
            print(f"  🛒 Productos: {products}")
            print(f"  🏪 Tiendas: {stores}")
        finally:
            session.close()

    else:
        print("❌ Error de conexión - verifica credenciales de Aiven")

except Exception as e:
    print(f"❌ Error: {e}")

# PASO 3: Lanzar aplicación Streamlit
print("\n🚀 Iniciando aplicación...")

import threading
import time
import subprocess

def run_streamlit():
    """Ejecutar Streamlit en segundo plano"""
    subprocess.run([
        "streamlit", "run", "app.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false"
    ])

# Iniciar Streamlit en hilo separado
print("⏳ Iniciando Streamlit...")
thread = threading.Thread(target=run_streamlit)
thread.daemon = True
thread.start()

# Esperar que inicie
time.sleep(15)

print("🎉 ¡APLICACIÓN LISTA!")
print("=" * 50)
print("💾 Base de datos: Aiven PostgreSQL (en la nube)")
print("🔐 Usuario: admin")
print("🔐 Contraseña: admin123")
print("📍 URL local: http://localhost:8501")
print("=" * 50)

# PASO 4: Configurar ngrok para acceso público (opcional)
try:
    from pyngrok import ngrok
    import getpass

    # Limpiar conexiones previas
    try:
        ngrok.disconnect_all()
        ngrok.kill()
        time.sleep(2)
    except:
        pass

    print("\n🌐 ¿Quieres URL pública?")
    use_ngrok = input("¿Configurar ngrok? (s/n): ").lower().strip()

    if use_ngrok in ['s', 'si', 'y', 'yes']:
        ngrok_token = getpass.getpass("Token de ngrok: ")

        if ngrok_token.strip():
            ngrok.set_auth_token(ngrok_token)
            public_url = ngrok.connect(8501)

            print(f"\n🌍 URL PÚBLICA: {public_url}")
            print("📱 Comparte esta URL para acceso remoto")
            print("🔐 Credenciales: admin / admin123")

            print("\n⏳ Manteniendo aplicación activa...")
            print("   (Presiona Ctrl+C para detener)")

            try:
                while True:
                    time.sleep(60)
                    print(".", end="", flush=True)
            except KeyboardInterrupt:
                print("\n🛑 Deteniendo aplicación...")
                ngrok.disconnect_all()
        else:
            print("🏠 Sin ngrok - solo acceso local")
    else:
        print("🏠 Acceso solo local configurado")

except ImportError:
    print("📱 ngrok no disponible - solo acceso local")

# Mantener aplicación local activa
try:
    print("\n⏳ Aplicación activa en localhost:8501")
    print("   (Presiona Ctrl+C para detener)")
    while True:
        time.sleep(30)
        print(".", end="", flush=True)
except KeyboardInterrupt:
    print("\n🛑 Aplicación detenida")

print("\n🎯 RESUMEN FINAL:")
print("✅ Base de datos: Aiven PostgreSQL")
print("✅ Aplicación: Sistema de Panadería")
print("✅ Datos: Persistentes en la nube")
print("✅ Login: admin / admin123")