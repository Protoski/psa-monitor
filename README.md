# PSA Monitor v2.0

Sistema de Monitoreo de Plantas de Oxígeno PSA para el Ministerio de Salud.

## Características

- ✅ **Autenticación JWT** con login web y roles (admin, operador, lector)
- ✅ **Gestión de Plantas** con datos administrativos completos
- ✅ **Gestión de Equipos** por planta (compresores, PSA, secadores, etc.)
- ✅ **Series de Equipo** para catalogar modelos de fabricantes
- ✅ **Números de Patrimonio** únicos para plantas y equipos
- ✅ **Dashboard de Monitoreo** en tiempo real
- ✅ **SCADA** con gráficos Chart.js
- ✅ **API REST** para integración con ESP32/PLC
- ✅ **Bot de Telegram** para monitoreo y alertas
- ✅ **Exportación CSV** de datos históricos
- ✅ **Soporte Duplex/Triplex** para plantas con múltiples líneas

## Requisitos

- Python 3.9+
- PostgreSQL 13+

## Instalación Local

```bash
# Clonar o descargar
cd psa_monitor

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# Ejecutar
python main.py
```

## Despliegue en Render

1. Crear nuevo "Web Service" en Render
2. Conectar repositorio Git
3. Configurar:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app`
4. Agregar variables de entorno:
   - `DATABASE_URL` (desde PostgreSQL de Render)
   - `SECRET_KEY` (generar clave segura)
   - `JWT_SECRET_KEY` (generar otra clave)
   - `API_KEY` (para dispositivos IoT)
   - `ADMIN_PASSWORD` (contraseña inicial)

## Estructura del Proyecto

```
psa_monitor/
├── app/
│   ├── __init__.py         # Factory de la aplicación
│   ├── database.py         # Modelos y funciones de BD
│   └── routes/
│       ├── auth.py         # Autenticación
│       ├── api.py          # API REST
│       ├── dashboard.py    # Vistas del dashboard
│       └── admin.py        # CRUD administrativo
├── templates/
│   ├── base.html           # Template base
│   ├── auth/               # Login, perfil
│   ├── dashboard/          # Monitoreo, SCADA
│   └── admin/              # CRUD plantas, equipos
├── main.py                 # Entrada para desarrollo
├── wsgi.py                 # Entrada para producción
├── requirements.txt
└── Procfile               # Para Render
```

## API Endpoints

### Autenticación
- `POST /login` - Iniciar sesión
- `GET /logout` - Cerrar sesión

### Monitoreo (API Key o JWT)
- `POST /api/datos` - Enviar datos desde ESP32/PLC
- `GET /api/plantas` - Listar plantas
- `GET /api/historial?planta_id=X` - Obtener historial
- `GET /api/estadisticas?planta_id=X` - Estadísticas
- `GET /api/exportar_csv` - Exportar datos

### Gestión (Requiere JWT)
- `GET/POST /api/plantas` - CRUD plantas
- `GET/POST /api/equipos` - CRUD equipos
- `GET /api/tipos-equipo` - Tipos de equipo
- `GET/POST /api/series-equipo` - Series/modelos

## Tipos de Equipo Predefinidos

| Código | Nombre | Descripción |
|--------|--------|-------------|
| COMP_AIRE | Compresor de Aire | Alimentación del sistema |
| SECADOR | Secador de Aire | Por refrigeración o adsorción |
| PSA | Generador PSA | Generador de oxígeno |
| GEN_ELEC | Generador Eléctrico | Respaldo eléctrico |
| COMP_O2 | Compresor de O2 | Alta presión para balones |
| TANQUE | Tanque | Buffer o almacenamiento |
| ANALIZADOR | Analizador de O2 | Sensor de pureza |

## Ejemplo: Enviar datos desde ESP32

```cpp
#include <HTTPClient.h>

void enviarDatos() {
    HTTPClient http;
    http.begin("https://tu-app.onrender.com/api/datos");
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", "tu_api_key");
    
    String json = "{";
    json += "\"planta_id\": \"hospital_central\",";
    json += "\"nombre\": \"Hospital Central\",";
    json += "\"presion_bar\": 5.2,";
    json += "\"temperatura_c\": 28.5,";
    json += "\"pureza_pct\": 95.3,";
    json += "\"flujo_nm3h\": 45.0,";
    json += "\"modo\": \"Producción\",";
    json += "\"alarma\": false";
    json += "}";
    
    int code = http.POST(json);
    http.end();
}
```

## Acceso por Defecto

- **Usuario**: admin
- **Contraseña**: admin123 (cambiar en producción)

## Bot de Telegram (Opcional)

El sistema incluye un bot de Telegram para monitoreo remoto y alertas.

### Configuración

1. Crear bot con @BotFather en Telegram
2. Configurar variables de entorno:
   - `TELEGRAM_TOKEN`: Token del bot
   - `ADMIN_PRINCIPAL_ID`: Tu ID de Telegram (obtener con @userinfobot)

### Comandos del Bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Iniciar el bot |
| `/ayuda` | Ver comandos disponibles |
| `/estado` | Ver estado de todas las plantas |
| `/planta [id]` | Ver detalles de una planta |
| `/stats [id]` | Ver estadísticas |
| `/equipos [id]` | Ver equipos de una planta |
| `/usuarios` | (Admin) Gestionar usuarios |
| `/autorizar [id] [rol]` | (Admin) Autorizar usuario |

### Roles de Telegram

- **admin**: Acceso completo + gestión de usuarios
- **operador**: Monitoreo + configuración de alertas
- **lector**: Solo lectura de datos

## Licencia

Desarrollado por Dggies - Paraguay
