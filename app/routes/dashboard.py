"""
================================================================================
Rutas del Dashboard
================================================================================
"""

import json
import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify

from app.database import (
    obtener_plantas, obtener_planta, obtener_equipos,
    obtener_historial, calcular_estadisticas, obtener_estadisticas_globales
)
from app.routes.auth import login_required, get_current_user

dashboard_bp = Blueprint('dashboard', __name__)

API_KEY = os.environ.get("API_KEY", "clave_secreta_123")


@dashboard_bp.route('/')
def index():
    """Página principal - redirige según autenticación"""
    user = get_current_user()
    if user:
        return render_template('dashboard/index.html', user=user)
    
    # Si no está logueado, mostrar dashboard público simplificado o redirigir
    from flask import redirect, url_for
    return redirect(url_for('auth.login_page'))


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal de monitoreo"""
    user = get_current_user()
    plantas = obtener_plantas()
    stats = obtener_estadisticas_globales()
    
    return render_template('dashboard/monitoreo.html', 
                           user=user,
                           plantas=plantas,
                           stats=stats)


@dashboard_bp.route('/planta/<planta_id>')
@login_required
def detalle_planta(planta_id):
    """Detalle de una planta específica"""
    user = get_current_user()
    planta = obtener_planta(planta_id)
    
    if not planta:
        return render_template('error.html', 
                               mensaje="Planta no encontrada",
                               detalle=f"No existe la planta con ID: {planta_id}"), 404
    
    equipos = obtener_equipos(planta_id)
    
    # Estadísticas últimas 24h
    desde = (datetime.now() - timedelta(hours=24)).isoformat()
    historial = obtener_historial(planta_id, desde=desde)
    stats_24h = calcular_estadisticas(historial)
    
    return render_template('dashboard/planta_detalle.html',
                           user=user,
                           planta=planta,
                           equipos=equipos,
                           stats=stats_24h)


@dashboard_bp.route('/reportes')
@login_required
def reportes():
    """Página de reportes"""
    user = get_current_user()
    plantas = obtener_plantas()
    
    return render_template('dashboard/reportes.html',
                           user=user,
                           plantas=plantas)


# ================================================================================
# DASHBOARD SCADA (Compatible con versión anterior)
# ================================================================================

@dashboard_bp.route('/scada')
def dashboard_scada():
    """Dashboard SCADA embebido (compatible con versión anterior)"""
    api_key = request.args.get("api_key")
    if api_key != API_KEY:
        # Verificar si está logueado
        user = get_current_user()
        if not user:
            return "No autorizado - Usa ?api_key=TU_CLAVE o inicia sesión", 401
    
    plantas = obtener_plantas()
    
    # Limpiar datos para JSON
    plantas_clean = {}
    for pid, p in plantas.items():
        plantas_clean[pid] = {}
        for k, v in p.items():
            if hasattr(v, 'isoformat'):
                plantas_clean[pid][k] = v.isoformat()
            else:
                plantas_clean[pid][k] = v
    
    if not plantas_clean:
        return """<html><body style='background:#0b1724;color:#fff;padding:50px;'>
                  <h2>No hay plantas registradas</h2>
                  <p>Use la API o el panel de admin para agregar plantas.</p>
                  </body></html>"""
    
    plantas_json = json.dumps(plantas_clean)
    
    # Template SCADA embebido
    return render_template('dashboard/scada.html', 
                           plantas_json=plantas_json,
                           api_key=api_key or API_KEY)
