"""
================================================================================
Módulo de Base de Datos - PostgreSQL
Incluye: Usuarios, Plantas, Equipos, Series de Equipos, Patrimonio
================================================================================
"""

import os
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from statistics import mean, stdev

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ================================================================================
# CONEXIÓN
# ================================================================================

def get_db_connection():
    """Obtiene conexión a PostgreSQL"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL no configurada")
    
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


@contextmanager
def get_db():
    """Context manager para conexiones"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ================================================================================
# INICIALIZACIÓN DE TABLAS
# ================================================================================

def inicializar_db():
    """Crea todas las tablas necesarias"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # ============ USUARIOS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                nombre_completo VARCHAR(100),
                rol VARCHAR(20) DEFAULT 'lector' CHECK (rol IN ('admin', 'operador', 'lector')),
                telegram_id BIGINT UNIQUE,
                activo BOOLEAN DEFAULT TRUE,
                ultimo_acceso TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ============ PLANTAS (AMPLIADA) ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plantas (
                id VARCHAR(50) PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                codigo_interno VARCHAR(50) UNIQUE,
                ubicacion VARCHAR(200) DEFAULT '',
                direccion VARCHAR(200),
                ciudad VARCHAR(100),
                departamento VARCHAR(100),
                
                -- Datos administrativos
                numero_patrimonio VARCHAR(50) UNIQUE,
                responsable VARCHAR(100),
                telefono_contacto VARCHAR(50),
                email_contacto VARCHAR(100),
                
                -- Configuración
                tipo_instalacion VARCHAR(50) DEFAULT 'simplex' CHECK (tipo_instalacion IN ('simplex', 'duplex', 'triplex')),
                capacidad_nominal_nm3h REAL,
                fecha_instalacion DATE,
                fecha_ultimo_mantenimiento DATE,
                proximo_mantenimiento DATE,
                
                -- Estado operativo (actualizado por monitoreo)
                presion_bar REAL DEFAULT 0,
                temperatura_c REAL DEFAULT 0,
                pureza_pct REAL DEFAULT 0,
                flujo_nm3h REAL DEFAULT 0,
                horas_operacion INTEGER DEFAULT 0,
                modo VARCHAR(50) DEFAULT 'Desconocido',
                alarma BOOLEAN DEFAULT FALSE,
                mensaje_alarma TEXT DEFAULT '',
                ultima_actualizacion TIMESTAMP,
                
                -- Metadatos
                estado VARCHAR(20) DEFAULT 'activa' CHECK (estado IN ('activa', 'inactiva', 'mantenimiento', 'baja')),
                notas TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activa BOOLEAN DEFAULT TRUE
            )
        """)
        
        # ============ TIPOS DE EQUIPO ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tipos_equipo (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(20) UNIQUE NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                descripcion TEXT,
                icono VARCHAR(10) DEFAULT '⚙️',
                orden_display INTEGER DEFAULT 0
            )
        """)
        
        # Insertar tipos de equipo predefinidos
        tipos_equipo = [
            ('COMP_AIRE', 'Compresor de Aire', 'Compresor de aire para alimentación del sistema', '🌀', 1),
            ('SECADOR', 'Secador de Aire', 'Secador de aire por refrigeración o adsorción', '💨', 2),
            ('PSA', 'Generador PSA', 'Generador de oxígeno por adsorción PSA', '🫁', 3),
            ('GEN_ELEC', 'Generador Eléctrico', 'Generador eléctrico de respaldo', '⚡', 4),
            ('COMP_O2', 'Compresor de O2', 'Compresor de alta presión para llenado de balones', '🔵', 5),
            ('TANQUE', 'Tanque de Almacenamiento', 'Tanque buffer o de almacenamiento de O2', '🛢️', 6),
            ('ANALIZADOR', 'Analizador de O2', 'Analizador/sensor de pureza de oxígeno', '📊', 7),
            ('OTRO', 'Otro', 'Otro tipo de equipo', '🔧', 99),
        ]
        
        for codigo, nombre, desc, icono, orden in tipos_equipo:
            cursor.execute("""
                INSERT INTO tipos_equipo (codigo, nombre, descripcion, icono, orden_display)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (codigo) DO NOTHING
            """, (codigo, nombre, desc, icono, orden))
        
        # ============ SERIES DE EQUIPO (MODELOS) ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS series_equipo (
                id SERIAL PRIMARY KEY,
                tipo_equipo_id INTEGER REFERENCES tipos_equipo(id),
                fabricante VARCHAR(100) NOT NULL,
                modelo VARCHAR(100) NOT NULL,
                descripcion TEXT,
                
                -- Especificaciones técnicas (JSON flexible)
                especificaciones JSONB DEFAULT '{}',
                
                -- Documentación
                manual_url VARCHAR(500),
                imagen_url VARCHAR(500),
                
                -- Metadatos
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(fabricante, modelo)
            )
        """)
        
        # ============ EQUIPOS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipos (
                id SERIAL PRIMARY KEY,
                planta_id VARCHAR(50) REFERENCES plantas(id) ON DELETE CASCADE,
                tipo_equipo_id INTEGER REFERENCES tipos_equipo(id),
                serie_equipo_id INTEGER REFERENCES series_equipo(id),
                
                -- Identificación
                nombre VARCHAR(100) NOT NULL,
                numero_serie VARCHAR(100),
                numero_patrimonio VARCHAR(50) UNIQUE,
                tag VARCHAR(50),  -- Ej: COMP-01, PSA-A, etc.
                
                -- Detalles
                marca VARCHAR(100),
                modelo VARCHAR(100),
                año_fabricacion INTEGER,
                
                -- Ubicación dentro de la planta
                ubicacion_interna VARCHAR(100),  -- Ej: "Sala de compresores", "Línea A"
                posicion INTEGER DEFAULT 1,  -- Para plantas duplex: 1=primario, 2=secundario
                
                -- Estado
                estado VARCHAR(30) DEFAULT 'operativo' CHECK (estado IN ('operativo', 'standby', 'mantenimiento', 'fuera_servicio', 'baja')),
                criticidad VARCHAR(10) DEFAULT 'media' CHECK (criticidad IN ('baja', 'media', 'alta', 'critica')),
                
                -- Fechas
                fecha_instalacion DATE,
                fecha_ultimo_mantenimiento DATE,
                proximo_mantenimiento DATE,
                fecha_baja DATE,
                
                -- Horas de operación (si aplica)
                horas_operacion INTEGER DEFAULT 0,
                horas_proximo_servicio INTEGER,
                
                -- Notas
                notas TEXT,
                
                -- Metadatos
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ============ HISTORIAL DE MONITOREO ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id SERIAL PRIMARY KEY,
                planta_id VARCHAR(50) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                presion_bar REAL,
                temperatura_c REAL,
                pureza_pct REAL,
                flujo_nm3h REAL,
                modo VARCHAR(50),
                alarma BOOLEAN DEFAULT FALSE,
                mensaje_alarma TEXT,
                horas_operacion INTEGER DEFAULT 0
            )
        """)
        
        # ============ HISTORIAL DE EQUIPOS (MOVIMIENTOS) ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_equipos (
                id SERIAL PRIMARY KEY,
                equipo_id INTEGER REFERENCES equipos(id) ON DELETE CASCADE,
                tipo_evento VARCHAR(50) NOT NULL,  -- 'instalacion', 'mantenimiento', 'traslado', 'baja', 'reparacion'
                fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                descripcion TEXT,
                usuario_id INTEGER REFERENCES usuarios(id),
                planta_origen_id VARCHAR(50),
                planta_destino_id VARCHAR(50),
                datos_adicionales JSONB DEFAULT '{}'
            )
        """)
        
        # ============ CONFIGURACIÓN DE ALERTAS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_alertas (
                id SERIAL PRIMARY KEY,
                planta_id VARCHAR(50) UNIQUE REFERENCES plantas(id) ON DELETE CASCADE,
                intervalo_alerta_min INTEGER DEFAULT 5,
                alertas_activas BOOLEAN DEFAULT TRUE,
                pureza_minima REAL DEFAULT 93.0,
                presion_maxima REAL DEFAULT 7.0,
                temperatura_maxima REAL DEFAULT 45.0,
                notificar_telegram BOOLEAN DEFAULT TRUE,
                notificar_email BOOLEAN DEFAULT FALSE,
                emails_notificacion TEXT  -- Lista separada por comas
            )
        """)
        
        # ============ ÍNDICES ============
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historial_planta ON historial(planta_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historial_timestamp ON historial(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historial_planta_ts ON historial(planta_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipos_planta ON equipos(planta_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipos_tipo ON equipos(tipo_equipo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipos_patrimonio ON equipos(numero_patrimonio)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plantas_patrimonio ON plantas(numero_patrimonio)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_telegram ON usuarios(telegram_id)")
        
        logger.info("Base de datos PostgreSQL inicializada correctamente")


# ================================================================================
# FUNCIONES DE USUARIOS
# ================================================================================

def crear_usuario(username: str, password: str, rol: str = 'lector', 
                  email: str = None, nombre_completo: str = None,
                  telegram_id: int = None) -> Optional[int]:
    """Crea un nuevo usuario"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            password_hash = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO usuarios (username, password_hash, rol, email, nombre_completo, telegram_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (username, password_hash, rol, email, nombre_completo, telegram_id))
            result = cursor.fetchone()
            return result['id'] if result else None
    except psycopg2.IntegrityError as e:
        logger.error(f"Usuario ya existe: {e}")
        return None


def verificar_usuario(username: str, password: str) -> Optional[Dict]:
    """Verifica credenciales y retorna datos del usuario"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password_hash, rol, nombre_completo, email, telegram_id, activo
            FROM usuarios WHERE username = %s
        """, (username,))
        user = cursor.fetchone()
        
        if user and user['activo'] and check_password_hash(user['password_hash'], password):
            # Actualizar último acceso
            cursor.execute("""
                UPDATE usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id = %s
            """, (user['id'],))
            
            return {
                'id': user['id'],
                'username': user['username'],
                'rol': user['rol'],
                'nombre_completo': user['nombre_completo'],
                'email': user['email'],
                'telegram_id': user['telegram_id']
            }
        return None


def obtener_usuario_por_id(user_id: int) -> Optional[Dict]:
    """Obtiene usuario por ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, rol, nombre_completo, email, telegram_id, activo,
                   ultimo_acceso, created_at
            FROM usuarios WHERE id = %s
        """, (user_id,))
        return dict(cursor.fetchone()) if cursor.fetchone() else None


def obtener_usuario_por_telegram(telegram_id: int) -> Optional[Dict]:
    """Obtiene usuario por Telegram ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, rol, nombre_completo, telegram_id, activo
            FROM usuarios WHERE telegram_id = %s AND activo = TRUE
        """, (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def listar_usuarios() -> List[Dict]:
    """Lista todos los usuarios"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, rol, nombre_completo, email, telegram_id, 
                   activo, ultimo_acceso, created_at
            FROM usuarios ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def actualizar_usuario(user_id: int, datos: Dict) -> bool:
    """Actualiza datos de usuario"""
    campos_permitidos = ['email', 'nombre_completo', 'rol', 'telegram_id', 'activo']
    campos = {k: v for k, v in datos.items() if k in campos_permitidos}
    
    if not campos:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        sets = ", ".join([f"{k} = %s" for k in campos.keys()])
        values = list(campos.values()) + [user_id]
        cursor.execute(f"""
            UPDATE usuarios SET {sets}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, values)
        return cursor.rowcount > 0


def cambiar_password(user_id: int, nuevo_password: str) -> bool:
    """Cambia la contraseña de un usuario"""
    with get_db() as conn:
        cursor = conn.cursor()
        password_hash = generate_password_hash(nuevo_password)
        cursor.execute("""
            UPDATE usuarios SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (password_hash, user_id))
        return cursor.rowcount > 0


# ================================================================================
# FUNCIONES DE PLANTAS
# ================================================================================

def obtener_plantas(incluir_inactivas: bool = False) -> Dict[str, Dict]:
    """Obtiene todas las plantas"""
    with get_db() as conn:
        cursor = conn.cursor()
        if incluir_inactivas:
            cursor.execute("SELECT * FROM plantas ORDER BY nombre")
        else:
            cursor.execute("SELECT * FROM plantas WHERE activa = TRUE ORDER BY nombre")
        rows = cursor.fetchall()
        return {row["id"]: dict(row) for row in rows}


def obtener_planta(planta_id: str) -> Optional[Dict]:
    """Obtiene una planta por ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plantas WHERE id = %s", (planta_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def crear_planta(planta_id: str, nombre: str, datos: Dict = None) -> bool:
    """Crea una nueva planta"""
    datos = datos or {}
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO plantas (
                    id, nombre, codigo_interno, ubicacion, direccion, ciudad, departamento,
                    numero_patrimonio, responsable, telefono_contacto, email_contacto,
                    tipo_instalacion, capacidad_nominal_nm3h, fecha_instalacion, notas
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                planta_id, nombre,
                datos.get('codigo_interno'),
                datos.get('ubicacion', ''),
                datos.get('direccion'),
                datos.get('ciudad'),
                datos.get('departamento'),
                datos.get('numero_patrimonio'),
                datos.get('responsable'),
                datos.get('telefono_contacto'),
                datos.get('email_contacto'),
                datos.get('tipo_instalacion', 'simplex'),
                datos.get('capacidad_nominal_nm3h'),
                datos.get('fecha_instalacion'),
                datos.get('notas')
            ))
            
            # Crear configuración de alertas por defecto
            cursor.execute("""
                INSERT INTO config_alertas (planta_id) VALUES (%s)
                ON CONFLICT (planta_id) DO NOTHING
            """, (planta_id,))
            
            return True
    except psycopg2.IntegrityError as e:
        logger.error(f"Error creando planta: {e}")
        return False


def actualizar_planta(planta_id: str, datos: Dict) -> bool:
    """Actualiza datos de una planta (datos administrativos)"""
    campos_permitidos = [
        'nombre', 'codigo_interno', 'ubicacion', 'direccion', 'ciudad', 'departamento',
        'numero_patrimonio', 'responsable', 'telefono_contacto', 'email_contacto',
        'tipo_instalacion', 'capacidad_nominal_nm3h', 'fecha_instalacion',
        'fecha_ultimo_mantenimiento', 'proximo_mantenimiento', 'estado', 'notas'
    ]
    campos = {k: v for k, v in datos.items() if k in campos_permitidos}
    
    if not campos:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        sets = ", ".join([f"{k} = %s" for k in campos.keys()])
        values = list(campos.values()) + [planta_id]
        cursor.execute(f"""
            UPDATE plantas SET {sets}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, values)
        return cursor.rowcount > 0


def actualizar_datos_monitoreo(planta_id: str, datos: Dict):
    """Actualiza datos de monitoreo en tiempo real (desde ESP32/PLC)"""
    with get_db() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now()
        
        # Verificar si existe la planta
        cursor.execute("SELECT id FROM plantas WHERE id = %s", (planta_id,))
        existe = cursor.fetchone()
        
        if existe:
            cursor.execute("""
                UPDATE plantas SET
                    nombre = COALESCE(%s, nombre),
                    presion_bar = %s,
                    temperatura_c = %s,
                    pureza_pct = %s,
                    flujo_nm3h = %s,
                    horas_operacion = COALESCE(%s, horas_operacion),
                    modo = %s,
                    alarma = %s,
                    mensaje_alarma = %s,
                    ultima_actualizacion = %s
                WHERE id = %s
            """, (
                datos.get("nombre"),
                datos.get("presion_bar", 0),
                datos.get("temperatura_c", 0),
                datos.get("pureza_pct", 0),
                datos.get("flujo_nm3h", 0),
                datos.get("horas_operacion"),
                datos.get("modo", "Desconocido"),
                datos.get("alarma", False),
                datos.get("mensaje_alarma", ""),
                timestamp,
                planta_id
            ))
        else:
            # Crear planta básica si no existe
            cursor.execute("""
                INSERT INTO plantas (id, nombre, presion_bar, temperatura_c, pureza_pct,
                                    flujo_nm3h, horas_operacion, modo, alarma, 
                                    mensaje_alarma, ultima_actualizacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                planta_id,
                datos.get("nombre", f"Planta {planta_id}"),
                datos.get("presion_bar", 0),
                datos.get("temperatura_c", 0),
                datos.get("pureza_pct", 0),
                datos.get("flujo_nm3h", 0),
                datos.get("horas_operacion", 0),
                datos.get("modo", "Desconocido"),
                datos.get("alarma", False),
                datos.get("mensaje_alarma", ""),
                timestamp
            ))
        
        # Guardar en historial
        cursor.execute("""
            INSERT INTO historial (planta_id, timestamp, presion_bar, temperatura_c,
                                  pureza_pct, flujo_nm3h, modo, alarma, mensaje_alarma, horas_operacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            planta_id, timestamp,
            datos.get("presion_bar", 0),
            datos.get("temperatura_c", 0),
            datos.get("pureza_pct", 0),
            datos.get("flujo_nm3h", 0),
            datos.get("modo", ""),
            datos.get("alarma", False),
            datos.get("mensaje_alarma", ""),
            datos.get("horas_operacion", 0)
        ))


def eliminar_planta(planta_id: str, soft_delete: bool = True) -> bool:
    """Elimina o desactiva una planta"""
    with get_db() as conn:
        cursor = conn.cursor()
        if soft_delete:
            cursor.execute("""
                UPDATE plantas SET activa = FALSE, estado = 'baja', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (planta_id,))
        else:
            cursor.execute("DELETE FROM plantas WHERE id = %s", (planta_id,))
        return cursor.rowcount > 0


# ================================================================================
# FUNCIONES DE TIPOS DE EQUIPO
# ================================================================================

def obtener_tipos_equipo() -> List[Dict]:
    """Obtiene todos los tipos de equipo"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tipos_equipo ORDER BY orden_display")
        return [dict(row) for row in cursor.fetchall()]


# ================================================================================
# FUNCIONES DE SERIES DE EQUIPO
# ================================================================================

def obtener_series_equipo(tipo_equipo_id: int = None) -> List[Dict]:
    """Obtiene series de equipo, opcionalmente filtradas por tipo"""
    with get_db() as conn:
        cursor = conn.cursor()
        if tipo_equipo_id:
            cursor.execute("""
                SELECT se.*, te.nombre as tipo_nombre, te.codigo as tipo_codigo
                FROM series_equipo se
                JOIN tipos_equipo te ON se.tipo_equipo_id = te.id
                WHERE se.tipo_equipo_id = %s AND se.activo = TRUE
                ORDER BY se.fabricante, se.modelo
            """, (tipo_equipo_id,))
        else:
            cursor.execute("""
                SELECT se.*, te.nombre as tipo_nombre, te.codigo as tipo_codigo
                FROM series_equipo se
                JOIN tipos_equipo te ON se.tipo_equipo_id = te.id
                WHERE se.activo = TRUE
                ORDER BY te.orden_display, se.fabricante, se.modelo
            """)
        return [dict(row) for row in cursor.fetchall()]


def crear_serie_equipo(datos: Dict) -> Optional[int]:
    """Crea una nueva serie de equipo"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO series_equipo (tipo_equipo_id, fabricante, modelo, descripcion,
                                          especificaciones, manual_url, imagen_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                datos['tipo_equipo_id'],
                datos['fabricante'],
                datos['modelo'],
                datos.get('descripcion'),
                datos.get('especificaciones', '{}'),
                datos.get('manual_url'),
                datos.get('imagen_url')
            ))
            result = cursor.fetchone()
            return result['id'] if result else None
    except psycopg2.IntegrityError:
        return None


# ================================================================================
# FUNCIONES DE EQUIPOS
# ================================================================================

def obtener_equipos(planta_id: str = None, tipo_equipo_id: int = None, 
                    incluir_inactivos: bool = False) -> List[Dict]:
    """Obtiene equipos con filtros opcionales"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT e.*, 
                   te.nombre as tipo_nombre, te.codigo as tipo_codigo, te.icono as tipo_icono,
                   se.fabricante as serie_fabricante, se.modelo as serie_modelo,
                   p.nombre as planta_nombre
            FROM equipos e
            JOIN tipos_equipo te ON e.tipo_equipo_id = te.id
            LEFT JOIN series_equipo se ON e.serie_equipo_id = se.id
            LEFT JOIN plantas p ON e.planta_id = p.id
            WHERE 1=1
        """
        params = []
        
        if not incluir_inactivos:
            query += " AND e.activo = TRUE"
        
        if planta_id:
            query += " AND e.planta_id = %s"
            params.append(planta_id)
        
        if tipo_equipo_id:
            query += " AND e.tipo_equipo_id = %s"
            params.append(tipo_equipo_id)
        
        query += " ORDER BY te.orden_display, e.posicion, e.nombre"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def obtener_equipo(equipo_id: int) -> Optional[Dict]:
    """Obtiene un equipo por ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.*, 
                   te.nombre as tipo_nombre, te.codigo as tipo_codigo,
                   se.fabricante as serie_fabricante, se.modelo as serie_modelo,
                   p.nombre as planta_nombre
            FROM equipos e
            JOIN tipos_equipo te ON e.tipo_equipo_id = te.id
            LEFT JOIN series_equipo se ON e.serie_equipo_id = se.id
            LEFT JOIN plantas p ON e.planta_id = p.id
            WHERE e.id = %s
        """, (equipo_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def crear_equipo(datos: Dict) -> Optional[int]:
    """Crea un nuevo equipo"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO equipos (
                    planta_id, tipo_equipo_id, serie_equipo_id, nombre, numero_serie,
                    numero_patrimonio, tag, marca, modelo, año_fabricacion,
                    ubicacion_interna, posicion, estado, criticidad,
                    fecha_instalacion, horas_operacion, horas_proximo_servicio, notas
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                datos['planta_id'],
                datos['tipo_equipo_id'],
                datos.get('serie_equipo_id'),
                datos['nombre'],
                datos.get('numero_serie'),
                datos.get('numero_patrimonio'),
                datos.get('tag'),
                datos.get('marca'),
                datos.get('modelo'),
                datos.get('año_fabricacion'),
                datos.get('ubicacion_interna'),
                datos.get('posicion', 1),
                datos.get('estado', 'operativo'),
                datos.get('criticidad', 'media'),
                datos.get('fecha_instalacion'),
                datos.get('horas_operacion', 0),
                datos.get('horas_proximo_servicio'),
                datos.get('notas')
            ))
            result = cursor.fetchone()
            
            if result:
                # Registrar en historial
                cursor.execute("""
                    INSERT INTO historial_equipos (equipo_id, tipo_evento, descripcion, planta_destino_id)
                    VALUES (%s, 'instalacion', 'Equipo registrado en el sistema', %s)
                """, (result['id'], datos['planta_id']))
            
            return result['id'] if result else None
    except psycopg2.IntegrityError as e:
        logger.error(f"Error creando equipo: {e}")
        return None


def actualizar_equipo(equipo_id: int, datos: Dict) -> bool:
    """Actualiza datos de un equipo"""
    campos_permitidos = [
        'planta_id', 'serie_equipo_id', 'nombre', 'numero_serie', 'numero_patrimonio',
        'tag', 'marca', 'modelo', 'año_fabricacion', 'ubicacion_interna', 'posicion',
        'estado', 'criticidad', 'fecha_instalacion', 'fecha_ultimo_mantenimiento',
        'proximo_mantenimiento', 'horas_operacion', 'horas_proximo_servicio', 'notas'
    ]
    campos = {k: v for k, v in datos.items() if k in campos_permitidos}
    
    if not campos:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        sets = ", ".join([f"{k} = %s" for k in campos.keys()])
        values = list(campos.values()) + [equipo_id]
        cursor.execute(f"""
            UPDATE equipos SET {sets}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, values)
        return cursor.rowcount > 0


def eliminar_equipo(equipo_id: int, soft_delete: bool = True) -> bool:
    """Elimina o desactiva un equipo"""
    with get_db() as conn:
        cursor = conn.cursor()
        if soft_delete:
            cursor.execute("""
                UPDATE equipos SET activo = FALSE, estado = 'baja', 
                       fecha_baja = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (equipo_id,))
        else:
            cursor.execute("DELETE FROM equipos WHERE id = %s", (equipo_id,))
        return cursor.rowcount > 0


def buscar_por_patrimonio(numero: str) -> Dict:
    """Busca plantas y equipos por número de patrimonio"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Buscar en plantas
        cursor.execute("""
            SELECT 'planta' as tipo, id, nombre, numero_patrimonio, ubicacion
            FROM plantas WHERE numero_patrimonio ILIKE %s AND activa = TRUE
        """, (f"%{numero}%",))
        plantas = [dict(row) for row in cursor.fetchall()]
        
        # Buscar en equipos
        cursor.execute("""
            SELECT 'equipo' as tipo, e.id, e.nombre, e.numero_patrimonio, 
                   p.nombre as planta_nombre, e.planta_id
            FROM equipos e
            LEFT JOIN plantas p ON e.planta_id = p.id
            WHERE e.numero_patrimonio ILIKE %s AND e.activo = TRUE
        """, (f"%{numero}%",))
        equipos = [dict(row) for row in cursor.fetchall()]
        
        return {'plantas': plantas, 'equipos': equipos}


# ================================================================================
# FUNCIONES DE HISTORIAL Y ESTADÍSTICAS
# ================================================================================

def obtener_historial(planta_id: str, desde: str = None, hasta: str = None, 
                      limite: int = None) -> List[Dict]:
    """Obtiene historial de monitoreo"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT planta_id, timestamp, presion_bar, temperatura_c,
                   pureza_pct, flujo_nm3h, modo, alarma, mensaje_alarma, horas_operacion
            FROM historial WHERE planta_id = %s
        """
        params = [planta_id]
        
        if desde:
            if len(desde) == 10:
                desde = desde + "T00:00:00"
            query += " AND timestamp >= %s"
            params.append(desde)
        
        if hasta:
            if len(hasta) == 10:
                hasta = hasta + "T23:59:59"
            query += " AND timestamp <= %s"
            params.append(hasta)
        
        query += " ORDER BY timestamp ASC"
        
        if limite:
            query += f" LIMIT {limite}"
        
        cursor.execute(query, params)
        
        result = []
        for row in cursor.fetchall():
            r = dict(row)
            if r.get('timestamp'):
                r['timestamp'] = r['timestamp'].isoformat()
            result.append(r)
        
        return result


def calcular_estadisticas(datos: List[Dict]) -> Dict:
    """Calcula estadísticas de una lista de datos de monitoreo"""
    if not datos:
        return {}
    
    def safe_stats(values):
        values = [v for v in values if v is not None]
        if not values:
            return {"min": 0, "max": 0, "avg": 0, "std": 0, "count": 0}
        return {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(mean(values), 2),
            "std": round(stdev(values), 2) if len(values) > 1 else 0,
            "count": len(values)
        }
    
    pureza = [d.get("pureza_pct", 0) for d in datos]
    flujo = [d.get("flujo_nm3h", 0) for d in datos]
    presion = [d.get("presion_bar", 0) for d in datos]
    temperatura = [d.get("temperatura_c", 0) for d in datos]
    
    alarmas = sum(1 for d in datos if d.get("alarma"))
    
    modos = {}
    for d in datos:
        modo = d.get("modo", "Desconocido")
        modos[modo] = modos.get(modo, 0) + 1
    
    tiempo_produccion = modos.get("Producción", 0)
    disponibilidad = (tiempo_produccion / len(datos) * 100) if datos else 0
    pureza_ok = sum(1 for p in pureza if p >= 93)
    cumplimiento_pureza = (pureza_ok / len(pureza) * 100) if pureza else 0
    
    return {
        "periodo": {"registros": len(datos)},
        "pureza": safe_stats(pureza),
        "flujo": safe_stats(flujo),
        "presion": safe_stats(presion),
        "temperatura": safe_stats(temperatura),
        "alarmas": {"total": alarmas},
        "modos": modos,
        "kpis": {
            "disponibilidad": round(disponibilidad, 2),
            "cumplimiento_pureza": round(cumplimiento_pureza, 2)
        }
    }


def obtener_estadisticas_globales() -> Dict:
    """Obtiene estadísticas globales de todas las plantas"""
    plantas = obtener_plantas()
    
    total = len(plantas)
    operando = sum(1 for p in plantas.values() if p.get("modo") == "Producción")
    mant = sum(1 for p in plantas.values() if p.get("modo") == "Mantenimiento")
    alarma = sum(1 for p in plantas.values() if p.get("alarma"))
    
    if plantas:
        pureza_prom = mean([p.get("pureza_pct", 0) or 0 for p in plantas.values()])
        flujo_total = sum([p.get("flujo_nm3h", 0) or 0 for p in plantas.values()])
    else:
        pureza_prom = 0
        flujo_total = 0
    
    return {
        "total_plantas": total,
        "plantas_operando": operando,
        "plantas_mantenimiento": mant,
        "plantas_alarma": alarma,
        "pureza_promedio": round(pureza_prom, 2),
        "flujo_total": round(flujo_total, 2)
    }


# ================================================================================
# FUNCIONES DE VALIDACIÓN
# ================================================================================

def validar_patrimonio_unico(numero: str, excluir_planta: str = None, 
                              excluir_equipo: int = None) -> bool:
    """Valida que un número de patrimonio sea único"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verificar en plantas
        query = "SELECT id FROM plantas WHERE numero_patrimonio = %s AND activa = TRUE"
        params = [numero]
        if excluir_planta:
            query += " AND id != %s"
            params.append(excluir_planta)
        cursor.execute(query, params)
        if cursor.fetchone():
            return False
        
        # Verificar en equipos
        query = "SELECT id FROM equipos WHERE numero_patrimonio = %s AND activo = TRUE"
        params = [numero]
        if excluir_equipo:
            query += " AND id != %s"
            params.append(excluir_equipo)
        cursor.execute(query, params)
        if cursor.fetchone():
            return False
        
        return True
