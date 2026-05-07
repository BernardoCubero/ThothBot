import sys
import os

# Asegurar que podemos importar desde la raíz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import SessionLocal
from models.usuario import Usuario

def guardar_o_actualizar_usuario(conversation_id, nombre=None, ciudad_origen=None, pais=None):
    """
    Crea o actualiza la información de un usuario en la base de datos MariaDB.
    """
    session = SessionLocal()
    try:
        usuario = session.query(Usuario).filter(Usuario.conversation_id == conversation_id).first()
        
        if not usuario:
            # Crear nuevo usuario
            usuario = Usuario(
                conversation_id=conversation_id,
                nombre=nombre,
                ciudad_origen=ciudad_origen,
                pais=pais
            )
            session.add(usuario)
        else:
            # Actualizar campos solo si se proporcionan
            if nombre:
                usuario.nombre = nombre
            if ciudad_origen:
                usuario.ciudad_origen = ciudad_origen
            if pais:
                usuario.pais = pais
                
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[ERROR MariaDB] No se pudo guardar el usuario: {e}")
    finally:
        session.close()

def obtener_usuario(conversation_id):
    """
    Devuelve los datos de un usuario si existe, None en caso contrario.
    """
    session = SessionLocal()
    try:
        return session.query(Usuario).filter(Usuario.conversation_id == conversation_id).first()
    finally:
        session.close()
