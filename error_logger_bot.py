import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from user_agents import parse as parse_user_agent
import threading

# Конфигурация
BOT_TOKEN = '8087171595:AAGcTv_TiNAY-Mv8CSyaIwk2tzYnnEM4Dsk'
ADMIN_ID = '7752180805'  # Только админ получает сообщения
PORT = int(os.environ.get('PORT', 3333))

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask приложение
app = Flask(__name__)
CORS(app)

class ErrorLogger:
    def __init__(self):
        self.platforms = {
            'bot.ts': '🤖 Telegram Bot',
            'savolia-frontend': '📱 Mini App (Telegram)',
            'savolia-web': '🌐 Web Site'
        }
        self.bot = None
        
    def set_bot(self, bot: Bot):
        """Устанавливает экземпляр бота"""
        self.bot = bot
    
    def format_error_message(self, error_data: Dict[str, Any]) -> str:
        """Форматирование сообщения об ошибке"""
        platform = error_data.get('platform', 'unknown')
        user_phone = error_data.get('userPhone', 'Не указан')
        device = error_data.get('device', 'Неизвестно')
        os_version = error_data.get('osVersion', 'Неизвестно')
        error_type = error_data.get('errorType', 'Общая ошибка')
        error_message = error_data.get('errorMessage', 'Нет описания')
        stack_trace = error_data.get('stackTrace')
        timestamp = error_data.get('timestamp')
        url = error_data.get('url')
        user_id = error_data.get('userId')
        user_agent = error_data.get('userAgent')
        additional_data = error_data.get('additionalData')
        
        platform_icon = self.platforms.get(platform, '❓ Unknown Platform')
        
        # Форматирование времени
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%d.%m.%Y %H:%M:%S')
            except:
                formatted_time = timestamp
        else:
            formatted_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        
        message = f"🚨 <b>ОШИБКА В SAVOLIA</b>\n\n"
        message += f"📍 <b>Платформа:</b> {platform_icon}\n"
        message += f"📱 <b>Номер пользователя:</b> <code>{user_phone}</code>\n"
        
        if user_id:
            message += f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            
        message += f"💻 <b>Устройство:</b> {device}\n"
        message += f"⚙️ <b>ОС:</b> {os_version}\n"
        message += f"❌ <b>Тип ошибки:</b> {error_type}\n"
        message += f"🕐 <b>Время:</b> {formatted_time}\n\n"
        
        if url:
            message += f"🔗 <b>URL:</b> <code>{url}</code>\n\n"
            
        message += f"📝 <b>Описание ошибки:</b>\n<code>{error_message}</code>\n\n"
        
        if stack_trace:
            # Обрезаем слишком длинный stack trace
            short_stack = stack_trace[:1000] + '...\n[Обрезано]' if len(stack_trace) > 1000 else stack_trace
            message += f"🔍 <b>Stack Trace:</b>\n<pre>{short_stack}</pre>\n\n"
            
        if user_agent:
            message += f"🌐 <b>User Agent:</b>\n<code>{user_agent}</code>\n\n"
            
        if additional_data and isinstance(additional_data, dict) and additional_data:
            formatted_data = json.dumps(additional_data, ensure_ascii=False, indent=2)
            message += f"📊 <b>Дополнительные данные:</b>\n<pre>{formatted_data}</pre>"
            
        return message
    
    def parse_user_agent(self, user_agent: Optional[str]) -> Dict[str, str]:
        """Парсинг User Agent для получения информации об устройстве"""
        if not user_agent:
            return {'device': 'Неизвестно', 'osVersion': 'Неизвестно'}
            
        try:
            parsed = parse_user_agent(user_agent)
            
            # Формируем название устройства
            device_parts = []
            if parsed.device.brand:
                device_parts.append(parsed.device.brand)
            if parsed.device.model:
                device_parts.append(parsed.device.model)
            if not device_parts and parsed.browser.family:
                device_parts.append(parsed.browser.family)
                
            device = ' '.join(device_parts) if device_parts else 'Неизвестно'
            
            # Формируем версию ОС
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
    
    async def send_error_to_admin(self, error_data: Dict[str, Any]) -> bool:
        """Отправка ошибки админу"""
        if not self.bot:
            logger.error("Бот не инициализирован")
            return False
            
        try:
            message = self.format_error_message(error_data)
            
            await self.bot.send_message(
                chat_id=ADMIN_ID,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.info(f"✅ Ошибка отправлена админу: {error_data.get('platform')} - {error_data.get('errorType')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке сообщения админу: {e}")
            return False

# Создаем экземпляр логгера
error_logger = ErrorLogger()

# Telegram бот handlers
async def start_command(update, context):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    
    if user_id != ADMIN_ID:
        logger.warning(f"🚫 Неавторизованный доступ от пользователя: {user_id}")
        return
    
    message = (
        "🚀 <b>Savolia Error Logger Bot</b>\n\n"
        "🔍 Этот бот отслеживает ошибки во всех платформах Savolia:\n"
        "• 🤖 Telegram Bot (bot.ts)\n"
        "• 📱 Mini App (savolia-frontend)\n"
        "• 🌐 Web Site (savolia-web)\n\n"
        "📊 <b>Доступные команды:</b>\n"
        "/status - Статус бота\n"
        "/help - Справка\n\n"
        "🔔 Все ошибки будут автоматически пересылаться сюда."
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def status_command(update, context):
    """Обработчик команды /status"""
    user_id = str(update.effective_user.id)
    
    if user_id != ADMIN_ID:
        return
    
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    platforms_count = len(error_logger.platforms)
    
    message = (
        "✅ <b>Статус системы:</b>\n\n"
        f"🤖 Бот: Активен\n"
        f"🌐 API: Работает на порту {PORT}\n"
        f"🕐 Время работы: {current_time}\n"
        f"📊 Платформы: {platforms_count}"
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def help_command(update, context):
    """Обработчик команды /help"""
    user_id = str(update.effective_user.id)
    
    if user_id != ADMIN_ID:
        return
    
    message = (
        "📖 <b>Справка по Error Logger Bot</b>\n\n"
        "<b>Формат ошибки:</b>\n"
        "• Платформа (bot.ts/frontend/web)\n"
        "• Номер пользователя\n"
        "• Устройство и ОС\n"
        "• Тип и описание ошибки\n"
        "• Stack trace\n"
        "• Время возникновения\n\n"
        "<b>API Endpoint:</b>\n"
        "<code>POST /api/log-error</code>\n\n"
        "Все ошибки автоматически форматируются и отправляются в этот чат."
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def handle_message(update, context):
    """Обработчик обычных сообщений"""
    user_id = str(update.effective_user.id)
    
    if user_id != ADMIN_ID:
        # Не отвечаем ничем другим пользователям
        logger.warning(f"🚫 Неавторизованное сообщение от пользователя: {user_id}")
        return

# Flask API endpoints
@app.route('/api/log-error', methods=['POST'])
def log_error():
    """API эндпоинт для получения ошибок"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Нет данных в запросе'
            }), 400
        
        # Валидация обязательных полей
        platform = data.get('platform')
        error_message = data.get('errorMessage')
        
        if not platform or not error_message:
            return jsonify({
                'success': False,
                'error': 'Обязательные поля: platform, errorMessage'
            }), 400
        
        # Парсинг User Agent
        user_agent = data.get('userAgent')
        device_info = error_logger.parse_user_agent(user_agent)
        
        # Формирование данных ошибки
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
        
        # Отправка ошибки админу асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sent = loop.run_until_complete(error_logger.send_error_to_admin(error_data))
        loop.close()
        
        if sent:
            return jsonify({
                'success': True,
                'message': 'Ошибка успешно зарегистрирована'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не удалось отправить ошибку'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка в API: {e}")
        return jsonify({
            'success': False,
            'error': 'Внутренняя ошибка сервера'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check эндпоинт"""
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat(),
        'service': 'Savolia Error Logger Bot'
    })

def run_bot():
    """Запуск Telegram бота"""
    async def main():
        # Создание приложения
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Устанавливаем бота в логгер
        error_logger.set_bot(application.bot)
        
        # Добавление обработчиков
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Запуск бота
        logger.info("🚀 Savolia Error Logger Bot запущен")
        logger.info(f"👤 Админ ID: {ADMIN_ID}")
        
        await application.run_polling()
    
    # Запуск в отдельном потоке
    asyncio.run(main())

if __name__ == '__main__':
    # Запуск бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запуск Flask сервера
    logger.info(f"🌐 API сервер запущен на http://localhost:{PORT}")
    logger.info(f"📡 Эндпоинт для ошибок: POST /api/log-error")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)