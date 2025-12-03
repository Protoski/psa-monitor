"""
================================================================================
Rutas de Administración
CRUD de Plantas, Equipos, Series, Usuarios
================================================================================
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from app.database import (
    # Plantas
    obtener_plantas, obtener_planta, crear_planta, actualizar_planta, eliminar_planta,
    # Equipos
    obtener_equipos, obtener_equipo, crear_equipo, actualizar_equipo, eliminar_equipo,
    obtener_tipos_equipo, obtener_series_equipo, crear_serie_equipo,
    # Usuarios
    listar_usuarios, obtener_usuario_por_id, crear_usuario, actualizar_usuario, cambiar_password,
    # Validaciones
    validar_patrimonio_unico
)
from app.routes.auth import login_required, admin_required, operador_required, get_current_user

admin_bp = Blueprint('admin', __name__)


# ================================================================================
# DASHBOARD ADMIN
# ================================================================================

@admin_bp.route('/')
@login_required
def index():
    """Panel de administración"""
    user = get_current_user()
    plantas = obtener_plantas(incluir_inactivas=True)
    equipos = obtener_equipos(incluir_inactivos=True)
    
    stats = {
        'total_plantas': len(plantas),
        'plantas_activas': sum(1 for p in plantas.values() if p.get('activa')),
        'total_equipos': len(equipos),
        'equipos_operativos': sum(1 for e in equipos if e.get('estado') == 'operativo')
    }
    
    return render_template('admin/index.html', user=user, stats=stats)


# ================================================================================
# CRUD PLANTAS
# ================================================================================

@admin_bp.route('/plantas')
@login_required
def plantas_lista():
    """Lista de plantas"""
    user = get_current_user()
    plantas = obtener_plantas(incluir_inactivas=True)
    return render_template('admin/plantas/lista.html', user=user, plantas=plantas)


@admin_bp.route('/plantas/nueva', methods=['GET', 'POST'])
@admin_required
def plantas_nueva():
    """Crear nueva planta"""
    user = get_current_user()
    
    if request.method == 'POST':
        planta_id = request.form.get('id', '').strip().lower().replace(' ', '_')
        nombre = request.form.get('nombre', '').strip()
        
        if not planta_id or not nombre:
            flash('ID y nombre son requeridos', 'error')
            return render_template('admin/plantas/form.html', user=user, planta=None)
        
        # Validar patrimonio
        patrimonio = request.form.get('numero_patrimonio', '').strip()
        if patrimonio and not validar_patrimonio_unico(patrimonio):
            flash('El número de patrimonio ya está en uso', 'error')
            return render_template('admin/plantas/form.html', user=user, planta=request.form)
        
        datos = {
            'codigo_interno': request.form.get('codigo_interno', '').strip() or None,
            'ubicacion': request.form.get('ubicacion', '').strip(),
            'direccion': request.form.get('direccion', '').strip() or None,
            'ciudad': request.form.get('ciudad', '').strip() or None,
            'departamento': request.form.get('departamento', '').strip() or None,
            'numero_patrimonio': patrimonio or None,
            'responsable': request.form.get('responsable', '').strip() or None,
            'telefono_contacto': request.form.get('telefono_contacto', '').strip() or None,
            'email_contacto': request.form.get('email_contacto', '').strip() or None,
            'tipo_instalacion': request.form.get('tipo_instalacion', 'simplex'),
            'capacidad_nominal_nm3h': float(request.form.get('capacidad_nominal_nm3h') or 0) or None,
            'fecha_instalacion': request.form.get('fecha_instalacion') or None,
            'notas': request.form.get('notas', '').strip() or None
        }
        
        if crear_planta(planta_id, nombre, datos):
            flash(f'Planta "{nombre}" creada correctamente', 'success')
            return redirect(url_for('admin.plantas_lista'))
        else:
            flash('Ya existe una planta con ese ID', 'error')
    
    return render_template('admin/plantas/form.html', user=user, planta=None)


@admin_bp.route('/plantas/<planta_id>/editar', methods=['GET', 'POST'])
@operador_required
def plantas_editar(planta_id):
    """Editar planta"""
    user = get_current_user()
    planta = obtener_planta(planta_id)
    
    if not planta:
        flash('Planta no encontrada', 'error')
        return redirect(url_for('admin.plantas_lista'))
    
    if request.method == 'POST':
        patrimonio = request.form.get('numero_patrimonio', '').strip()
        if patrimonio and not validar_patrimonio_unico(patrimonio, excluir_planta=planta_id):
            flash('El número de patrimonio ya está en uso', 'error')
            return render_template('admin/plantas/form.html', user=user, planta=planta)
        
        datos = {
            'nombre': request.form.get('nombre', '').strip(),
            'codigo_interno': request.form.get('codigo_interno', '').strip() or None,
            'ubicacion': request.form.get('ubicacion', '').strip(),
            'direccion': request.form.get('direccion', '').strip() or None,
            'ciudad': request.form.get('ciudad', '').strip() or None,
            'departamento': request.form.get('departamento', '').strip() or None,
            'numero_patrimonio': patrimonio or None,
            'responsable': request.form.get('responsable', '').strip() or None,
            'telefono_contacto': request.form.get('telefono_contacto', '').strip() or None,
            'email_contacto': request.form.get('email_contacto', '').strip() or None,
            'tipo_instalacion': request.form.get('tipo_instalacion', 'simplex'),
            'capacidad_nominal_nm3h': float(request.form.get('capacidad_nominal_nm3h') or 0) or None,
            'fecha_instalacion': request.form.get('fecha_instalacion') or None,
            'estado': request.form.get('estado', 'activa'),
            'notas': request.form.get('notas', '').strip() or None
        }
        
        if actualizar_planta(planta_id, datos):
            flash('Planta actualizada correctamente', 'success')
            return redirect(url_for('admin.plantas_lista'))
        else:
            flash('Error al actualizar', 'error')
    
    return render_template('admin/plantas/form.html', user=user, planta=planta)


@admin_bp.route('/plantas/<planta_id>/eliminar', methods=['POST'])
@admin_required
def plantas_eliminar(planta_id):
    """Eliminar planta"""
    if eliminar_planta(planta_id):
        flash('Planta eliminada correctamente', 'success')
    else:
        flash('Error al eliminar planta', 'error')
    
    return redirect(url_for('admin.plantas_lista'))


# ================================================================================
# CRUD EQUIPOS
# ================================================================================

@admin_bp.route('/equipos')
@login_required
def equipos_lista():
    """Lista de equipos"""
    user = get_current_user()
    
    planta_id = request.args.get('planta_id')
    tipo_id = request.args.get('tipo_equipo_id', type=int)
    
    equipos = obtener_equipos(planta_id, tipo_id, incluir_inactivos=True)
    plantas = obtener_plantas()
    tipos = obtener_tipos_equipo()
    
    return render_template('admin/equipos/lista.html', 
                           user=user, 
                           equipos=equipos,
                           plantas=plantas,
                           tipos=tipos,
                           filtro_planta=planta_id,
                           filtro_tipo=tipo_id)


@admin_bp.route('/equipos/nuevo', methods=['GET', 'POST'])
@operador_required
def equipos_nuevo():
    """Crear nuevo equipo"""
    user = get_current_user()
    plantas = obtener_plantas()
    tipos = obtener_tipos_equipo()
    series = obtener_series_equipo()
    
    # Pre-seleccionar planta si viene en query
    planta_id = request.args.get('planta_id')
    
    if request.method == 'POST':
        patrimonio = request.form.get('numero_patrimonio', '').strip()
        if patrimonio and not validar_patrimonio_unico(patrimonio):
            flash('El número de patrimonio ya está en uso', 'error')
            return render_template('admin/equipos/form.html', 
                                   user=user, equipo=request.form, 
                                   plantas=plantas, tipos=tipos, series=series)
        
        datos = {
            'planta_id': request.form.get('planta_id'),
            'tipo_equipo_id': int(request.form.get('tipo_equipo_id')),
            'serie_equipo_id': int(request.form.get('serie_equipo_id')) if request.form.get('serie_equipo_id') else None,
            'nombre': request.form.get('nombre', '').strip(),
            'numero_serie': request.form.get('numero_serie', '').strip() or None,
            'numero_patrimonio': patrimonio or None,
            'tag': request.form.get('tag', '').strip() or None,
            'marca': request.form.get('marca', '').strip() or None,
            'modelo': request.form.get('modelo', '').strip() or None,
            'año_fabricacion': int(request.form.get('año_fabricacion')) if request.form.get('año_fabricacion') else None,
            'ubicacion_interna': request.form.get('ubicacion_interna', '').strip() or None,
            'posicion': int(request.form.get('posicion', 1)),
            'estado': request.form.get('estado', 'operativo'),
            'criticidad': request.form.get('criticidad', 'media'),
            'fecha_instalacion': request.form.get('fecha_instalacion') or None,
            'horas_operacion': int(request.form.get('horas_operacion', 0)),
            'horas_proximo_servicio': int(request.form.get('horas_proximo_servicio')) if request.form.get('horas_proximo_servicio') else None,
            'notas': request.form.get('notas', '').strip() or None
        }
        
        if not datos['planta_id'] or not datos['nombre']:
            flash('Planta y nombre son requeridos', 'error')
            return render_template('admin/equipos/form.html', 
                                   user=user, equipo=request.form,
                                   plantas=plantas, tipos=tipos, series=series)
        
        equipo_id = crear_equipo(datos)
        
        if equipo_id:
            flash(f'Equipo "{datos["nombre"]}" creado correctamente', 'success')
            return redirect(url_for('admin.equipos_lista', planta_id=datos['planta_id']))
        else:
            flash('Error al crear equipo', 'error')
    
    return render_template('admin/equipos/form.html', 
                           user=user, 
                           equipo={'planta_id': planta_id} if planta_id else None,
                           plantas=plantas, 
                           tipos=tipos, 
                           series=series)


@admin_bp.route('/equipos/<int:equipo_id>/editar', methods=['GET', 'POST'])
@operador_required
def equipos_editar(equipo_id):
    """Editar equipo"""
    user = get_current_user()
    equipo = obtener_equipo(equipo_id)
    
    if not equipo:
        flash('Equipo no encontrado', 'error')
        return redirect(url_for('admin.equipos_lista'))
    
    plantas = obtener_plantas()
    tipos = obtener_tipos_equipo()
    series = obtener_series_equipo()
    
    if request.method == 'POST':
        patrimonio = request.form.get('numero_patrimonio', '').strip()
        if patrimonio and not validar_patrimonio_unico(patrimonio, excluir_equipo=equipo_id):
            flash('El número de patrimonio ya está en uso', 'error')
            return render_template('admin/equipos/form.html', 
                                   user=user, equipo=equipo,
                                   plantas=plantas, tipos=tipos, series=series)
        
        datos = {
            'planta_id': request.form.get('planta_id'),
            'serie_equipo_id': int(request.form.get('serie_equipo_id')) if request.form.get('serie_equipo_id') else None,
            'nombre': request.form.get('nombre', '').strip(),
            'numero_serie': request.form.get('numero_serie', '').strip() or None,
            'numero_patrimonio': patrimonio or None,
            'tag': request.form.get('tag', '').strip() or None,
            'marca': request.form.get('marca', '').strip() or None,
            'modelo': request.form.get('modelo', '').strip() or None,
            'año_fabricacion': int(request.form.get('año_fabricacion')) if request.form.get('año_fabricacion') else None,
            'ubicacion_interna': request.form.get('ubicacion_interna', '').strip() or None,
            'posicion': int(request.form.get('posicion', 1)),
            'estado': request.form.get('estado', 'operativo'),
            'criticidad': request.form.get('criticidad', 'media'),
            'fecha_instalacion': request.form.get('fecha_instalacion') or None,
            'horas_operacion': int(request.form.get('horas_operacion', 0)),
            'horas_proximo_servicio': int(request.form.get('horas_proximo_servicio')) if request.form.get('horas_proximo_servicio') else None,
            'notas': request.form.get('notas', '').strip() or None
        }
        
        if actualizar_equipo(equipo_id, datos):
            flash('Equipo actualizado correctamente', 'success')
            return redirect(url_for('admin.equipos_lista'))
        else:
            flash('Error al actualizar', 'error')
    
    return render_template('admin/equipos/form.html', 
                           user=user, 
                           equipo=equipo,
                           plantas=plantas, 
                           tipos=tipos, 
                           series=series)


@admin_bp.route('/equipos/<int:equipo_id>/eliminar', methods=['POST'])
@admin_required
def equipos_eliminar(equipo_id):
    """Eliminar equipo"""
    if eliminar_equipo(equipo_id):
        flash('Equipo eliminado correctamente', 'success')
    else:
        flash('Error al eliminar equipo', 'error')
    
    return redirect(url_for('admin.equipos_lista'))


# ================================================================================
# CRUD SERIES DE EQUIPO
# ================================================================================

@admin_bp.route('/series')
@login_required
def series_lista():
    """Lista de series de equipo"""
    user = get_current_user()
    series = obtener_series_equipo()
    tipos = obtener_tipos_equipo()
    return render_template('admin/series/lista.html', user=user, series=series, tipos=tipos)


@admin_bp.route('/series/nueva', methods=['GET', 'POST'])
@admin_required
def series_nueva():
    """Crear nueva serie de equipo"""
    user = get_current_user()
    tipos = obtener_tipos_equipo()
    
    if request.method == 'POST':
        datos = {
            'tipo_equipo_id': int(request.form.get('tipo_equipo_id')),
            'fabricante': request.form.get('fabricante', '').strip(),
            'modelo': request.form.get('modelo', '').strip(),
            'descripcion': request.form.get('descripcion', '').strip() or None,
            'manual_url': request.form.get('manual_url', '').strip() or None,
            'imagen_url': request.form.get('imagen_url', '').strip() or None
        }
        
        if not datos['fabricante'] or not datos['modelo']:
            flash('Fabricante y modelo son requeridos', 'error')
            return render_template('admin/series/form.html', user=user, serie=request.form, tipos=tipos)
        
        serie_id = crear_serie_equipo(datos)
        
        if serie_id:
            flash('Serie creada correctamente', 'success')
            return redirect(url_for('admin.series_lista'))
        else:
            flash('Ya existe esa combinación fabricante/modelo', 'error')
    
    return render_template('admin/series/form.html', user=user, serie=None, tipos=tipos)


# ================================================================================
# CRUD USUARIOS
# ================================================================================

@admin_bp.route('/usuarios')
@admin_required
def usuarios_lista():
    """Lista de usuarios"""
    user = get_current_user()
    usuarios = listar_usuarios()
    return render_template('admin/usuarios/lista.html', user=user, usuarios=usuarios)


@admin_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@admin_required
def usuarios_nuevo():
    """Crear nuevo usuario"""
    user = get_current_user()
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        rol = request.form.get('rol', 'lector')
        email = request.form.get('email', '').strip() or None
        nombre_completo = request.form.get('nombre_completo', '').strip() or None
        telegram_id = request.form.get('telegram_id', '').strip()
        
        if telegram_id:
            try:
                telegram_id = int(telegram_id)
            except:
                telegram_id = None
        else:
            telegram_id = None
        
        if not username or not password:
            flash('Usuario y contraseña son requeridos', 'error')
            return render_template('admin/usuarios/form.html', user=user, usuario=request.form)
        
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('admin/usuarios/form.html', user=user, usuario=request.form)
        
        user_id = crear_usuario(username, password, rol, email, nombre_completo, telegram_id)
        
        if user_id:
            flash(f'Usuario "{username}" creado correctamente', 'success')
            return redirect(url_for('admin.usuarios_lista'))
        else:
            flash('El usuario ya existe', 'error')
    
    return render_template('admin/usuarios/form.html', user=user, usuario=None)


@admin_bp.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@admin_required
def usuarios_editar(user_id):
    """Editar usuario"""
    user = get_current_user()
    usuario = obtener_usuario_por_id(user_id)
    
    if not usuario:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('admin.usuarios_lista'))
    
    if request.method == 'POST':
        datos = {
            'rol': request.form.get('rol', 'lector'),
            'email': request.form.get('email', '').strip() or None,
            'nombre_completo': request.form.get('nombre_completo', '').strip() or None,
            'activo': request.form.get('activo') == 'on'
        }
        
        telegram_id = request.form.get('telegram_id', '').strip()
        if telegram_id:
            try:
                datos['telegram_id'] = int(telegram_id)
            except:
                pass
        
        actualizar_usuario(user_id, datos)
        
        # Cambiar contraseña si se proporciona
        nuevo_password = request.form.get('nuevo_password', '')
        if nuevo_password:
            if len(nuevo_password) < 6:
                flash('Contraseña muy corta', 'error')
                return render_template('admin/usuarios/form.html', user=user, usuario=usuario)
            cambiar_password(user_id, nuevo_password)
        
        flash('Usuario actualizado correctamente', 'success')
        return redirect(url_for('admin.usuarios_lista'))
    
    return render_template('admin/usuarios/form.html', user=user, usuario=usuario)
