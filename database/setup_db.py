import os
import pymysql
from dotenv import load_dotenv
import sys

# Asegurar que podemos importar desde la raíz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import engine
from models.usuario import Base

def init_db():
    load_dotenv()
    DB_USER = os.getenv("MARIADB_USER")
    DB_PASS = os.getenv("MARIADB_PASSWORD")
    DB_HOST = os.getenv("MARIADB_HOST")
    DB_PORT = int(os.getenv("MARIADB_PORT", 3306))
    DB_NAME = os.getenv("MARIADB_DB")

    print(f"[*] Conectando a MariaDB en {DB_HOST}:{DB_PORT}...")
    
    # Paso 1: Crear la BD usando pymysql directamente (fuera del ORM)
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME};")
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[OK] Base de datos '{DB_NAME}' garantizada.")
    except Exception as e:
        print(f"[ERROR] No se pudo crear la base de datos: {e}")
        return

    # Paso 2: Crear las tablas con SQLAlchemy
    print("[*] Creando tablas con SQLAlchemy...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[OK] Tablas creadas correctamente.")
    except Exception as e:
        print(f"[ERROR] No se pudieron crear las tablas: {e}")

if __name__ == "__main__":
    init_db()