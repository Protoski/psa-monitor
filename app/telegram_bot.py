"""
================================================================================
Bot de Telegram - Integración con PSA Monitor
================================================================================
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

from app.database import (
    obtener_plantas, obtener_planta, obtener_equipos,
    obtener_historial, calcular_estadisticas,
    obtener_usuario_por_telegram, crear_usuario, actualizar_usuario
)

logger = logging.getLogger(__name__)

# Configuración
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
ADMIN_PRINCIPAL_ID = int(os.environ.get("ADMIN_PRINCIPAL_ID", "0"))


# ================================================================================
# DECORADORES
# ================================================================================

def requiere_auth(func):
    """Decorador que requiere usuario registrado"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        usuario = obtener_usuario_por_telegram(user_id)
        
        if not usuario:
            await update.message.reply_text(
                "⚠️ No estás autorizado para usar este bot.\n"
                "Contacta al administrador para solicitar acceso."
            )
            return
        
        context.user_data['usuario'] = usuario
        return await func(update, context)
    return wrapper


def requiere_operador(func):
    """Decorador que requiere rol operador o admin"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        usuario = obtener_usuario_por_telegram(user_id)
        
        if not usuario or usuario.get('rol') not in ['admin', 'operador']:
            await update.message.reply_text("⛔ No tienes permisos para esta acción.")
            return
        
        context.user_data['usuario'] = usuario
        return await func(update, context)
    return wrapper


def requiere_admin(func):
    """Decorador que requiere rol admin"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        usuario = obtener_usuario_por_telegram(user_id)
        
        if not usuario or usuario.get('rol') != 'admin':
            await update.message.reply_text("⛔ Solo administradores pueden usar este comando.")
            return
        
        context.user_data['usuario'] = usuario
        return await func(update, context)
    return wrapper


# ================================================================================
# COMANDOS BÁSICOS
# ================================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    user = update.effective_user
    usuario = obtener_usuario_por_telegram(user.id)
    
    if usuario:
        await update.message.reply_text(
            f"👋 ¡Hola {usuario.get('nombre_completo') or usuario.get('username')}!\n\n"
            f"🏥 *PSA Monitor Bot*\n"
            f"Sistema de monitoreo de plantas de oxígeno\n\n"
            f"Usa /ayuda para ver los comandos disponibles.",
            parse_mode='Markdown'
        )
    else:
        # Usuario nuevo - verificar si es admin principal
        if user.id == ADMIN_PRINCIPAL_ID:
            # Auto-registrar admin principal
            crear_usuario(
                username=user.username or f"admin_{user.id}",
                password="telegram_auth",
                rol='admin',
                nombre_completo=user.full_name,
                telegram_id=user.id
            )
            await update.message.reply_text(
                f"✅ ¡Bienvenido Administrador!\n"
                f"Tu cuenta ha sido configurada automáticamente.\n"
                f"Usa /ayuda para comenzar."
            )
        else:
            await update.message.reply_text(
                f"👋 Hola {user.first_name}!\n\n"
                f"🏥 *PSA Monitor Bot*\n\n"
                f"No tienes acceso autorizado.\n"
                f"Tu ID de Telegram es: `{user.id}`\n\n"
                f"Envía este ID al administrador para solicitar acceso.",
                parse_mode='Markdown'
            )


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ayuda"""
    usuario = obtener_usuario_por_telegram(update.effective_user.id)
    
    comandos = [
        ("📊 /estado", "Ver estado de todas las plantas"),
        ("🏭 /planta [id]", "Ver detalles de una planta"),
        ("📈 /stats [id]", "Ver estadísticas de una planta"),
        ("⚙️ /equipos [id]", "Ver equipos de una planta"),
    ]
    
    if usuario and usuario.get('rol') in ['admin', 'operador']:
        comandos.extend([
            ("🔔 /alertas", "Configurar alertas"),
        ])
    
    if usuario and usuario.get('rol') == 'admin':
        comandos.extend([
            ("👥 /usuarios", "Gestionar usuarios"),
            ("➕ /autorizar [id]", "Autorizar nuevo usuario"),
        ])
    
    texto = "📖 *Comandos disponibles:*\n\n"
    for cmd, desc in comandos:
        texto += f"{cmd}\n    _{desc}_\n"
    
    await update.message.reply_text(texto, parse_mode='Markdown')


# ================================================================================
# COMANDOS DE MONITOREO
# ================================================================================

@requiere_auth
async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /estado - Ver estado de todas las plantas"""
    plantas = obtener_plantas()
    
    if not plantas:
        await update.message.reply_text("ℹ️ No hay plantas registradas.")
        return
    
    texto = "🏥 *Estado de Plantas PSA*\n\n"
    
    alarmas = []
    for planta_id, p in plantas.items():
        estado_icon = "🔴" if p.get('alarma') else ("🟢" if p.get('modo') == 'Producción' else "🟡")
        pureza = p.get('pureza_pct', 0) or 0
        flujo = p.get('flujo_nm3h', 0) or 0
        
        texto += f"{estado_icon} *{p.get('nombre')}*\n"
        texto += f"    O₂: {pureza:.1f}% | Flujo: {flujo:.1f} Nm³/h\n"
        texto += f"    Modo: {p.get('modo', 'Desconocido')}\n"
        
        if p.get('alarma'):
            alarmas.append(f"⚠️ {p.get('nombre')}: {p.get('mensaje_alarma', 'Alarma')}")
    
    if alarmas:
        texto += "\n🚨 *ALARMAS ACTIVAS:*\n"
        for a in alarmas:
            texto += f"{a}\n"
    
    # Botones para cada planta
    keyboard = []
    row = []
    for planta_id, p in plantas.items():
        row.append(InlineKeyboardButton(p.get('nombre', planta_id)[:15], callback_data=f"planta_{planta_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    await update.message.reply_text(
        texto,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )


@requiere_auth
async def cmd_planta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /planta [id] - Ver detalles de una planta"""
    if not context.args:
        # Mostrar lista de plantas
        plantas = obtener_plantas()
        keyboard = []
        for planta_id, p in plantas.items():
            keyboard.append([InlineKeyboardButton(
                f"🏭 {p.get('nombre')}", 
                callback_data=f"planta_{planta_id}"
            )])
        
        await update.message.reply_text(
            "Selecciona una planta:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    planta_id = context.args[0]
    await mostrar_planta(update, planta_id)


async def mostrar_planta(update: Update, planta_id: str, edit: bool = False):
    """Muestra detalles de una planta"""
    planta = obtener_planta(planta_id)
    
    if not planta:
        msg = "❌ Planta no encontrada."
        if edit:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    estado_icon = "🔴" if planta.get('alarma') else ("🟢" if planta.get('modo') == 'Producción' else "🟡")
    
    texto = f"{estado_icon} *{planta.get('nombre')}*\n"
    texto += f"📍 {planta.get('ubicacion') or planta.get('ciudad') or 'Sin ubicación'}\n\n"
    
    if planta.get('alarma'):
        texto += f"🚨 *ALARMA:* {planta.get('mensaje_alarma')}\n\n"
    
    texto += "📊 *Valores actuales:*\n"
    texto += f"• Pureza O₂: *{planta.get('pureza_pct', 0):.1f}%*\n"
    texto += f"• Flujo: *{planta.get('flujo_nm3h', 0):.1f}* Nm³/h\n"
    texto += f"• Presión: *{planta.get('presion_bar', 0):.1f}* bar\n"
    texto += f"• Temperatura: *{planta.get('temperatura_c', 0):.1f}°C*\n"
    texto += f"• Modo: {planta.get('modo', 'Desconocido')}\n"
    texto += f"• Horas: {planta.get('horas_operacion', 0):,}\n"
    
    if planta.get('ultima_actualizacion'):
        try:
            ultima = planta['ultima_actualizacion']
            if hasattr(ultima, 'strftime'):
                texto += f"\n🕐 Última actualización: {ultima.strftime('%H:%M:%S')}\n"
        except:
            pass
    
    # Botones
    keyboard = [
        [
            InlineKeyboardButton("📈 Stats 24h", callback_data=f"stats_{planta_id}_24h"),
            InlineKeyboardButton("⚙️ Equipos", callback_data=f"equipos_{planta_id}")
        ],
        [
            InlineKeyboardButton("📊 Stats 7d", callback_data=f"stats_{planta_id}_7d"),
            InlineKeyboardButton("🔄 Actualizar", callback_data=f"planta_{planta_id}")
        ],
        [InlineKeyboardButton("« Volver", callback_data="estado")]
    ]
    
    if edit:
        await update.callback_query.edit_message_text(
            texto, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            texto, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


@requiere_auth
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats [planta] - Ver estadísticas"""
    if not context.args:
        await update.message.reply_text(
            "Uso: /stats [planta_id]\n"
            "Ejemplo: /stats hospital_central"
        )
        return
    
    planta_id = context.args[0]
    await mostrar_stats(update, planta_id, '24h')


async def mostrar_stats(update: Update, planta_id: str, periodo: str, edit: bool = False):
    """Muestra estadísticas de una planta"""
    planta = obtener_planta(planta_id)
    
    if not planta:
        msg = "❌ Planta no encontrada."
        if edit:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    # Calcular rango de fechas
    horas = {'1h': 1, '6h': 6, '24h': 24, '7d': 168}.get(periodo, 24)
    desde = (datetime.now() - timedelta(hours=horas)).isoformat()
    
    datos = obtener_historial(planta_id, desde=desde)
    stats = calcular_estadisticas(datos)
    
    if not stats:
        msg = f"ℹ️ Sin datos para el período seleccionado."
        if edit:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    texto = f"📈 *Estadísticas: {planta.get('nombre')}*\n"
    texto += f"📅 Período: últimas {periodo}\n"
    texto += f"📝 Registros: {stats.get('periodo', {}).get('registros', 0)}\n\n"
    
    texto += "🫁 *Pureza O₂:*\n"
    pureza = stats.get('pureza', {})
    texto += f"   Min: {pureza.get('min', 0):.1f}% | Prom: {pureza.get('avg', 0):.1f}% | Max: {pureza.get('max', 0):.1f}%\n\n"
    
    texto += "💨 *Flujo:*\n"
    flujo = stats.get('flujo', {})
    texto += f"   Min: {flujo.get('min', 0):.1f} | Prom: {flujo.get('avg', 0):.1f} | Max: {flujo.get('max', 0):.1f} Nm³/h\n\n"
    
    kpis = stats.get('kpis', {})
    texto += "📊 *KPIs:*\n"
    texto += f"   Disponibilidad: {kpis.get('disponibilidad', 0):.1f}%\n"
    texto += f"   Cumplimiento pureza: {kpis.get('cumplimiento_pureza', 0):.1f}%\n"
    
    alarmas = stats.get('alarmas', {}).get('total', 0)
    if alarmas:
        texto += f"\n⚠️ Alarmas en el período: {alarmas}"
    
    keyboard = [
        [
            InlineKeyboardButton("1h", callback_data=f"stats_{planta_id}_1h"),
            InlineKeyboardButton("6h", callback_data=f"stats_{planta_id}_6h"),
            InlineKeyboardButton("24h", callback_data=f"stats_{planta_id}_24h"),
            InlineKeyboardButton("7d", callback_data=f"stats_{planta_id}_7d"),
        ],
        [InlineKeyboardButton("« Volver", callback_data=f"planta_{planta_id}")]
    ]
    
    if edit:
        await update.callback_query.edit_message_text(
            texto, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            texto, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


@requiere_auth
async def cmd_equipos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /equipos [planta] - Ver equipos"""
    if not context.args:
        await update.message.reply_text(
            "Uso: /equipos [planta_id]\n"
            "Ejemplo: /equipos hospital_central"
        )
        return
    
    planta_id = context.args[0]
    await mostrar_equipos(update, planta_id)


async def mostrar_equipos(update: Update, planta_id: str, edit: bool = False):
    """Muestra equipos de una planta"""
    planta = obtener_planta(planta_id)
    
    if not planta:
        msg = "❌ Planta no encontrada."
        if edit:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    equipos = obtener_equipos(planta_id)
    
    texto = f"⚙️ *Equipos: {planta.get('nombre')}*\n"
    texto += f"📍 Tipo: {planta.get('tipo_instalacion', 'simplex').capitalize()}\n\n"
    
    if not equipos:
        texto += "ℹ️ No hay equipos registrados."
    else:
        for eq in equipos:
            estado_icon = "🟢" if eq.get('estado') == 'operativo' else "🟡" if eq.get('estado') == 'standby' else "🔴"
            texto += f"{eq.get('tipo_icono', '⚙️')} *{eq.get('nombre')}*\n"
            texto += f"    {estado_icon} {eq.get('estado', 'N/A')}"
            if eq.get('marca') or eq.get('modelo'):
                texto += f" | {eq.get('marca', '')} {eq.get('modelo', '')}"
            texto += "\n"
            if eq.get('numero_patrimonio'):
                texto += f"    📋 Patr: {eq.get('numero_patrimonio')}\n"
    
    keyboard = [[InlineKeyboardButton("« Volver", callback_data=f"planta_{planta_id}")]]
    
    if edit:
        await update.callback_query.edit_message_text(
            texto, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            texto, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ================================================================================
# COMANDOS DE ADMINISTRACIÓN
# ================================================================================

@requiere_admin
async def cmd_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /usuarios - Gestionar usuarios"""
    from app.database import listar_usuarios
    
    usuarios = listar_usuarios()
    
    texto = "👥 *Usuarios del sistema:*\n\n"
    
    for u in usuarios:
        rol_icon = "👑" if u.get('rol') == 'admin' else "🔧" if u.get('rol') == 'operador' else "👁"
        estado = "✅" if u.get('activo') else "❌"
        texto += f"{rol_icon} {estado} *{u.get('username')}*"
        if u.get('telegram_id'):
            texto += f" (TG: {u.get('telegram_id')})"
        texto += f"\n    Rol: {u.get('rol')}\n"
    
    await update.message.reply_text(texto, parse_mode='Markdown')


@requiere_admin
async def cmd_autorizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /autorizar [telegram_id] [rol] - Autorizar usuario"""
    if len(context.args) < 1:
        await update.message.reply_text(
            "Uso: /autorizar [telegram_id] [rol]\n"
            "Roles: admin, operador, lector\n"
            "Ejemplo: /autorizar 123456789 operador"
        )
        return
    
    try:
        telegram_id = int(context.args[0])
        rol = context.args[1] if len(context.args) > 1 else 'lector'
        
        if rol not in ['admin', 'operador', 'lector']:
            rol = 'lector'
        
        # Verificar si ya existe
        usuario = obtener_usuario_por_telegram(telegram_id)
        
        if usuario:
            # Actualizar rol
            actualizar_usuario(usuario['id'], {'rol': rol})
            await update.message.reply_text(f"✅ Usuario actualizado a rol: {rol}")
        else:
            # Crear nuevo
            user_id = crear_usuario(
                username=f"tg_{telegram_id}",
                password="telegram_auth",
                rol=rol,
                telegram_id=telegram_id
            )
            if user_id:
                await update.message.reply_text(
                    f"✅ Usuario autorizado!\n"
                    f"ID: {telegram_id}\n"
                    f"Rol: {rol}\n\n"
                    f"El usuario debe enviar /start al bot para activar su cuenta."
                )
            else:
                await update.message.reply_text("❌ Error al crear usuario.")
    
    except ValueError:
        await update.message.reply_text("❌ ID de Telegram inválido.")


# ================================================================================
# CALLBACKS
# ================================================================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja callbacks de botones inline"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Verificar autenticación
    usuario = obtener_usuario_por_telegram(update.effective_user.id)
    if not usuario:
        await query.edit_message_text("⚠️ No autorizado.")
        return
    
    if data == "estado":
        # Volver al estado general
        plantas = obtener_plantas()
        texto = "🏥 *Estado de Plantas PSA*\n\n"
        
        for planta_id, p in plantas.items():
            estado_icon = "🔴" if p.get('alarma') else ("🟢" if p.get('modo') == 'Producción' else "🟡")
            texto += f"{estado_icon} *{p.get('nombre')}*: {p.get('pureza_pct', 0):.1f}%\n"
        
        keyboard = []
        row = []
        for planta_id, p in plantas.items():
            row.append(InlineKeyboardButton(p.get('nombre', planta_id)[:15], callback_data=f"planta_{planta_id}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        await query.edit_message_text(
            texto, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
    
    elif data.startswith("planta_"):
        planta_id = data.replace("planta_", "")
        await mostrar_planta(update, planta_id, edit=True)
    
    elif data.startswith("stats_"):
        parts = data.split("_")
        planta_id = parts[1]
        periodo = parts[2] if len(parts) > 2 else '24h'
        await mostrar_stats(update, planta_id, periodo, edit=True)
    
    elif data.startswith("equipos_"):
        planta_id = data.replace("equipos_", "")
        await mostrar_equipos(update, planta_id, edit=True)


# ================================================================================
# NOTIFICACIONES
# ================================================================================

async def enviar_alerta(app: Application, planta: dict, mensaje: str):
    """Envía alerta a usuarios con rol admin/operador"""
    from app.database import listar_usuarios
    
    usuarios = listar_usuarios()
    
    texto = f"🚨 *ALERTA - {planta.get('nombre')}*\n\n"
    texto += f"📍 {planta.get('ubicacion', '')}\n"
    texto += f"⚠️ {mensaje}\n\n"
    texto += f"📊 Valores actuales:\n"
    texto += f"• Pureza: {planta.get('pureza_pct', 0):.1f}%\n"
    texto += f"• Presión: {planta.get('presion_bar', 0):.1f} bar\n"
    texto += f"• Temperatura: {planta.get('temperatura_c', 0):.1f}°C"
    
    for u in usuarios:
        if u.get('telegram_id') and u.get('rol') in ['admin', 'operador'] and u.get('activo'):
            try:
                await app.bot.send_message(
                    chat_id=u['telegram_id'],
                    text=texto,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error enviando alerta a {u.get('username')}: {e}")


# ================================================================================
# INICIALIZACIÓN
# ================================================================================

def crear_bot_application() -> Optional[Application]:
    """Crea y configura la aplicación del bot"""
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN no configurado - Bot deshabilitado")
        return None
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("planta", cmd_planta))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("equipos", cmd_equipos))
    app.add_handler(CommandHandler("usuarios", cmd_usuarios))
    app.add_handler(CommandHandler("autorizar", cmd_autorizar))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("Bot de Telegram configurado")
    return app


async def iniciar_bot_polling():
    """Inicia el bot en modo polling"""
    app = crear_bot_application()
    if app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot de Telegram iniciado en modo polling")
        return app
    return None
