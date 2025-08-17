import asyncio
import json
import logging
import os
import psutil
from datetime import datetime
from typing import Dict, Any, Optional

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from user_agents import parse as parse_user_agent

# Конфигурация
BOT_TOKEN = '8087171595:AAGcTv_TiNAY-Mv8CSyaIwk2tzYnnEM4Dsk'
ADMIN_ID = '7752180805'
PORT = int(os.environ.get('PORT', 3333))

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные
start_time = datetime.now()
error_count = 0
platform_stats = {'bot.ts': 0, 'savolia-frontend': 0, 'savolia-web': 0}
recent_errors = []
maintenance_mode = False

# Создаем Flask приложение
app = Flask(__name__)
CORS(app)

# Создаем бота
bot = Bot(BOT_TOKEN)
application = None

class SystemMonitor:
    @staticmethod
    def get_system_info():
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu': {'percent': cpu_percent, 'count': psutil.cpu_count()},
                'memory': {
                    'total': round(memory.total / (1024**3), 2),
                    'used': round(memory.used / (1024**3), 2),
                    'percent': memory.percent
                },
                'disk': {
                    'total': round(disk.total / (1024**3), 2),
                    'used': round(disk.used / (1024**3), 2),
                    'percent': round((disk.used / disk.total) * 100, 1)
                },
                'uptime': str(datetime.now() - start_time).split('.')[0]
            }
        except Exception as e:
            logger.error(f"Ошибка получения системной информации: {e}")
            return None

class ErrorLogger:
    def __init__(self):
        self.platforms = {
            'bot.ts': '🤖 Telegram Bot',
            'savolia-frontend': '📱 Mini App (Telegram)', 
            'savolia-web': '🌐 Web Site'
        }

    def parse_user_agent(self, user_agent: Optional[str]) -> Dict[str, str]:
        if not user_agent:
            return {'device': 'Неизвестно', 'osVersion': 'Неизвестно'}
        try:
            parsed = parse_user_agent(user_agent)
            device_parts = []
            if parsed.device.brand:
                device_parts.append(parsed.device.brand)
            if parsed.device.model:
                device_parts.append(parsed.device.model)
            if not device_parts and parsed.browser.family:
                device_parts.append(parsed.browser.family)
            device = ' '.join(device_parts) if device_parts else 'Неизвестно'
            
            os_parts = []
            if parsed.os.family:
                os_parts.append(parsed.os.family)
            if parsed.os.version_string:
                os_parts.append(parsed.os.version_string)
            os_version = ' '.join(os_parts) if os_parts else 'Неизвестно'
            
            return {'device': device, 'osVersion': os_version}
        except Exception as e:
            logger.error(f"Ошибка парсинга User Agent: {e}")
            return {'device': 'Неизвестно', 'osVersion': 'Неизвестно'}

    def format_error_message(self, error_data: Dict[str, Any]) -> str:
        platform = error_data.get('platform', 'unknown')
        platform_icon = self.platforms.get(platform, '❓ Unknown Platform')
        
        if error_data.get('timestamp'):
            try:
                dt = datetime.fromisoformat(error_data['timestamp'].replace('Z', '+00:00'))
                formatted_time = dt.strftime('%d.%m.%Y %H:%M:%S')
            except:
                formatted_time = error_data['timestamp']
        else:
            formatted_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        
        message = f"🚨 <b>ОШИБКА В SAVOLIA</b>\n\n"
        message += f"📍 <b>Платформа:</b> {platform_icon}\n"
        message += f"📱 <b>Пользователь:</b> <code>{error_data.get('userPhone', 'Не указан')}</code>\n"
        message += f"💻 <b>Устройство:</b> {error_data.get('device', 'Неизвестно')}\n"
        message += f"⚙️ <b>ОС:</b> {error_data.get('osVersion', 'Неизвестно')}\n"
        message += f"❌ <b>Тип:</b> {error_data.get('errorType', 'Общая ошибка')}\n"
        message += f"🕐 <b>Время:</b> {formatted_time}\n\n"
        
        if error_data.get('url'):
            message += f"🔗 <b>URL:</b> <code>{error_data['url']}</code>\n\n"
        
        message += f"📝 <b>Описание:</b>\n<code>{error_data.get('errorMessage', 'Нет описания')}</code>\n"
        
        if error_data.get('stackTrace'):
            stack = error_data['stackTrace'][:1000] + '...[Обрезано]' if len(error_data['stackTrace']) > 1000 else error_data['stackTrace']
            message += f"\n🔍 <b>Stack Trace:</b>\n<pre>{stack}</pre>"
        
        return message

    async def send_error_to_admin(self, error_data: Dict[str, Any]) -> bool:
        global error_count, platform_stats, recent_errors
        try:
            message = self.format_error_message(error_data)
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            error_count += 1
            platform = error_data.get('platform', 'unknown')
            if platform in platform_stats:
                platform_stats[platform] += 1
            
            recent_errors.append({
                'timestamp': datetime.now(),
                'platform': platform,
                'error_type': error_data.get('errorType', 'Unknown'),
                'user_phone': error_data.get('userPhone', 'Unknown')
            })
            
            if len(recent_errors) > 50:
                recent_errors = recent_errors[-50:]
            
            logger.info(f"✅ Ошибка отправлена: {platform} - {error_data.get('errorType')}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

error_logger = ErrorLogger()
system_monitor = SystemMonitor()

# Клавиатуры
def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📊 Статистика", callback_data="stats"),
            InlineKeyboardButton("🖥️ Система", callback_data="system")
        ],
        [
            InlineKeyboardButton("⚙️ Управление", callback_data="management"),
            InlineKeyboardButton("📝 Логи", callback_data="logs")
        ],
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="refresh")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        logger.warning(f"🚫 Неавторизованный доступ: {user_id}")
        return
    
    system_info = system_monitor.get_system_info()
    
    message = (
        "🚀 <b>Savolia Error Logger Bot</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Ошибок: {error_count}\n"
        f"• Uptime: {system_info['uptime'] if system_info else 'N/A'}\n"
        f"• Режим: {'🔴 Обслуживание' if maintenance_mode else '🟢 Активен'}\n\n"
        f"🖥️ <b>Система:</b>\n"
        f"• CPU: {system_info['cpu']['percent'] if system_info else 'N/A'}%\n"
        f"• RAM: {system_info['memory']['percent'] if system_info else 'N/A'}%\n"
        f"• Диск: {system_info['disk']['percent'] if system_info else 'N/A'}%\n\n"
        "Выберите действие:"
    )
    
    await update.message.reply_text(
        message,
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if user_id != ADMIN_ID:
        await query.answer("❌ Доступ запрещен")
        return
    
    await query.answer()
    
    if query.data == "refresh":
        await show_main_menu(query)
    elif query.data == "stats":
        await show_statistics(query)
    elif query.data == "system":
        await show_system_info(query)
    elif query.data == "management":
        await show_management(query)
    elif query.data == "logs":
        await show_logs(query)
    elif query.data == "test_error":
        await send_test_error(query)

async def show_main_menu(query):
    system_info = system_monitor.get_system_info()
    message = (
        "🚀 <b>Savolia Error Logger Bot</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Ошибок: {error_count}\n"
        f"• Uptime: {system_info['uptime'] if system_info else 'N/A'}\n"
        f"• Режим: {'🔴 Обслуживание' if maintenance_mode else '🟢 Активен'}\n\n"
        f"🖥️ <b>Система:</b>\n"
        f"• CPU: {system_info['cpu']['percent'] if system_info else 'N/A'}%\n"
        f"• RAM: {system_info['memory']['percent'] if system_info else 'N/A'}%\n"
        f"• Диск: {system_info['disk']['percent'] if system_info else 'N/A'}%\n\n"
        "Выберите действие:"
    )
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=get_main_keyboard())

async def show_statistics(query):
    platform_text = "\n🏢 <b>По платформам:</b>\n"
    for platform, count in platform_stats.items():
        icon = {'bot.ts': '🤖', 'savolia-frontend': '📱', 'savolia-web': '🌐'}.get(platform, '❓')
        platform_text += f"• {icon} {platform}: {count}\n"
    
    recent_text = ""
    if recent_errors:
        recent_text = "\n📋 <b>Последние ошибки:</b>\n"
        for i, error in enumerate(recent_errors[-5:], 1):
            time_str = error['timestamp'].strftime('%H:%M:%S')
            recent_text += f"{i}. {time_str} | {error['platform']}\n"
    
    message = (
        f"📊 <b>Детальная статистика</b>\n\n"
        f"🔢 <b>Показатели:</b>\n"
        f"• Всего ошибок: {error_count}\n"
        f"• Время работы: {system_monitor.get_system_info()['uptime'] if system_monitor.get_system_info() else 'N/A'}\n"
        f"{platform_text}"
        f"{recent_text}"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]])
    )

async def show_system_info(query):
    system_info = system_monitor.get_system_info()
    if not system_info:
        await query.edit_message_text(
            "❌ Не удалось получить системную информацию",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]])
        )
        return
    
    message = (
        f"🖥️ <b>Мониторинг системы</b>\n\n"
        f"⚡ <b>CPU:</b> {system_info['cpu']['percent']}% ({system_info['cpu']['count']} ядер)\n\n"
        f"💾 <b>Память:</b>\n"
        f"• {system_info['memory']['used']} GB / {system_info['memory']['total']} GB\n"
        f"• {system_info['memory']['percent']}%\n\n"
        f"💿 <b>Диск:</b>\n"
        f"• {system_info['disk']['used']} GB / {system_info['disk']['total']} GB\n"
        f"• {system_info['disk']['percent']}%\n\n"
        f"🆙 <b>Uptime:</b> {system_info['uptime']}"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]])
    )

async def show_management(query):
    global maintenance_mode
    keyboard = [
        [InlineKeyboardButton("📤 Тест ошибки", callback_data="test_error")],
        [InlineKeyboardButton("🚫 Переключить режим обслуживания", callback_data="toggle_maintenance")],
        [InlineKeyboardButton("🔙 Назад", callback_data="refresh")]
    ]
    
    message = (
        f"⚙️ <b>Панель управления</b>\n\n"
        f"🤖 <b>Статус:</b>\n"
        f"• Режим: {'🔴 Обслуживание' if maintenance_mode else '🟢 Активен'}\n"
        f"• Ошибок обработано: {error_count}\n\n"
        f"🛠️ Доступные действия:"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_logs(query):
    if not recent_errors:
        message = "📝 <b>Логи ошибок</b>\n\n❌ Нет записей."
    else:
        message = f"📝 <b>Логи ошибок</b> (последние {min(len(recent_errors), 10)})\n\n"
        for i, error in enumerate(recent_errors[-10:], 1):
            time_str = error['timestamp'].strftime('%d.%m %H:%M')
            platform_icon = {'bot.ts': '🤖', 'savolia-frontend': '📱', 'savolia-web': '🌐'}.get(error['platform'], '❓')
            message += f"{i}. {time_str} | {platform_icon} {error['platform']}\n"
            message += f"   {error['error_type'][:25]}\n\n"
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]])
    )

async def send_test_error(query):
    test_error = {
        'platform': 'admin-panel',
        'userPhone': 'ADMIN TEST',
        'device': 'Admin Panel',
        'osVersion': 'System',
        'errorType': 'Test Error',
        'errorMessage': 'Тестовая ошибка из админ-панели',
        'timestamp': datetime.now().isoformat(),
        'additionalData': {'test': True}
    }
    
    success = await error_logger.send_error_to_admin(test_error)
    
    if success:
        await query.edit_message_text(
            "📤 <b>Тестовая ошибка отправлена!</b>\n\nПроверьте, пришло ли сообщение.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="management")]])
        )
    else:
        await query.edit_message_text(
            "❌ <b>Ошибка отправки</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="management")]])
        )

# Flask API endpoints
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        update = Update.de_json(json_data, bot)
        
        # Обработка в отдельном потоке
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if update.message and update.message.text:
            if update.message.text.startswith('/start'):
                loop.run_until_complete(start_command(update, None))
        elif update.callback_query:
            loop.run_until_complete(callback_handler(update, None))
        
        loop.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/api/log-error', methods=['POST'])
def log_error():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        if maintenance_mode:
            return jsonify({'success': False, 'error': 'Режим обслуживания'}), 503
        
        platform = data.get('platform')
        error_message = data.get('errorMessage')
        
        if not platform or not error_message:
            return jsonify({'success': False, 'error': 'Обязательные поля: platform, errorMessage'}), 400
        
        user_agent = data.get('userAgent')
        device_info = error_logger.parse_user_agent(user_agent)
        
        error_data = {
            'platform': platform,
            'userPhone': data.get('userPhone', 'Не указан'),
            'userId': data.get('userId'),
            'device': device_info['device'],
            'osVersion': device_info['osVersion'],
            'errorType': data.get('errorType', 'Runtime Error'),
            'errorMessage': error_message,
            'stackTrace': data.get('stackTrace'),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'url': data.get('url'),
            'userAgent': user_agent,
            'additionalData': data.get('additionalData')
        }
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sent = loop.run_until_complete(error_logger.send_error_to_admin(error_data))
        loop.close()
        
        if sent:
            return jsonify({'success': True, 'message': 'Ошибка зарегистрирована'})
        else:
            return jsonify({'success': False, 'error': 'Не удалось отправить'}), 500
            
    except Exception as e:
        logger.error(f"❌ API error: {e}")
        return jsonify({'success': False, 'error': 'Серверная ошибка'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    system_info = system_monitor.get_system_info()
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat(),
        'service': 'Savolia Error Logger Bot',
        'uptime': system_info['uptime'] if system_info else 'N/A',
        'errors_processed': error_count,
        'maintenance_mode': maintenance_mode,
        'system': {
            'cpu_percent': system_info['cpu']['percent'] if system_info else None,
            'memory_percent': system_info['memory']['percent'] if system_info else None,
            'disk_percent': system_info['disk']['percent'] if system_info else None
        }
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    system_info = system_monitor.get_system_info()
    return jsonify({
        'error_count': error_count,
        'platform_stats': platform_stats,
        'recent_errors_count': len(recent_errors),
        'system_stats': system_info,
        'maintenance_mode': maintenance_mode,
        'uptime': system_info['uptime'] if system_info else 'N/A'
    })

if __name__ == '__main__':
    # Установка webhook
    try:
        webhook_url = f"https://savolia-logs.onrender.com/webhook"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.set_webhook(url=webhook_url))
        loop.close()
        logger.info("✅ Webhook установлен")
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}")
    
    logger.info("🚀 Savolia Error Logger Bot запущен")
    logger.info(f"👤 Админ ID: {ADMIN_ID}")
    logger.info(f"🌐 Сервер: http://localhost:{PORT}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)