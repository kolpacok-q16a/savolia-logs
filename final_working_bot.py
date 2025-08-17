import asyncio
import json
import logging
import os
import psutil
from datetime import datetime
from typing import Dict, Any, Optional
import threading

from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
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
bot = Bot(token=BOT_TOKEN)

class SystemMonitor:
    @staticmethod
    def get_system_info():
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
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
            stack = error_data['stackTrace'][:800] + '...[Обрезано]' if len(error_data['stackTrace']) > 800 else error_data['stackTrace']
            message += f"\n🔍 <b>Stack Trace:</b>\n<pre>{stack}</pre>"
        
        return message

    def send_error_to_admin_sync(self, error_data: Dict[str, Any]) -> bool:
        global error_count, platform_stats, recent_errors
        try:
            message = self.format_error_message(error_data)
            
            # Используем синхронный вызов
            import requests
            
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': ADMIN_ID,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
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
            else:
                logger.error(f"❌ Telegram API error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

error_logger = ErrorLogger()
system_monitor = SystemMonitor()

# Простые обработчики для webhook
def send_telegram_message(chat_id, text, reply_markup=None):
    """Синхронная отправка сообщения"""
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            payload['reply_markup'] = reply_markup.to_json()
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return False

def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    """Синхронное редактирование сообщения"""
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            payload['reply_markup'] = reply_markup.to_json()
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        return False

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

def handle_start_command(chat_id):
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
    
    return send_telegram_message(chat_id, message, get_main_keyboard())

def handle_callback_query(chat_id, message_id, callback_data):
    if callback_data == "refresh":
        return handle_refresh(chat_id, message_id)
    elif callback_data == "stats":
        return handle_stats(chat_id, message_id)
    elif callback_data == "system":
        return handle_system(chat_id, message_id)
    elif callback_data == "management":
        return handle_management(chat_id, message_id)
    elif callback_data == "logs":
        return handle_logs(chat_id, message_id)
    elif callback_data == "test_error":
        return handle_test_error(chat_id, message_id)
    
    return False

def handle_refresh(chat_id, message_id):
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
    
    return edit_telegram_message(chat_id, message_id, message, get_main_keyboard())

def handle_stats(chat_id, message_id):
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
    
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]])
    return edit_telegram_message(chat_id, message_id, message, back_keyboard)

def handle_system(chat_id, message_id):
    system_info = system_monitor.get_system_info()
    if not system_info:
        message = "❌ Не удалось получить системную информацию"
    else:
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
    
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]])
    return edit_telegram_message(chat_id, message_id, message, back_keyboard)

def handle_management(chat_id, message_id):
    keyboard = [
        [InlineKeyboardButton("📤 Тест ошибки", callback_data="test_error")],
        [InlineKeyboardButton("🔙 Назад", callback_data="refresh")]
    ]
    
    message = (
        f"⚙️ <b>Панель управления</b>\n\n"
        f"🤖 <b>Статус:</b>\n"
        f"• Режим: {'🔴 Обслуживание' if maintenance_mode else '🟢 Активен'}\n"
        f"• Ошибок обработано: {error_count}\n\n"
        f"🛠️ Доступные действия:"
    )
    
    return edit_telegram_message(chat_id, message_id, message, InlineKeyboardMarkup(keyboard))

def handle_logs(chat_id, message_id):
    if not recent_errors:
        message = "📝 <b>Логи ошибок</b>\n\n❌ Нет записей."
    else:
        message = f"📝 <b>Логи ошибок</b> (последние {min(len(recent_errors), 10)})\n\n"
        for i, error in enumerate(recent_errors[-10:], 1):
            time_str = error['timestamp'].strftime('%d.%m %H:%M')
            platform_icon = {'bot.ts': '🤖', 'savolia-frontend': '📱', 'savolia-web': '🌐'}.get(error['platform'], '❓')
            message += f"{i}. {time_str} | {platform_icon} {error['platform']}\n"
            message += f"   {error['error_type'][:25]}\n\n"
    
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]])
    return edit_telegram_message(chat_id, message_id, message, back_keyboard)

def handle_test_error(chat_id, message_id):
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
    
    success = error_logger.send_error_to_admin_sync(test_error)
    
    if success:
        message = "📤 <b>Тестовая ошибка отправлена!</b>\n\nПроверьте, пришло ли сообщение."
    else:
        message = "❌ <b>Ошибка отправки</b>"
    
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="management")]])
    return edit_telegram_message(chat_id, message_id, message, back_keyboard)

# Flask endpoints
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        
        if not json_data:
            return jsonify({'status': 'no_data'}), 200
        
        # Обработка обычного сообщения
        if 'message' in json_data:
            message = json_data['message']
            chat_id = message['chat']['id']
            user_id = str(message['from']['id'])
            
            if user_id != ADMIN_ID:
                logger.warning(f"🚫 Неавторизованный доступ: {user_id}")
                return jsonify({'status': 'unauthorized'}), 200
            
            if 'text' in message and message['text'].startswith('/start'):
                handle_start_command(chat_id)
        
        # Обработка callback query
        elif 'callback_query' in json_data:
            callback_query = json_data['callback_query']
            chat_id = callback_query['message']['chat']['id']
            message_id = callback_query['message']['message_id']
            user_id = str(callback_query['from']['id'])
            callback_data = callback_query['data']
            
            if user_id != ADMIN_ID:
                logger.warning(f"🚫 Неавторизованный callback: {user_id}")
                return jsonify({'status': 'unauthorized'}), 200
            
            handle_callback_query(chat_id, message_id, callback_data)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error'}), 200

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
        
        sent = error_logger.send_error_to_admin_sync(error_data)
        
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
        } if system_info else None
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
        import requests
        webhook_url = f"https://savolia-logs.onrender.com/webhook"
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        response = requests.post(url, json={'url': webhook_url}, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Webhook установлен")
        else:
            logger.error(f"❌ Ошибка установки webhook: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}")
    
    logger.info("🚀 Savolia Error Logger Bot запущен")
    logger.info(f"👤 Админ ID: {ADMIN_ID}")
    logger.info(f"🌐 Сервер: http://localhost:{PORT}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)