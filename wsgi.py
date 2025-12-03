"""
WSGI Entry Point para Gunicorn/Producción
"""

import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app import create_app
from app.database import inicializar_db, get_db, crear_usuario

# Crear aplicación
app = create_app()

# Inicializar base de datos al arrancar
with app.app_context():
    try:
        inicializar_db()
        logger.info("Base de datos inicializada")
        
        # Crear admin si no existe
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
            if not cursor.fetchone():
                admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
                crear_usuario('admin', admin_password, 'admin', nombre_completo='Administrador')
                logger.info("Usuario admin creado")
    except Exception as e:
        logger.error(f"Error en inicialización: {e}")
