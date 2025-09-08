import os
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
import streamlit as st
import pandas as pd
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

# Importar desde tu db.py
try:
    from db import (
        engine, get_session, init_db,
        Store, Supplier, Ingredient, Product, Order, OrderItem, User
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

# Inicializar bandera de reinicio
if "should_rerun" not in st.session_state:
    st.session_state["should_rerun"] = False

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
            session.add(Store(name="Tienda Central", address="Av. Principal 123", phone="999-888-777"))
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
                    st.session_state["should_rerun"] = True

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
        st.session_state["should_rerun"] = True


# --- NAVEGACIÓN ---
st.sidebar.markdown("---")
st.sidebar.subheader("📋 Menú")
menu_options = ["🏠 Dashboard", "🛒 Productos", "💰 Ventas (POS)"]
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
            total_orders = session.query(func.count(Order.id)).scalar() or 0
            total_sales = session.query(func.coalesce(func.sum(Order.total), 0)).scalar() or 0
        finally:
            session.close()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🛒 Productos", total_prod)
        col2.metric("📦 Ingredientes", total_ing)
        col3.metric("🧾 Órdenes", total_orders)
        col4.metric("💰 Ventas Total", format_money(total_sales))
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

elif choice == "💰 Ventas (POS)":
    st.title("💰 Punto de Venta (POS)")
    
    if not require_login():
        st.warning("⚠️ Debes iniciar sesión para usar el POS")
        st.stop()
    
    try:
        session = get_session()
        try:
            productos = session.query(Product).filter_by(is_active=True).order_by(Product.name).all()
            store = session.query(Store).first()
        finally:
            session.close()
        
        # Información del cajero
        user = st.session_state["user"]
        st.info(f"👤 **Cajero:** {user.get('username')} | 🏪 **Tienda:** {store.name if store else 'N/A'}")
        
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
                                    customer_id=None,
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
                                
                                # Limpiar carrito
                                st.session_state["carrito"] = {}
                                
                                st.success(f"✅ **Venta registrada exitosamente!**\n\n🧾 **Orden #{orden.id}**\n💰 **Total: {format_money(total_venta)}**")
                                st.balloons()
                                st.rerun()
                            finally:
                                session.close()
                        
                        except Exception as e:
                            st.error(f"❌ Error al procesar venta: {e}")
            
            else:
                st.info("🛒 Carrito vacío\n\nAgrega productos usando los botones de la izquierda")
    
    except Exception as e:
        st.error(f"Error en POS: {e}")

# --- REPORTES ---
elif choice == "📊 Reportes" and require_role("admin"):
    st.title("📊 Reportes y Análisis")
    try:
        session = get_session()
        try:
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
            
            st.subheader("📋 Resumen General")
            total_productos = session.query(func.count(Product.id)).scalar() or 0
            total_usuarios = session.query(func.count(User.id)).scalar() or 0
            total_ordenes = session.query(func.count(Order.id)).scalar() or 0
            ingresos_totales = session.query(func.sum(Order.total)).scalar() or 0
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("🛍️ Total Productos", total_productos)
            with col2: st.metric("👥 Total Usuarios", total_usuarios)
            with col3: st.metric("🧾 Total Órdenes", total_ordenes)
            with col4: st.metric("💰 Ingresos Totales", format_money(ingresos_totales))
        finally:
            session.close()
    except Exception as e:
        st.error(f"Error al generar reportes: {e}")

# --- ADMIN ---
elif choice == "⚙️ Administración" and require_role("admin"):
    st.title("⚙️ Panel de Administración")
    
    tabs = st.tabs(["👥 Usuarios", "🏪 Tiendas", "🚚 Proveedores", "🧾 Ingredientes"])
    
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

else:
    if not require_login():
        st.warning("⚠️ Debes iniciar sesión para acceder a esta sección")
    elif not require_role("admin"):
        st.error("❌ No tienes permisos para acceder a esta sección")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    🥖 <strong>Sistema de Panadería v1.0</strong><br>
    Desarrollado con ❤️ usando Streamlit | 
    <em>Credenciales demo: admin / admin123</em>
</div>
""", unsafe_allow_html=True)



