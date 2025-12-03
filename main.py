"""
================================================================================
PSA Monitor - Sistema de Monitoreo de Plantas de Oxígeno PSA
Versión 2.0

Autor: ONYX INGENIERÍA
================================================================================

Para ejecutar:
    python main.py

Variables de entorno requeridas:
    DATABASE_URL     - URL de conexión PostgreSQL
    SECRET_KEY       - Clave secreta para Flask
    JWT_SECRET_KEY   - Clave para tokens JWT
    API_KEY          - Clave para API de dispositivos IoT
    TELEGRAM_TOKEN   - (Opcional) Token del bot de Telegram
    ADMIN_PRINCIPAL_ID - (Opcional) ID de Telegram del admin
"""

import os
import sys
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_admin_user():
    """Crea usuario admin por defecto si no existe"""
    from app.database import get_db, crear_usuario
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
            if not cursor.fetchone():
                # Crear admin con contraseña por defecto
                admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
                user_id = crear_usuario(
                    username='admin',
                    password=admin_password,
                    rol='admin',
                    nombre_completo='Administrador'
                )
                if user_id:
                    logger.info(f"Usuario admin creado (password: {admin_password})")
                    logger.warning("¡CAMBIA LA CONTRASEÑA DEL ADMIN!")
    except Exception as e:
        logger.error(f"Error creando admin: {e}")


def main():
    """Punto de entrada principal"""
    
    # Verificar variables de entorno críticas
    if not os.environ.get('DATABASE_URL'):
        logger.error("DATABASE_URL no configurada")
        sys.exit(1)
    
    # Importar después de verificar
    from app import create_app
    from app.database import inicializar_db
    
    # Crear aplicación
    app = create_app()
    
    # Inicializar base de datos
    logger.info("Inicializando base de datos...")
    try:
        inicializar_db()
        logger.info("Base de datos lista")
    except Exception as e:
        logger.error(f"Error inicializando DB: {e}")
        sys.exit(1)
    
    # Crear usuario admin si no existe
    create_admin_user()
    
    # Configurar puerto
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Iniciando servidor en puerto {port}...")
    logger.info(f"Dashboard: http://localhost:{port}/")
    logger.info(f"API: http://localhost:{port}/api/")
    logger.info(f"SCADA: http://localhost:{port}/scada")
    
    # Iniciar bot de Telegram si está configurado
    telegram_token = os.environ.get('TELEGRAM_TOKEN')
    if telegram_token:
        import threading
        import asyncio
        from app.telegram_bot import crear_bot_application
        
        def run_bot():
            """Ejecuta el bot en un thread separado"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            bot_app = crear_bot_application()
            if bot_app:
                try:
                    loop.run_until_complete(bot_app.initialize())
                    loop.run_until_complete(bot_app.start())
                    loop.run_until_complete(bot_app.updater.start_polling(drop_pending_updates=True))
                    logger.info("Bot de Telegram iniciado")
                    loop.run_forever()
                except Exception as e:
                    logger.error(f"Error en bot de Telegram: {e}")
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info("Thread del bot de Telegram iniciado")
    else:
        logger.info("Bot de Telegram no configurado (sin TELEGRAM_TOKEN)")
    
    # Ejecutar servidor Flask
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )


if __name__ == '__main__':
    main()
