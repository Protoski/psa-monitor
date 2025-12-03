"""
================================================================================
Aplicación Flask - Monitor de Plantas PSA
Versión 2.0 - Refactorizada con autenticación y gestión de equipos
================================================================================
"""

from flask import Flask
from flask_jwt_extended import JWTManager
from datetime import timedelta
import os

jwt = JWTManager()

def create_app():
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Detectar si estamos en producción (Render u otro hosting)
    is_production = os.environ.get('RENDER') or os.environ.get('DATABASE_URL', '').startswith('postgresql')
    
    # Configuración
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)
    app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
    
    # Configuración de cookies para HTTPS en producción
    app.config['JWT_COOKIE_SECURE'] = is_production
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False
    app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
    app.config['JWT_COOKIE_DOMAIN'] = None
    
    # Inicializar extensiones
    jwt.init_app(app)
    
    # Registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.api import api_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    return app
