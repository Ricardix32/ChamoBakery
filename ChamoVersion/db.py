import os
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Boolean,
    ForeignKey, Numeric, Text, func
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# === DATOS DE CONEXIÓN AIVEN POSTGRESQL ===
DB_HOST = "pg-39dfce5c-togata.d.aivencloud.com"
DB_NAME = "defaultdb"
DB_USER = "avnadmin"
DB_PASS = "AVNS_8t_NfZ6Pe0Q9s8RqL6x"
DB_PORT = 11620

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# === CONEXIÓN A LA DB ===
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# === MODELOS ===

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    role = Column(String(50), default="cajero")
    is_active = Column(Boolean, default=True)
    orders = relationship("Order", back_populates="user")


class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    address = Column(String(200))
    phone = Column(String(50))
    is_active = Column(Boolean, default=True)
    orders = relationship("Order", back_populates="store")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    last_name = Column(String(120))
    email = Column(String(120))
    phone = Column(String(50))
    document_type = Column(String(20), default="DNI")  # DNI, RUC, CE, etc.
    document_number = Column(String(20))
    address = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="customer")


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    contact = Column(String(120))
    phone = Column(String(50))
    email = Column(String(120))
    is_active = Column(Boolean, default=True)


class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    unit = Column(String(20), nullable=False)
    cost_per_unit = Column(Numeric(12,4), nullable=False, default=0)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    sku = Column(String(50), nullable=False, unique=True)
    name = Column(String(120), nullable=False)
    description = Column(Text)
    price = Column(Numeric(12,2), nullable=False, default=0)
    category = Column(String(80))
    is_active = Column(Boolean, default=True)
    order_items = relationship("OrderItem", back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    total = Column(Numeric(12,2), default=0)
    ts = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    store = relationship("Store", back_populates="orders")
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty = Column(Numeric(12,2), nullable=False, default=1)
    price = Column(Numeric(12,2), nullable=False, default=0)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


# === FUNCIONES ===

def init_db(drop=False):
    """Inicializa la base de datos"""
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

def get_session():
    """Obtiene una sesión de base de datos"""
    return SessionLocal()

def test_connection():
    """Prueba la conexión a la base de datos"""
    try:
        with engine.connect() as conn:
            conn.execute(func.now())
            return True
    except Exception:
        return False

def force_recreate_tables():
    """Elimina y recrea todas las tablas"""
    try:
        print("Eliminando tablas existentes...")
        Base.metadata.drop_all(engine)
        print("Creando tablas con esquema correcto...")
        Base.metadata.create_all(engine)
        print("Tablas recreadas exitosamente")
        return True
    except Exception as e:
        print(f"Error al recrear tablas: {e}")
        return False

# Verificar conexión al importar
try:
    test_connection()
except Exception:
    pass