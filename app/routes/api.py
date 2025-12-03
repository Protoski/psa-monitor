"""
================================================================================
Rutas de API REST
Endpoints para plantas, equipos, monitoreo, estadísticas
================================================================================
"""

import os
import io
import csv
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response

from app.database import (
    # Plantas
    obtener_plantas, obtener_planta, crear_planta, actualizar_planta,
    actualizar_datos_monitoreo, eliminar_planta,
    # Equipos
    obtener_equipos, obtener_equipo, crear_equipo, actualizar_equipo, eliminar_equipo,
    obtener_tipos_equipo, obtener_series_equipo, crear_serie_equipo,
    # Estadísticas
    obtener_historial, calcular_estadisticas, obtener_estadisticas_globales,
    # Validaciones
    validar_patrimonio_unico, buscar_por_patrimonio
)
from app.routes.auth import login_required, admin_required, operador_required

api_bp = Blueprint('api', __name__)

# API Key para dispositivos IoT (ESP32, PLC, etc.)
API_KEY = os.environ.get("API_KEY", "clave_secreta_123")


def verificar_api_key():
    """Verifica API key en header o query param"""
    api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
    return api_key == API_KEY


# ================================================================================
# ENDPOINTS DE MONITOREO (Para ESP32/PLC)
# ================================================================================

@api_bp.route('/datos', methods=['POST'])
def recibir_datos():
    """Recibe datos de monitoreo desde dispositivos IoT"""
    if not verificar_api_key():
        return jsonify({"error": "No autorizado"}), 401
    
    try:
        datos = request.get_json()
        if not datos or "planta_id" not in datos:
            return jsonify({"error": "Datos incompletos - se requiere planta_id"}), 400
        
        planta_id = datos["planta_id"]
        
        # Obtener estado anterior para detectar nuevas alarmas
        planta_anterior = obtener_planta(planta_id)
        alarma_anterior = planta_anterior.get("alarma", False) if planta_anterior else False
        
        # Actualizar datos
        actualizar_datos_monitoreo(planta_id, datos)
        
        # TODO: Enviar alerta si hay nueva alarma (integrar con bot)
        nueva_alarma = datos.get("alarma", False) and not alarma_anterior
        
        return jsonify({
            "status": "ok",
            "planta_id": planta_id,
            "nueva_alarma": nueva_alarma
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/datos/batch', methods=['POST'])
def recibir_datos_batch():
    """Recibe múltiples lecturas de monitoreo"""
    if not verificar_api_key():
        return jsonify({"error": "No autorizado"}), 401
    
    try:
        datos_list = request.get_json()
        if not isinstance(datos_list, list):
            return jsonify({"error": "Se espera una lista de datos"}), 400
        
        procesados = 0
        errores = []
        
        for datos in datos_list:
            if "planta_id" in datos:
                try:
                    actualizar_datos_monitoreo(datos["planta_id"], datos)
                    procesados += 1
                except Exception as e:
                    errores.append(f"{datos.get('planta_id')}: {str(e)}")
        
        return jsonify({
            "status": "ok",
            "procesados": procesados,
            "errores": errores
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================================================================================
# ENDPOINTS DE PLANTAS
# ================================================================================

@api_bp.route('/plantas', methods=['GET'])
def listar_plantas():
    """Lista todas las plantas"""
    # Soportar tanto API key como JWT
    if not verificar_api_key():
        try:
            from flask_jwt_extended import verify_jwt_in_request
            verify_jwt_in_request()
        except:
            return jsonify({"error": "No autorizado"}), 401
    
    incluir_inactivas = request.args.get('incluir_inactivas', 'false').lower() == 'true'
    plantas = obtener_plantas(incluir_inactivas)
    
    # Convertir timestamps a string
    for p in plantas.values():
        for key in ['ultima_actualizacion', 'created_at', 'updated_at']:
            if p.get(key) and hasattr(p[key], 'isoformat'):
                p[key] = p[key].isoformat()
        for key in ['fecha_instalacion', 'fecha_ultimo_mantenimiento', 'proximo_mantenimiento']:
            if p.get(key) and hasattr(p[key], 'isoformat'):
                p[key] = p[key].isoformat()
    
    return jsonify(plantas), 200


@api_bp.route('/plantas/<planta_id>', methods=['GET'])
@login_required
def obtener_planta_api(planta_id):
    """Obtiene una planta específica"""
    planta = obtener_planta(planta_id)
    if not planta:
        return jsonify({"error": "Planta no encontrada"}), 404
    
    # Convertir timestamps
    for key in ['ultima_actualizacion', 'created_at', 'updated_at']:
        if planta.get(key) and hasattr(planta[key], 'isoformat'):
            planta[key] = planta[key].isoformat()
    
    return jsonify(planta), 200


@api_bp.route('/plantas', methods=['POST'])
@admin_required
def crear_planta_api():
    """Crea una nueva planta"""
    datos = request.get_json()
    
    if not datos:
        return jsonify({"error": "Datos requeridos"}), 400
    
    planta_id = datos.get('id', '').strip().lower().replace(' ', '_')
    nombre = datos.get('nombre', '').strip()
    
    if not planta_id or not nombre:
        return jsonify({"error": "ID y nombre son requeridos"}), 400
    
    # Validar patrimonio único si se proporciona
    if datos.get('numero_patrimonio'):
        if not validar_patrimonio_unico(datos['numero_patrimonio']):
            return jsonify({"error": "El número de patrimonio ya está en uso"}), 409
    
    if crear_planta(planta_id, nombre, datos):
        return jsonify({
            "message": "Planta creada",
            "id": planta_id
        }), 201
    else:
        return jsonify({"error": "Ya existe una planta con ese ID"}), 409


@api_bp.route('/plantas/<planta_id>', methods=['PUT', 'PATCH'])
@operador_required
def actualizar_planta_api(planta_id):
    """Actualiza datos de una planta"""
    datos = request.get_json()
    
    if not datos:
        return jsonify({"error": "Datos requeridos"}), 400
    
    # Validar patrimonio único si se cambia
    if datos.get('numero_patrimonio'):
        if not validar_patrimonio_unico(datos['numero_patrimonio'], excluir_planta=planta_id):
            return jsonify({"error": "El número de patrimonio ya está en uso"}), 409
    
    if actualizar_planta(planta_id, datos):
        return jsonify({"message": "Planta actualizada"}), 200
    else:
        return jsonify({"error": "No se pudo actualizar"}), 400


@api_bp.route('/plantas/<planta_id>', methods=['DELETE'])
@admin_required
def eliminar_planta_api(planta_id):
    """Elimina (desactiva) una planta"""
    if eliminar_planta(planta_id):
        return jsonify({"message": "Planta eliminada"}), 200
    else:
        return jsonify({"error": "Planta no encontrada"}), 404


# ================================================================================
# ENDPOINTS DE TIPOS DE EQUIPO
# ================================================================================

@api_bp.route('/tipos-equipo', methods=['GET'])
@login_required
def listar_tipos_equipo():
    """Lista todos los tipos de equipo"""
    tipos = obtener_tipos_equipo()
    return jsonify(tipos), 200


# ================================================================================
# ENDPOINTS DE SERIES DE EQUIPO
# ================================================================================

@api_bp.route('/series-equipo', methods=['GET'])
@login_required
def listar_series_equipo():
    """Lista series de equipo"""
    tipo_id = request.args.get('tipo_equipo_id', type=int)
    series = obtener_series_equipo(tipo_id)
    return jsonify(series), 200


@api_bp.route('/series-equipo', methods=['POST'])
@admin_required
def crear_serie_equipo_api():
    """Crea una nueva serie de equipo"""
    datos = request.get_json()
    
    if not datos:
        return jsonify({"error": "Datos requeridos"}), 400
    
    campos_requeridos = ['tipo_equipo_id', 'fabricante', 'modelo']
    for campo in campos_requeridos:
        if not datos.get(campo):
            return jsonify({"error": f"Campo requerido: {campo}"}), 400
    
    serie_id = crear_serie_equipo(datos)
    
    if serie_id:
        return jsonify({
            "message": "Serie creada",
            "id": serie_id
        }), 201
    else:
        return jsonify({"error": "Ya existe esa combinación fabricante/modelo"}), 409


# ================================================================================
# ENDPOINTS DE EQUIPOS
# ================================================================================

@api_bp.route('/equipos', methods=['GET'])
@login_required
def listar_equipos():
    """Lista equipos con filtros opcionales"""
    planta_id = request.args.get('planta_id')
    tipo_id = request.args.get('tipo_equipo_id', type=int)
    incluir_inactivos = request.args.get('incluir_inactivos', 'false').lower() == 'true'
    
    equipos = obtener_equipos(planta_id, tipo_id, incluir_inactivos)
    
    # Convertir fechas
    for e in equipos:
        for key in ['fecha_instalacion', 'fecha_ultimo_mantenimiento', 'proximo_mantenimiento', 
                    'fecha_baja', 'created_at', 'updated_at']:
            if e.get(key) and hasattr(e[key], 'isoformat'):
                e[key] = e[key].isoformat()
    
    return jsonify(equipos), 200


@api_bp.route('/equipos/<int:equipo_id>', methods=['GET'])
@login_required
def obtener_equipo_api(equipo_id):
    """Obtiene un equipo específico"""
    equipo = obtener_equipo(equipo_id)
    if not equipo:
        return jsonify({"error": "Equipo no encontrado"}), 404
    
    return jsonify(equipo), 200


@api_bp.route('/equipos', methods=['POST'])
@operador_required
def crear_equipo_api():
    """Crea un nuevo equipo"""
    datos = request.get_json()
    
    if not datos:
        return jsonify({"error": "Datos requeridos"}), 400
    
    campos_requeridos = ['planta_id', 'tipo_equipo_id', 'nombre']
    for campo in campos_requeridos:
        if not datos.get(campo):
            return jsonify({"error": f"Campo requerido: {campo}"}), 400
    
    # Validar que la planta existe
    if not obtener_planta(datos['planta_id']):
        return jsonify({"error": "Planta no encontrada"}), 404
    
    # Validar patrimonio único si se proporciona
    if datos.get('numero_patrimonio'):
        if not validar_patrimonio_unico(datos['numero_patrimonio']):
            return jsonify({"error": "El número de patrimonio ya está en uso"}), 409
    
    equipo_id = crear_equipo(datos)
    
    if equipo_id:
        return jsonify({
            "message": "Equipo creado",
            "id": equipo_id
        }), 201
    else:
        return jsonify({"error": "Error al crear equipo"}), 500


@api_bp.route('/equipos/<int:equipo_id>', methods=['PUT', 'PATCH'])
@operador_required
def actualizar_equipo_api(equipo_id):
    """Actualiza datos de un equipo"""
    datos = request.get_json()
    
    if not datos:
        return jsonify({"error": "Datos requeridos"}), 400
    
    # Validar patrimonio único si se cambia
    if datos.get('numero_patrimonio'):
        if not validar_patrimonio_unico(datos['numero_patrimonio'], excluir_equipo=equipo_id):
            return jsonify({"error": "El número de patrimonio ya está en uso"}), 409
    
    if actualizar_equipo(equipo_id, datos):
        return jsonify({"message": "Equipo actualizado"}), 200
    else:
        return jsonify({"error": "No se pudo actualizar"}), 400


@api_bp.route('/equipos/<int:equipo_id>', methods=['DELETE'])
@admin_required
def eliminar_equipo_api(equipo_id):
    """Elimina (desactiva) un equipo"""
    if eliminar_equipo(equipo_id):
        return jsonify({"message": "Equipo eliminado"}), 200
    else:
        return jsonify({"error": "Equipo no encontrado"}), 404


# ================================================================================
# ENDPOINTS DE HISTORIAL Y ESTADÍSTICAS
# ================================================================================

@api_bp.route('/historial', methods=['GET'])
def historial_api():
    """Obtiene historial de monitoreo"""
    if not verificar_api_key():
        try:
            from flask_jwt_extended import verify_jwt_in_request
            verify_jwt_in_request()
        except:
            return jsonify({"error": "No autorizado"}), 401
    
    planta_id = request.args.get('planta_id')
    if not planta_id:
        return jsonify({"error": "Se requiere planta_id"}), 400
    
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    limite = request.args.get('limite', type=int)
    
    datos = obtener_historial(planta_id, desde, hasta, limite)
    return jsonify(datos), 200


# Alias para compatibilidad con el código anterior
@api_bp.route('/historial_json', methods=['GET'])
def historial_json():
    """Alias para compatibilidad"""
    return historial_api()


@api_bp.route('/estadisticas', methods=['GET'])
def estadisticas_api():
    """Obtiene estadísticas"""
    if not verificar_api_key():
        try:
            from flask_jwt_extended import verify_jwt_in_request
            verify_jwt_in_request()
        except:
            return jsonify({"error": "No autorizado"}), 401
    
    planta_id = request.args.get('planta_id')
    
    if planta_id:
        desde = request.args.get('desde')
        hasta = request.args.get('hasta')
        datos = obtener_historial(planta_id, desde, hasta)
        stats = calcular_estadisticas(datos)
    else:
        stats = obtener_estadisticas_globales()
    
    return jsonify(stats), 200


@api_bp.route('/exportar_csv', methods=['GET'])
def exportar_csv():
    """Exporta datos a CSV"""
    if not verificar_api_key():
        try:
            from flask_jwt_extended import verify_jwt_in_request
            verify_jwt_in_request()
        except:
            return jsonify({"error": "No autorizado"}), 401
    
    planta_id = request.args.get('planta_id')
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    
    if planta_id and planta_id.lower() != 'all':
        datos = obtener_historial(planta_id, desde, hasta)
    else:
        # Exportar todas las plantas
        plantas = obtener_plantas()
        datos = []
        for pid in plantas:
            datos.extend(obtener_historial(pid, desde, hasta))
    
    if not datos:
        return Response("Sin datos", mimetype="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=datos[0].keys())
    writer.writeheader()
    writer.writerows(datos)
    
    filename = f"historial_{planta_id or 'todas'}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ================================================================================
# ENDPOINTS DE BÚSQUEDA
# ================================================================================

@api_bp.route('/buscar/patrimonio', methods=['GET'])
@login_required
def buscar_patrimonio():
    """Busca por número de patrimonio"""
    numero = request.args.get('numero', '')
    
    if not numero:
        return jsonify({"error": "Se requiere número de patrimonio"}), 400
    
    resultados = buscar_por_patrimonio(numero)
    return jsonify(resultados), 200


@api_bp.route('/validar/patrimonio', methods=['GET'])
@login_required
def validar_patrimonio():
    """Valida si un número de patrimonio está disponible"""
    numero = request.args.get('numero', '')
    excluir_planta = request.args.get('excluir_planta')
    excluir_equipo = request.args.get('excluir_equipo', type=int)
    
    if not numero:
        return jsonify({"error": "Se requiere número"}), 400
    
    disponible = validar_patrimonio_unico(numero, excluir_planta, excluir_equipo)
    return jsonify({"disponible": disponible}), 200


# ================================================================================
# HEALTH CHECK
# ================================================================================

@api_bp.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "database": "postgresql"
    }), 200
