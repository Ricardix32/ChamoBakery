import os
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
import streamlit as st
import pandas as pd
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from fpdf import FPDF
import base64


# Importar desde tu db.py
try:
    from db import (
        engine, get_session, init_db,
        Store, Supplier, Ingredient, Product, Order, OrderItem, User, Customer
    )
except ImportError as e:
    st.error(f"Error al importar db.py: {e}")
    st.stop()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="🥖 Panadería - Gestión",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INICIALIZAR DB ---
try:
    init_db(drop=False)
except Exception as e:
    st.error(f"Error al inicializar la base de datos: {e}")

# --- FUNCIONES HELPER ---
def format_money(x):
    try:
        return f"S/ {Decimal(x):.2f}"
    except Exception:
        return str(x)

# Función corregida para generar PDF
from fpdf import FPDF

def generar_pdf(ticket_html, filename):
    try:
        import re
        from html import unescape
        from datetime import datetime
        
        # Función helper para extraer texto del HTML
        def extraer_texto(patron, html, default=""):
            match = re.search(patron, html, re.DOTALL | re.IGNORECASE)
            return unescape(match.group(1).strip()) if match else default
        
        # Extraer información del ticket
        orden_id = extraer_texto(r'TICKET DE VENTA #(\d+)', ticket_html, "N/A")
        fecha = extraer_texto(r'Fecha: ([^<\n]+)', ticket_html, datetime.now().strftime("%d/%m/%Y %H:%M"))
        cajero = extraer_texto(r'Cajero: ([^<\n]+)', ticket_html, "N/A")
        total = extraer_texto(r'TOTAL:\s*([^<\n]+)', ticket_html, "S/ 0.00")
        
        # Extraer datos de la tienda
        tienda_nombre = extraer_texto(r'<h2[^>]*>([^<]+)</h2>', ticket_html, "Panadería El Buen Pan")
        tienda_direccion = extraer_texto(r'<p[^>]*>([^<]+)</p>', ticket_html, "Av. Principal 123, Lima")
        tienda_telefono = extraer_texto(r'Tel:\s*([^<\n]+)', ticket_html, "999-888-777")
        
        # Extraer información del cliente
        cliente_info = None
        if "CLIENTE:" in ticket_html:
            cliente_match = re.search(r'CLIENTE:</strong><br>\s*([^<]+)<br>\s*([^<]+)<br>(?:\s*([^<]+)<br>)?', ticket_html, re.DOTALL)
            if cliente_match:
                cliente_info = {
                    'nombre': cliente_match.group(1).strip(),
                    'documento': cliente_match.group(2).strip(),
                    'telefono': cliente_match.group(3).strip() if cliente_match.group(3) else ""
                }
        
        # Extraer items de la tabla
        items = []
        tabla_match = re.search(r'<tbody>(.*?)</tbody>', ticket_html, re.DOTALL)
        if tabla_match:
            filas = re.findall(r'<tr[^>]*>(.*?)</tr>', tabla_match.group(1), re.DOTALL)
            for fila in filas:
                celdas = re.findall(r'<td[^>]*[^>]*>([^<]*)</td>', fila, re.DOTALL)
                if len(celdas) >= 4:
                    items.append({
                        'producto': celdas[0].strip(),
                        'cantidad': celdas[1].strip(),
                        'precio': celdas[2].strip(),
                        'subtotal': celdas[3].strip()
                    })
        
        # Crear PDF
        pdf = FPDF("P", "mm", (80, 200))
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        
        # Encabezado
        pdf.cell(0, 8, tienda_nombre.replace("🥖", "").strip(), ln=True, align="C")
        pdf.set_font("Arial", size=9)
        pdf.cell(0, 5, tienda_direccion, ln=True, align="C")
        pdf.cell(0, 5, f"Tel: {tienda_telefono}", ln=True, align="C")
        pdf.ln(5)
        pdf.cell(0, 0, "-"*32, ln=True, align="C")
        pdf.ln(3)

        # Info de ticket
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 5, f"Ticket: #{orden_id}", ln=True)
        pdf.set_font("Arial", size=9)
        pdf.cell(0, 5, f"Fecha: {fecha}", ln=True)
        pdf.cell(0, 5, f"Cajero: {cajero}", ln=True)
        
        # Información del cliente si existe
        if cliente_info:
            pdf.ln(3)
            pdf.cell(0, 0, "-"*32, ln=True, align="C")
            pdf.ln(2)
            pdf.set_font("Arial", "B", 9)
            pdf.cell(0, 4, "CLIENTE:", ln=True)
            pdf.set_font("Arial", size=8)
            pdf.cell(0, 4, cliente_info['nombre'], ln=True)
            pdf.cell(0, 4, cliente_info['documento'], ln=True)
            if cliente_info['telefono']:
                pdf.cell(0, 4, cliente_info['telefono'], ln=True)
        
        pdf.ln(3)
        pdf.cell(0, 0, "-"*32, ln=True, align="C")
        pdf.ln(3)

        # Tabla de items con datos reales
        pdf.set_font("Courier", "B", 8)
        pdf.set_left_margin(8)
        
        # Encabezados de tabla
        pdf.cell(22, 5, "Producto", border=0)
        pdf.cell(8, 5, "Cant", border=0, align="R")
        pdf.cell(12, 5, "P.Unit", border=0, align="R")
        pdf.cell(18, 5, "Total", border=0, align="R")
        pdf.ln(5)
        
        # Items reales
        pdf.set_font("Courier", size=8)
        for item in items:
            # Truncar nombre del producto si es muy largo
            producto_nombre = item['producto'][:12] + "." if len(item['producto']) > 12 else item['producto']
            
            pdf.cell(22, 5, producto_nombre, border=0)
            pdf.cell(8, 5, item['cantidad'], border=0, align="R")
            pdf.cell(12, 5, item['precio'].replace("S/ ", ""), border=0, align="R")
            pdf.cell(18, 5, item['subtotal'].replace("S/ ", ""), border=0, align="R")
            pdf.ln(5)

        # Restaurar márgenes
        pdf.set_left_margin(10)
        
        pdf.ln(3)
        pdf.cell(0, 0, "-"*32, ln=True, align="C")
        pdf.ln(5)

        # Total centrado con datos reales
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 6, f"TOTAL: {total}", ln=True, align="C")

        pdf.ln(5)
        pdf.cell(0, 0, "-"*32, ln=True, align="C")
        pdf.ln(8)

        # Footer
        pdf.set_font("Arial", "I", 9)
        pdf.multi_cell(0, 5, "¡Gracias por su compra!\nVuelva pronto", align="C")

        # Manejar output correctamente
        pdf_output = pdf.output(dest="S")
        
        if isinstance(pdf_output, str):
            return pdf_output.encode("latin-1")
        elif isinstance(pdf_output, bytearray):
            return bytes(pdf_output)
        elif isinstance(pdf_output, bytes):
            return pdf_output
        else:
            return bytes(str(pdf_output), "latin-1")

    except Exception as e:
        # PDF de error
        try:
            error_pdf = FPDF("P", "mm", (80, 100))
            error_pdf.add_page()
            error_pdf.set_font("Arial", "B", 10)
            error_pdf.cell(0, 8, "ERROR EN TICKET", ln=True, align="C")
            error_pdf.set_font("Arial", size=8)
            error_pdf.cell(0, 5, f"Error: {str(e)[:30]}", ln=True, align="C")
            
            error_output = error_pdf.output(dest="S")
            if isinstance(error_output, bytearray):
                return bytes(error_output)
            elif isinstance(error_output, str):
                return error_output.encode("latin-1")
            else:
                return bytes(error_output)
        except:
            return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 400]>>endobj xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n189\n%%EOF"
def login_user(username, password):
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if user and check_password_hash(user.password, password) and user.is_active:
            return {"id": user.id, "username": user.username, "role": user.role}
    finally:
        session.close()
    return None

def require_login():
    return st.session_state.get("user")

def require_role(*roles):
    u = require_login()
    if not u:
        return False
    return u.get("role") in roles

def generate_ticket_html(order, items_data, store_data, customer_data=None):
    """Genera el HTML del ticket de venta"""
    fecha = order.ts.strftime("%d/%m/%Y %H:%M")
    
    customer_info = ""
    if customer_data:
        customer_info = f"""
        <div style="margin: 10px 0; padding: 5px; border: 1px solid #ddd;">
            <strong>CLIENTE:</strong><br>
            {customer_data['name']} {customer_data.get('last_name', '')}<br>
            {customer_data.get('document_type', 'DNI')}: {customer_data.get('document_number', 'N/A')}<br>
            {f"Tel: {customer_data['phone']}" if customer_data.get('phone') else ""}
        </div>
        """
    
    items_html = ""
    for item in items_data:
        items_html += f"""
        <tr>
            <td style="text-align: left; padding: 2px;">{item['producto']}</td>
            <td style="text-align: center; padding: 2px;">{item['cantidad']}</td>
            <td style="text-align: right; padding: 2px;">{item['precio_unit']}</td>
            <td style="text-align: right; padding: 2px;">{item['subtotal']}</td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Ticket de Venta #{order.id}</title>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                font-size: 12px;
                margin: 0;
                padding: 20px;
                max-width: 300px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                margin-bottom: 15px;
                border-bottom: 1px dashed #000;
                padding-bottom: 10px;
            }}
            .ticket-info {{
                margin: 10px 0;
                font-size: 11px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 10px 0;
            }}
            th, td {{
                padding: 2px;
                font-size: 10px;
            }}
            .total {{
                border-top: 1px dashed #000;
                margin-top: 10px;
                padding-top: 5px;
                text-align: right;
                font-weight: bold;
                font-size: 14px;
            }}
            .footer {{
                text-align: center;
                margin-top: 15px;
                border-top: 1px dashed #000;
                padding-top: 10px;
                font-size: 10px;
            }}
            @media print {{
                body {{ margin: 0; padding: 10px; }}
                .no-print {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2 style="margin: 0;">🥖 {store_data['name']}</h2>
            <p style="margin: 2px 0;">{store_data.get('address', '')}</p>
            <p style="margin: 2px 0;">Tel: {store_data.get('phone', 'N/A')}</p>
        </div>
        
        <div class="ticket-info">
            <strong>TICKET DE VENTA #{order.id}</strong><br>
            Fecha: {fecha}<br>
            Cajero: {order.user.username}
        </div>
        
        {customer_info}
        
        <table>
            <thead>
                <tr style="border-bottom: 1px solid #000;">
                    <th style="text-align: left;">Producto</th>
                    <th style="text-align: center;">Cant.</th>
                    <th style="text-align: right;">P.Unit</th>
                    <th style="text-align: right;">Total</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>
        
        <div class="total">
            TOTAL: {format_money(order.total)}
        </div>
        
        <div class="footer">
            ¡Gracias por su compra!<br>
            Vuelva pronto 😊
        </div>
        
        <div class="no-print" style="text-align: center; margin-top: 20px;">
            <button onclick="window.print()" style="padding: 10px 20px; font-size: 14px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
                🖨️ Imprimir Ticket
            </button>
            <button onclick="window.close()" style="padding: 10px 20px; font-size: 14px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer; margin-left: 10px;">
                ❌ Cerrar
            </button>
        </div>
        
        <script>
            // Auto-imprimir al cargar (opcional)
            // window.onload = function() {{ window.print(); }}
        </script>
    </body>
    </html>
    """
    return html

# --- SESSION STATE ---
if "user" not in st.session_state:
    st.session_state["user"] = None
if "carrito" not in st.session_state:
    st.session_state["carrito"] = {}

# --- CREAR DATOS DEMO SI NO EXISTEN ---
try:
    session = get_session()
    try:
        if session.query(Store).count() == 0:
            session.add(Store(name="Panadería El Buen Pan", address="Av. Principal 123, Lima", phone="999-888-777"))
        if session.query(User).count() == 0:
            admin_pw = generate_password_hash("admin123")
            session.add(User(username="admin", password=admin_pw, role="admin"))
        if session.query(Ingredient).count() == 0:
            session.add_all([
                Ingredient(name="Harina de Trigo", unit="kg", cost_per_unit=Decimal("3.50")),
                Ingredient(name="Azúcar", unit="kg", cost_per_unit=Decimal("2.80")),
                Ingredient(name="Levadura", unit="kg", cost_per_unit=Decimal("12.00")),
                Ingredient(name="Sal", unit="kg", cost_per_unit=Decimal("1.20")),
            ])
        if session.query(Product).count() == 0:
            session.add_all([
                Product(sku="PAN-001", name="Pan francés", price=Decimal("0.40"), category="Pan diario"),
                Product(sku="PAN-002", name="Pan dulce", price=Decimal("0.80"), category="Dulces"),
                Product(sku="TORTA-001", name="Torta de chocolate", price=Decimal("15.50"), category="Tortas"),
                Product(sku="GALLETA-001", name="Galletas de avena", price=Decimal("2.50"), category="Galletas"),
            ])
        if session.query(Customer).count() == 0:
            session.add_all([
                Customer(name="Cliente", last_name="General", document_type="DNI", document_number="00000000", phone="000-000-000"),
                Customer(name="María", last_name="García", document_type="DNI", document_number="12345678", phone="999-111-222", email="maria@email.com"),
                Customer(name="Carlos", last_name="López", document_type="DNI", document_number="87654321", phone="999-333-444"),
            ])
        session.commit()
    finally:
        session.close()
except Exception as e:
    st.error(f"Error al crear datos demo: {e}")

# --- SIDEBAR LOGIN / REGISTRO ---
st.sidebar.title("🥖 Panadería")
st.sidebar.markdown("---")

if st.session_state["user"] is None:
    # LOGIN
    st.sidebar.subheader("🔐 Iniciar sesión")
    with st.sidebar.form("login_form"):
        u_input = st.text_input("Usuario", placeholder="admin")
        pw_input = st.text_input("Contraseña", type="password", placeholder="admin123")
        login_btn = st.form_submit_button("🚪 Entrar")
        if login_btn:
            if u_input and pw_input:
                user = login_user(u_input, pw_input)
                if user:
                    st.session_state["user"] = user
                    st.success(f"¡Bienvenido {user.get('username')}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña inválidos")
            else:
                st.error("❌ Completa todos los campos")
    st.sidebar.info("💡 Usuario demo:\n- Usuario: `admin`\n- Contraseña: `admin123`")

    # REGISTRO RÁPIDO
    st.sidebar.subheader("📝 Registro rápido")
    with st.sidebar.form("register_form"):
        ru = st.text_input("Nuevo usuario")
        rp = st.text_input("Contraseña", type="password")
        rrole = st.selectbox("Rol", options=["cajero", "panadero"], index=0)
        register_btn = st.form_submit_button("✅ Crear cuenta")
        if register_btn:
            if ru and rp:
                session = get_session()
                try:
                    user = User(username=ru, password=generate_password_hash(rp), role=rrole)
                    session.add(user)
                    session.commit()
                    st.success("✅ Cuenta creada. ¡Inicia sesión!")
                except IntegrityError:
                    st.error("❌ Usuario ya existe")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                finally:
                    session.close()
            else:
                st.error("❌ Completa todos los campos")
else:
    # USUARIO LOGUEADO
    user = st.session_state["user"]
    st.sidebar.success(f"👋 {user.get('username')}")
    st.sidebar.info(f"📋 Rol: **{user.get('role').title()}**")
    if st.sidebar.button("🚪 Cerrar sesión"):
        st.session_state["user"] = None
        st.session_state["carrito"] = {}
        st.rerun()

# --- NAVEGACIÓN ---
st.sidebar.markdown("---")
st.sidebar.subheader("📋 Menú")
menu_options = ["🏠 Dashboard", "🛒 Productos", "👥 Clientes", "💰 Ventas (POS)"]
if require_role("admin"):
    menu_options += ["📊 Reportes", "⚙️ Administración"]
choice = st.sidebar.radio("Navegación", menu_options, label_visibility="collapsed")

# --- DASHBOARD ---
if choice == "🏠 Dashboard":
    st.title("🏠 Dashboard Principal")
    try:
        session = get_session()
        try:
            total_prod = session.query(func.count(Product.id)).scalar() or 0
            total_ing = session.query(func.count(Ingredient.id)).scalar() or 0
            total_customers = session.query(func.count(Customer.id)).scalar() or 0
            total_orders = session.query(func.count(Order.id)).scalar() or 0
            total_sales = session.query(func.coalesce(func.sum(Order.total), 0)).scalar() or 0
        finally:
            session.close()
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("🛒 Productos", total_prod)
        col2.metric("📦 Ingredientes", total_ing)
        col3.metric("👥 Clientes", total_customers)
        col4.metric("🧾 Órdenes", total_orders)
        col5.metric("💰 Ventas Total", format_money(total_sales))
    except Exception as e:
        st.error(f"Error al cargar dashboard: {e}")

elif choice == "🛒 Productos":
    st.title("🛒 Gestión de Productos")
    
    try:
        session = get_session()
        try:
            productos = session.query(Product).order_by(Product.name).all()
        finally:
            session.close()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📋 Lista de Productos")
            
            if productos:
                df = pd.DataFrame([{
                    "ID": p.id,
                    "SKU": p.sku,
                    "Nombre": p.name,
                    "Precio": format_money(p.price),
                    "Categoría": p.category,
                    "Estado": "✅ Activo" if p.is_active else "❌ Inactivo"
                } for p in productos])
                
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No hay productos registrados")
        
        with col2:
            st.subheader("➕ Agregar/Editar")
            
            # Selector para editar
            edit_options = [("Nuevo producto", 0)] + [(f"{p.name} (ID: {p.id})", p.id) for p in productos]
            selected = st.selectbox("Producto a editar", edit_options, format_func=lambda x: x[0])
            
            # Cargar datos si es edición
            if selected[1] > 0:
                producto_edit = next((p for p in productos if p.id == selected[1]), None)
                default_sku = producto_edit.sku if producto_edit else ""
                default_name = producto_edit.name if producto_edit else ""
                default_price = float(producto_edit.price) if producto_edit else 0.40
                default_cat = producto_edit.category if producto_edit else "Pan diario"
                default_active = producto_edit.is_active if producto_edit else True
            else:
                default_sku = default_name = default_cat = ""
                default_price = 0.40
                default_active = True
            
            with st.form("product_form"):
                sku = st.text_input("SKU", value=default_sku, placeholder="PAN-001")
                nombre = st.text_input("Nombre", value=default_name, placeholder="Pan francés")
                precio = st.number_input("Precio (S/)", min_value=0.01, value=default_price, step=0.10)
                categoria = st.text_input("Categoría", value=default_cat, placeholder="Pan diario")
                activo = st.checkbox("Producto activo", value=default_active)
                
                submit = st.form_submit_button("💾 Guardar", use_container_width=True)
                
                if submit:
                    if sku and nombre:
                        try:
                            session = get_session()
                            try:
                                if selected[1] > 0:  # Editar
                                    prod = session.query(Product).get(selected[1])
                                    if prod:
                                        prod.sku = sku
                                        prod.name = nombre
                                        prod.price = Decimal(str(precio))
                                        prod.category = categoria
                                        prod.is_active = activo
                                        st.success("✅ Producto actualizado")
                                else:  # Crear nuevo
                                    nuevo_prod = Product(
                                        sku=sku,
                                        name=nombre,
                                        price=Decimal(str(precio)),
                                        category=categoria,
                                        is_active=activo
                                    )
                                    session.add(nuevo_prod)
                                    st.success("✅ Producto creado")
                                
                                session.commit()
                                st.rerun()
                            finally:
                                session.close()
                        except IntegrityError:
                            st.error("❌ El SKU ya existe")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                    else:
                        st.error("❌ SKU y nombre son obligatorios")
    
    except Exception as e:
        st.error(f"Error en gestión de productos: {e}")

elif choice == "👥 Clientes":
    st.title("👥 Gestión de Clientes")
    
    try:
        session = get_session()
        try:
            clientes = session.query(Customer).filter_by(is_active=True).order_by(Customer.name).all()
        finally:
            session.close()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📋 Lista de Clientes")
            
            if clientes:
                df = pd.DataFrame([{
                    "ID": c.id,
                    "Nombre Completo": f"{c.name} {c.last_name or ''}".strip(),
                    "Documento": f"{c.document_type}: {c.document_number}" if c.document_number else "N/A",
                    "Teléfono": c.phone or "N/A",
                    "Email": c.email or "N/A",
                    "Registrado": c.created_at.strftime("%d/%m/%Y") if c.created_at else "N/A"
                } for c in clientes])
                
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No hay clientes registrados")
        
        with col2:
            st.subheader("➕ Nuevo Cliente")
            
            with st.form("customer_form"):
                nombre = st.text_input("Nombre *", placeholder="María")
                apellido = st.text_input("Apellido", placeholder="García")
                
                col_doc1, col_doc2 = st.columns(2)
                with col_doc1:
                    doc_type = st.selectbox("Tipo Doc.", ["DNI", "RUC", "CE", "Pasaporte"])
                with col_doc2:
                    doc_number = st.text_input("Número", placeholder="12345678")
                
                telefono = st.text_input("Teléfono", placeholder="999-123-456")
                email = st.text_input("Email", placeholder="cliente@email.com")
                direccion = st.text_area("Dirección", placeholder="Av. Principal 123")
                
                submit_customer = st.form_submit_button("💾 Registrar Cliente", use_container_width=True)
                
                if submit_customer:
                    if nombre:
                        try:
                            session = get_session()
                            try:
                                nuevo_cliente = Customer(
                                    name=nombre,
                                    last_name=apellido,
                                    document_type=doc_type,
                                    document_number=doc_number if doc_number else None,
                                    phone=telefono if telefono else None,
                                    email=email if email else None,
                                    address=direccion if direccion else None
                                )
                                session.add(nuevo_cliente)
                                session.commit()
                                st.success("✅ Cliente registrado exitosamente")
                                st.rerun()
                            finally:
                                session.close()
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                    else:
                        st.error("❌ El nombre es obligatorio")
    
    except Exception as e:
        st.error(f"Error en gestión de clientes: {e}")

elif choice == "💰 Ventas (POS)":
    st.title("💰 Punto de Venta (POS)")
    
    if not require_login():
        st.warning("⚠️ Debes iniciar sesión para usar el POS")
        st.stop()
    
    try:
        session = get_session()
        try:
            productos = session.query(Product).filter_by(is_active=True).order_by(Product.name).all()
            clientes = session.query(Customer).filter_by(is_active=True).order_by(Customer.name).all()
            store = session.query(Store).first()
        finally:
            session.close()
        
        # Información del cajero
        user = st.session_state["user"]
        st.info(f"👤 **Cajero:** {user.get('username')} | 🏪 **Tienda:** {store.name if store else 'N/A'}")
        
        # Selección de cliente
        st.subheader("👥 Seleccionar Cliente")
        cliente_options = [("VENTA GENERAL", None)] + [(f"{c.name} {c.last_name or ''} - {c.document_type}: {c.document_number}".strip(), c.id) for c in clientes]
        selected_customer = st.selectbox(
            "Cliente para esta venta:", 
            cliente_options, 
            format_func=lambda x: x[0],
            key="customer_selector"
        )
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader("🛒 Productos Disponibles")
            
            if productos:
                # Mostrar productos en grid
                for i in range(0, len(productos), 2):
                    cols = st.columns(2)
                    for j, col in enumerate(cols):
                        if i + j < len(productos):
                            p = productos[i + j]
                            with col:
                                with st.container():
                                    st.write(f"**{p.name}**")
                                    st.caption(f"SKU: {p.sku} | {format_money(p.price)}")
                                    
                                    # Input de cantidad
                                    qty_key = f"qty_pos_{p.id}"
                                    if qty_key not in st.session_state:
                                        st.session_state[qty_key] = 0.0
                                    
                                    qty = st.number_input(
                                        "Cantidad",
                                        min_value=0.0,
                                        step=1.0,
                                        value=st.session_state[qty_key],
                                        key=f"input_{qty_key}"
                                    )
                                    
                                    if st.button(f"➕ Agregar", key=f"btn_{p.id}", use_container_width=True):
                                        if qty > 0:
                                            carrito = st.session_state.get("carrito", {})
                                            carrito[p.id] = carrito.get(p.id, 0) + qty
                                            st.session_state["carrito"] = carrito
                                            st.session_state[qty_key] = 0.0
                                            st.rerun()
            else:
                st.warning("⚠️ No hay productos activos")
        
        with col2:
            st.subheader("🧾 Carrito de Compras")
            
            carrito = st.session_state.get("carrito", {})
            
            if carrito:
                items_carrito = []
                total_venta = Decimal("0")
                
                for prod_id, qty in carrito.items():
                    producto = next((p for p in productos if p.id == prod_id), None)
                    if producto:
                        subtotal = Decimal(str(qty)) * producto.price
                        total_venta += subtotal
                        
                        items_carrito.append({
                            "Producto": producto.name,
                            "Cant.": int(qty),
                            "Precio": format_money(producto.price),
                            "Subtotal": format_money(subtotal)
                        })
                
                # Mostrar items del carrito
                df_carrito = pd.DataFrame(items_carrito)
                st.dataframe(df_carrito, use_container_width=True, hide_index=True)
                
                # Cliente seleccionado
                if selected_customer[1]:
                    cliente_seleccionado = next((c for c in clientes if c.id == selected_customer[1]), None)
                    if cliente_seleccionado:
                        st.info(f"👤 **Cliente:** {cliente_seleccionado.name} {cliente_seleccionado.last_name or ''}")
                
                # Total
                st.markdown(f"### 💰 **Total: {format_money(total_venta)}**")
                
                # Botones de acción
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("🗑️ Limpiar", use_container_width=True):
                        st.session_state["carrito"] = {}
                        st.rerun()
                
                with col_btn2:
                    if st.button("💳 **COBRAR**", use_container_width=True, type="primary"):
                        try:
                            session = get_session()
                            try:
                                # Crear orden con el esquema correcto
                                orden = Order(
                                    user_id=user.get("id"), 
                                    store_id=store.id if store else 1,
                                    customer_id=selected_customer[1],  # Incluir ID del cliente
                                    total=total_venta
                                )
                                session.add(orden)
                                session.flush()
                                
                                # Agregar items
                                for prod_id, qty in carrito.items():
                                    producto = session.query(Product).get(prod_id)
                                    
                                    # Item de la orden
                                    session.add(OrderItem(
                                        order_id=orden.id,
                                        product_id=prod_id,
                                        qty=Decimal(str(qty)),
                                        price=producto.price
                                    ))
                                
                                session.commit()
                                
                                # Preparar datos para el ticket
                                orden_completa = session.query(Order).filter_by(id=orden.id).first()
                                items_ticket = []
                                for prod_id, qty in carrito.items():
                                    producto = next((p for p in productos if p.id == prod_id), None)
                                    if producto:
                                        subtotal = Decimal(str(qty)) * producto.price
                                        items_ticket.append({
                                            "producto": producto.name,
                                            "cantidad": int(qty),
                                            "precio_unit": format_money(producto.price),
                                            "subtotal": format_money(subtotal)
                                        })
                                
                                # Datos del cliente
                                customer_data = None
                                customer_info = ""
                                if selected_customer[1]:
                                    cliente = next((c for c in clientes if c.id == selected_customer[1]), None)
                                    if cliente:
                                        customer_data = {
                                            "name": cliente.name,
                                            "last_name": cliente.last_name,
                                            "document_type": cliente.document_type,
                                            "document_number": cliente.document_number,
                                            "phone": cliente.phone
                                        }
                                        customer_info = f"""
                                        <div style="margin: 10px 0; padding: 5px; border: 1px solid #ddd;">
                                            <strong>CLIENTE:</strong><br>
                                            {customer_data['name']} {customer_data.get('last_name', '')}<br>
                                            {customer_data.get('document_type', 'DNI')}: {customer_data.get('document_number', 'N/A')}<br>
                                            {f"Tel: {customer_data['phone']}" if customer_data.get('phone') else ""}
                                        </div>
                                        """
                                
                                # Datos de la tienda
                                store_data = {
                                    "name": store.name if store else "Panadería",
                                    "address": store.address if store else "",
                                    "phone": store.phone if store else ""
                                }
                                
                                # Generar HTML del ticket
                                ticket_html = generate_ticket_html(orden_completa, items_ticket, store_data, customer_data)
                                
                                # Limpiar carrito
                                st.session_state["carrito"] = {}
                                
                                st.success(f"✅ **Venta registrada exitosamente!**\n\n🧾 **Orden #{orden.id}**\n💰 **Total: {format_money(total_venta)}**")
                                st.balloons()
                                
                                # Botón para mostrar ticket
                                # Generar HTML del ticket
                                try:
                                    ticket_html = generate_ticket_html(orden_completa, items_ticket, store_data, customer_data)
                                    
                                    # Generar PDF del ticket
                                    pdf_bytes = generar_pdf(ticket_html, f"Ticket_Orden_{orden.id}.pdf")
                                    
                                    # Botón de descarga directo
                                    st.download_button(
                                        "🖨️ Descargar Ticket PDF",
                                        data=pdf_bytes,
                                        file_name=f"Ticket_Orden_{orden.id}.pdf",
                                        mime="application/pdf",
                                        key=f"download_ticket_{orden.id}"
                                    )
                                    
                                except Exception as pdf_error:
                                    st.warning(f"⚠️ Venta procesada correctamente, pero hubo un problema al generar el PDF: {pdf_error}")
                                    st.info("💡 La venta se registró exitosamente en el sistema.")

                                
                               
                            finally:
                                session.close()
                        
                        except Exception as e:
                            st.error(f"❌ Error al procesar venta: {e}")
            
            else:
                st.info("🛒 Carrito vacío\n\nAgrega productos usando los botones de la izquierda")
                
                # Mostrar cliente seleccionado incluso con carrito vacío
                if selected_customer[1]:
                    cliente_seleccionado = next((c for c in clientes if c.id == selected_customer[1]), None)
                    if cliente_seleccionado:
                        st.info(f"👤 **Cliente seleccionado:** {cliente_seleccionado.name} {cliente_seleccionado.last_name or ''}")
    
    except Exception as e:
        st.error(f"Error en POS: {e}")

# --- REPORTES ---
elif choice == "📊 Reportes" and require_role("admin"):
    st.title("📊 Reportes y Análisis")
    try:
        session = get_session()
        try:
            # Reportes de ventas por día
            stmt_ventas = text("""
            SELECT 
                DATE(ts) as fecha,
                COUNT(*) as num_ordenes,
                SUM(total) as total_ventas
            FROM orders 
            GROUP BY DATE(ts) 
            ORDER BY fecha DESC
            LIMIT 30
            """)
            ventas_result = session.execute(stmt_ventas).all()
            
            if ventas_result:
                st.subheader("📈 Ventas por Día (Últimos 30 días)")
                df_ventas = pd.DataFrame(ventas_result, columns=["Fecha", "Órdenes", "Total Ventas"])
                df_ventas["Fecha"] = pd.to_datetime(df_ventas["Fecha"])
                df_ventas["Total Ventas"] = df_ventas["Total Ventas"].astype(float)
                st.line_chart(df_ventas.set_index("Fecha")["Total Ventas"])
                df_display = df_ventas.copy()
                df_display["Total Ventas"] = df_display["Total Ventas"].apply(lambda x: format_money(x))
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Top productos más vendidos
            stmt_top_productos = text("""
            SELECT 
                p.name as producto,
                SUM(oi.qty) as total_vendido,
                SUM(oi.qty * oi.price) as ingresos_totales
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            GROUP BY p.name
            ORDER BY total_vendido DESC
            LIMIT 10
            """)
            top_result = session.execute(stmt_top_productos).all()
            
            if top_result:
                st.subheader("🏆 Top 10 Productos Más Vendidos")
                df_top = pd.DataFrame(top_result, columns=["Producto", "Cantidad Vendida", "Ingresos Totales"])
                df_top["Ingresos Totales"] = df_top["Ingresos Totales"].apply(lambda x: format_money(float(x)))
                chart_data = pd.DataFrame(top_result, columns=["Producto", "Cantidad", "Ingresos"])
                st.bar_chart(chart_data.set_index("Producto")["Cantidad"])
                st.dataframe(df_top, use_container_width=True, hide_index=True)
            
            # Reporte de clientes frecuentes
            stmt_clientes = text("""
            SELECT 
                CONCAT(c.name, ' ', COALESCE(c.last_name, '')) as cliente,
                COUNT(o.id) as total_compras,
                SUM(o.total) as total_gastado
            FROM customers c
            LEFT JOIN orders o ON c.id = o.customer_id
            WHERE c.is_active = true
            GROUP BY c.id, c.name, c.last_name
            HAVING COUNT(o.id) > 0
            ORDER BY total_compras DESC
            LIMIT 10
            """)
            clientes_result = session.execute(stmt_clientes).all()
            
            if clientes_result:
                st.subheader("🌟 Top 10 Clientes Frecuentes")
                df_clientes = pd.DataFrame(clientes_result, columns=["Cliente", "Total Compras", "Total Gastado"])
                df_clientes["Total Gastado"] = df_clientes["Total Gastado"].apply(lambda x: format_money(float(x)))
                st.dataframe(df_clientes, use_container_width=True, hide_index=True)
            
            st.subheader("📋 Resumen General")
            total_productos = session.query(func.count(Product.id)).scalar() or 0
            total_usuarios = session.query(func.count(User.id)).scalar() or 0
            total_clientes = session.query(func.count(Customer.id)).scalar() or 0
            total_ordenes = session.query(func.count(Order.id)).scalar() or 0
            ingresos_totales = session.query(func.sum(Order.total)).scalar() or 0
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.metric("🛒 Total Productos", total_productos)
            with col2: st.metric("👥 Total Usuarios", total_usuarios)
            with col3: st.metric("🙋 Total Clientes", total_clientes)
            with col4: st.metric("🧾 Total Órdenes", total_ordenes)
            with col5: st.metric("💰 Ingresos Totales", format_money(ingresos_totales))
            
        finally:
            session.close()
    except Exception as e:
        st.error(f"Error al generar reportes: {e}")

# --- ADMIN ---
elif choice == "⚙️ Administración" and require_role("admin"):
    st.title("⚙️ Panel de Administración")
    
    tabs = st.tabs(["👥 Usuarios", "🏪 Tiendas", "🚚 Proveedores", "🧾 Ingredientes", "👤 Gestión Clientes"])
    
    # TAB: Usuarios
    with tabs[0]:
        st.subheader("👥 Gestión de Usuarios")
        
        try:
            session = get_session()
            try:
                usuarios = session.query(User).order_by(User.username).all()
            finally:
                session.close()
            
            if usuarios:
                # Mostrar usuarios existentes
                df_users = pd.DataFrame([{
                    "ID": u.id,
                    "Usuario": u.username,
                    "Rol": u.role,
                    "Estado": "✅ Activo" if u.is_active else "❌ Inactivo"
                } for u in usuarios])
                
                st.dataframe(df_users, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Crear usuario
            st.subheader("➕ Nuevo Usuario")
            
            with st.form("admin_user_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    new_username = st.text_input("Usuario", placeholder="cajero1")
                    new_password = st.text_input("Contraseña", type="password", placeholder="contraseña123")
                
                with col2:
                    new_role = st.selectbox("Rol", ["admin", "cajero", "panadero"])
                    new_active = st.checkbox("Usuario activo", value=True)
                
                submit_user = st.form_submit_button("💾 Crear Usuario", use_container_width=True)
                
                if submit_user:
                    if new_username and new_password:
                        try:
                            session = get_session()
                            try:
                                nuevo_usuario = User(
                                    username=new_username,
                                    password=generate_password_hash(new_password),
                                    role=new_role,
                                    is_active=new_active
                                )
                                session.add(nuevo_usuario)
                                session.commit()
                                st.success("✅ Usuario creado exitosamente")
                                st.rerun()
                            finally:
                                session.close()
                        
                        except IntegrityError:
                            st.error("❌ El usuario ya existe")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                    else:
                        st.error("❌ Completa los campos obligatorios")
        
        except Exception as e:
            st.error(f"Error en gestión de usuarios: {e}")
    
    # TAB: Tiendas
    with tabs[1]:
        st.subheader("🏪 Gestión de Tiendas")
        
        try:
            session = get_session()
            try:
                tiendas = session.query(Store).all()
            finally:
                session.close()
            
            if tiendas:
                df_stores = pd.DataFrame([{
                    "ID": s.id,
                    "Nombre": s.name,
                    "Dirección": s.address,
                    "Teléfono": s.phone or "N/A"
                } for s in tiendas])
                
                st.dataframe(df_stores, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("➕ Nueva Tienda")
            
            with st.form("store_form"):
                store_name = st.text_input("Nombre de la tienda", placeholder="Sucursal Centro")
                store_address = st.text_area("Dirección", placeholder="Av. Principal 123, Lima")
                store_phone = st.text_input("Teléfono", placeholder="999-888-777")
                
                submit_store = st.form_submit_button("💾 Crear Tienda", use_container_width=True)
                
                if submit_store:
                    if store_name:
                        try:
                            session = get_session()
                            try:
                                nueva_tienda = Store(
                                    name=store_name,
                                    address=store_address,
                                    phone=store_phone
                                )
                                session.add(nueva_tienda)
                                session.commit()
                                st.success("✅ Tienda creada exitosamente")
                                st.rerun()
                            finally:
                                session.close()
                        
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                    else:
                        st.error("❌ El nombre es obligatorio")
        
        except Exception as e:
            st.error(f"Error en gestión de tiendas: {e}")
    
    # TAB: Proveedores
    with tabs[2]:
        st.subheader("🚚 Gestión de Proveedores")
        
        try:
            session = get_session()
            try:
                proveedores = session.query(Supplier).all()
            finally:
                session.close()
            
            if proveedores:
                df_suppliers = pd.DataFrame([{
                    "ID": s.id,
                    "Nombre": s.name,
                    "Contacto": s.contact or "N/A",
                    "Teléfono": s.phone or "N/A",
                    "Email": s.email or "N/A"
                } for s in proveedores])
                
                st.dataframe(df_suppliers, use_container_width=True, hide_index=True)
            else:
                st.info("No hay proveedores registrados")
            
            st.markdown("---")
            st.subheader("➕ Nuevo Proveedor")
            
            with st.form("supplier_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    supplier_name = st.text_input("Nombre del proveedor", placeholder="Molinos del Perú")
                    supplier_contact = st.text_input("Persona de contacto", placeholder="Carlos García")
                
                with col2:
                    supplier_phone = st.text_input("Teléfono", placeholder="999-888-777")
                    supplier_email = st.text_input("Email", placeholder="ventas@proveedor.com")
                
                submit_supplier = st.form_submit_button("💾 Crear Proveedor", use_container_width=True)
                
                if submit_supplier:
                    if supplier_name:
                        try:
                            session = get_session()
                            try:
                                nuevo_proveedor = Supplier(
                                    name=supplier_name,
                                    contact=supplier_contact,
                                    phone=supplier_phone,
                                    email=supplier_email
                                )
                                session.add(nuevo_proveedor)
                                session.commit()
                                st.success("✅ Proveedor creado exitosamente")
                                st.rerun()
                            finally:
                                session.close()
                        
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                    else:
                        st.error("❌ El nombre es obligatorio")
        
        except Exception as e:
            st.error(f"Error en gestión de proveedores: {e}")
    
    # TAB: Ingredientes
    with tabs[3]:
        st.subheader("🧾 Gestión de Ingredientes")
        
        try:
            session = get_session()
            try:
                ingredientes = session.query(Ingredient).order_by(Ingredient.name).all()
            finally:
                session.close()
            
            if ingredientes:
                df_ingredients = pd.DataFrame([{
                    "ID": i.id,
                    "Nombre": i.name,
                    "Unidad": i.unit,
                    "Costo por Unidad": format_money(i.cost_per_unit) if i.cost_per_unit else "N/A"
                } for i in ingredientes])
                
                st.dataframe(df_ingredients, use_container_width=True, hide_index=True)
            else:
                st.info("No hay ingredientes registrados")
            
            st.markdown("---")
            st.subheader("➕ Nuevo Ingrediente")
            
            with st.form("ingredient_form"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    ingredient_name = st.text_input("Nombre", placeholder="Harina Integral")
                
                with col2:
                    ingredient_unit = st.selectbox("Unidad", ["kg", "lt", "unidad", "gramos", "ml"])
                
                with col3:
                    ingredient_cost = st.number_input("Costo por unidad (S/)", min_value=0.01, value=1.00, step=0.10)
                
                submit_ingredient = st.form_submit_button("💾 Crear Ingrediente", use_container_width=True)
                
                if submit_ingredient:
                    if ingredient_name:
                        try:
                            session = get_session()
                            try:
                                nuevo_ingrediente = Ingredient(
                                    name=ingredient_name,
                                    unit=ingredient_unit,
                                    cost_per_unit=Decimal(str(ingredient_cost))
                                )
                                session.add(nuevo_ingrediente)
                                session.commit()
                                st.success("✅ Ingrediente creado exitosamente")
                                st.rerun()
                            finally:
                                session.close()
                        
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                    else:
                        st.error("❌ El nombre es obligatorio")
        
        except Exception as e:
            st.error(f"Error en gestión de ingredientes: {e}")
    
    # TAB: Gestión de Clientes (Admin)
    with tabs[4]:
        st.subheader("👤 Gestión Avanzada de Clientes")
        
        try:
            session = get_session()
            try:
                clientes_completo = session.query(Customer).order_by(Customer.created_at.desc()).all()
            finally:
                session.close()
            
            if clientes_completo:
                # Mostrar todos los clientes incluyendo inactivos
                df_customers_admin = pd.DataFrame([{
                    "ID": c.id,
                    "Nombre": c.name,
                    "Apellido": c.last_name or "",
                    "Documento": f"{c.document_type}: {c.document_number}" if c.document_number else "N/A",
                    "Teléfono": c.phone or "N/A",
                    "Email": c.email or "N/A",
                    "Estado": "✅ Activo" if c.is_active else "❌ Inactivo",
                    "Registrado": c.created_at.strftime("%d/%m/%Y %H:%M") if c.created_at else "N/A"
                } for c in clientes_completo])
                
                st.dataframe(df_customers_admin, use_container_width=True, hide_index=True)
                
                # Estadísticas de clientes
                clientes_activos = len([c for c in clientes_completo if c.is_active])
                clientes_inactivos = len([c for c in clientes_completo if not c.is_active])
                
                col1, col2, col3 = st.columns(3)
                with col1: st.metric("👥 Clientes Activos", clientes_activos)
                with col2: st.metric("❌ Clientes Inactivos", clientes_inactivos)
                with col3: st.metric("📊 Total Clientes", len(clientes_completo))
            else:
                st.info("No hay clientes registrados")
        
        except Exception as e:
            st.error(f"Error en gestión avanzada de clientes: {e}")

else:
    if not require_login():
        st.warning("⚠️ Debes iniciar sesión para acceder a esta sección")
    elif not require_role("admin"):
        st.error("❌ No tienes permisos para acceder a esta sección")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    🥖 <strong>Sistema de Panadería v2.0</strong><br>
    Desarrollado con ❤️ usando Streamlit | 
    <em>Credenciales demo: admin / admin123</em><br>
    <small>✨ Nuevas funciones: Gestión de clientes y tickets de venta</small>
</div>
""", unsafe_allow_html=True)