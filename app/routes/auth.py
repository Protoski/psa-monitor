"""
================================================================================
Rutas de Autenticación
================================================================================
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, 
    get_jwt_identity, set_access_cookies, unset_jwt_cookies,
    verify_jwt_in_request
)
from functools import wraps

from app.database import (
    verificar_usuario, crear_usuario, obtener_usuario_por_id,
    listar_usuarios, actualizar_usuario, cambiar_password
)

auth_bp = Blueprint('auth', __name__)


# ================================================================================
# DECORADORES DE AUTORIZACIÓN
# ================================================================================

def login_required(func):
    """Decorador que requiere autenticación"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            return func(*args, **kwargs)
        except Exception:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"error": "No autorizado"}), 401
            return redirect(url_for('auth.login_page'))
    return wrapper


def admin_required(func):
    """Decorador que requiere rol admin"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = obtener_usuario_por_id(user_id)
            if not user or user.get('rol') != 'admin':
                if request.is_json:
                    return jsonify({"error": "Solo administradores"}), 403
                return render_template('error.html', 
                                       mensaje="Acceso denegado", 
                                       detalle="Solo administradores pueden acceder a esta sección"), 403
            return func(*args, **kwargs)
        except Exception:
            if request.is_json:
                return jsonify({"error": "No autorizado"}), 401
            return redirect(url_for('auth.login_page'))
    return wrapper


def operador_required(func):
    """Decorador que requiere rol operador o admin"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = obtener_usuario_por_id(user_id)
            if not user or user.get('rol') not in ['admin', 'operador']:
                if request.is_json:
                    return jsonify({"error": "Permisos insuficientes"}), 403
                return render_template('error.html', 
                                       mensaje="Acceso denegado"), 403
            return func(*args, **kwargs)
        except Exception:
            if request.is_json:
                return jsonify({"error": "No autorizado"}), 401
            return redirect(url_for('auth.login_page'))
    return wrapper


def get_current_user():
    """Obtiene el usuario actual si está autenticado"""
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            return obtener_usuario_por_id(user_id)
    except Exception:
        pass
    return None


# ================================================================================
# RUTAS WEB
# ================================================================================

@auth_bp.route('/login', methods=['GET'])
def login_page():
    """Página de login"""
    # Si ya está logueado, redirigir al dashboard
    user = get_current_user()
    if user:
        return redirect(url_for('dashboard.index'))
    return render_template('auth/login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    """Procesa el login"""
    # Soportar tanto JSON como form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        if request.is_json:
            return jsonify({"error": "Usuario y contraseña requeridos"}), 400
        return render_template('auth/login.html', error="Usuario y contraseña requeridos")
    
    user = verificar_usuario(username, password)
    
    if not user:
        if request.is_json:
            return jsonify({"error": "Credenciales inválidas"}), 401
        return render_template('auth/login.html', error="Usuario o contraseña incorrectos")
    
    # Crear tokens
    access_token = create_access_token(
        identity=user['id'],
        additional_claims={
            'username': user['username'],
            'rol': user['rol']
        }
    )
    
    if request.is_json:
        return jsonify({
            "access_token": access_token,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "rol": user['rol'],
                "nombre_completo": user['nombre_completo']
            }
        }), 200
    
    # Para requests web, setear cookie y redirigir
    response = make_response(redirect(url_for('dashboard.index')))
    set_access_cookies(response, access_token)
    return response


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Cierra sesión"""
    if request.is_json:
        response = jsonify({"message": "Sesión cerrada"})
    else:
        response = make_response(redirect(url_for('auth.login_page')))
    
    unset_jwt_cookies(response)
    return response


@auth_bp.route('/registro', methods=['GET'])
def registro_page():
    """Página de registro (solo si está habilitado)"""
    return render_template('auth/registro.html')


@auth_bp.route('/registro', methods=['POST'])
@admin_required
def registro():
    """Registra nuevo usuario (solo admin)"""
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    rol = data.get('rol', 'lector')
    email = data.get('email', '').strip() or None
    nombre_completo = data.get('nombre_completo', '').strip() or None
    telegram_id = data.get('telegram_id')
    
    if telegram_id:
        try:
            telegram_id = int(telegram_id)
        except:
            telegram_id = None
    
    if not username or not password:
        if request.is_json:
            return jsonify({"error": "Usuario y contraseña requeridos"}), 400
        return render_template('auth/registro.html', error="Usuario y contraseña requeridos")
    
    if len(password) < 6:
        if request.is_json:
            return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400
        return render_template('auth/registro.html', error="Contraseña muy corta")
    
    if rol not in ['admin', 'operador', 'lector']:
        rol = 'lector'
    
    user_id = crear_usuario(username, password, rol, email, nombre_completo, telegram_id)
    
    if not user_id:
        if request.is_json:
            return jsonify({"error": "El usuario ya existe"}), 409
        return render_template('auth/registro.html', error="El usuario ya existe")
    
    if request.is_json:
        return jsonify({
            "message": "Usuario creado",
            "user_id": user_id
        }), 201
    
    return redirect(url_for('admin.usuarios'))


@auth_bp.route('/perfil', methods=['GET'])
@login_required
def perfil_page():
    """Página de perfil del usuario"""
    user_id = get_jwt_identity()
    user = obtener_usuario_por_id(user_id)
    return render_template('auth/perfil.html', user=user)


@auth_bp.route('/perfil', methods=['POST'])
@login_required
def actualizar_perfil():
    """Actualiza perfil del usuario"""
    user_id = get_jwt_identity()
    
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    # Solo permitir actualizar ciertos campos
    datos_update = {}
    if data.get('email'):
        datos_update['email'] = data['email'].strip()
    if data.get('nombre_completo'):
        datos_update['nombre_completo'] = data['nombre_completo'].strip()
    
    if datos_update:
        actualizar_usuario(user_id, datos_update)
    
    # Cambiar contraseña si se proporciona
    nuevo_password = data.get('nuevo_password')
    if nuevo_password:
        if len(nuevo_password) < 6:
            if request.is_json:
                return jsonify({"error": "Contraseña muy corta"}), 400
            return render_template('auth/perfil.html', error="Contraseña muy corta")
        cambiar_password(user_id, nuevo_password)
    
    if request.is_json:
        return jsonify({"message": "Perfil actualizado"}), 200
    
    return redirect(url_for('auth.perfil_page'))


# ================================================================================
# API DE AUTENTICACIÓN
# ================================================================================

@auth_bp.route('/api/me', methods=['GET'])
@login_required
def api_me():
    """Retorna información del usuario actual"""
    user_id = get_jwt_identity()
    user = obtener_usuario_por_id(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    return jsonify({
        "id": user['id'],
        "username": user['username'],
        "rol": user['rol'],
        "nombre_completo": user['nombre_completo'],
        "email": user['email']
    }), 200


@auth_bp.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Renueva el token de acceso"""
    user_id = get_jwt_identity()
    user = obtener_usuario_por_id(user_id)
    
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    access_token = create_access_token(
        identity=user_id,
        additional_claims={
            'username': user['username'],
            'rol': user['rol']
        }
    )
    
    return jsonify({"access_token": access_token}), 200
