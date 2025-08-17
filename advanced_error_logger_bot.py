import asyncio
import json
import logging
import os
import psutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
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

# Глобальные переменные для статистики
start_time = datetime.now()
error_count = 0
platform_stats = {'bot.ts': 0, 'savolia-frontend': 0, 'savolia-web': 0}
recent_errors = []

class SystemMonitor:
    """Мониторинг системы"""
    
    @staticmethod
    def get_system_info():
        """Получение информации о системе"""
        try:
            # CPU информация
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Память
            memory = psutil.virtual_memory()
            memory_total = round(memory.total / (1024**3), 2)
            memory_used = round(memory.used / (1024**3), 2)
            memory_percent = memory.percent
            
            # Диск
            disk = psutil.disk_usage('/')
            disk_total = round(disk.total / (1024**3), 2)
            disk_used = round(disk.used / (1024**3), 2)
            disk_percent = round((disk.used / disk.total) * 100, 1)
            
            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'total': memory_total,
                    'used': memory_used,
                    'percent': memory_percent
                },
                'disk': {
                    'total': disk_total,
                    'used': disk_used,
                    'percent': disk_percent
                },
                'uptime': str(uptime).split('.')[0],
                'boot_time': boot_time.strftime('%d.%m.%Y %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"Ошибка получения системной информации: {e}")
            return None

    @staticmethod
    def get_process_info():
        """Получение информации о процессах"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    if proc.info['cpu_percent'] > 1 or proc.info['memory_percent'] > 1:
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'][:15],
                            'cpu': round(proc.info['cpu_percent'], 1),
                            'memory': round(proc.info['memory_percent'], 1)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            # Сортируем по использованию CPU
            processes.sort(key=lambda x: x['cpu'], reverse=True)
            return processes[:10]  # Топ 10 процессов
        except Exception as e:
            logger.error(f"Ошибка получения информации о процессах: {e}")
            return []

    @staticmethod
    def get_network_info():
        """Получение сетевой информации"""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': round(net_io.bytes_sent / (1024**2), 2),
                'bytes_recv': round(net_io.bytes_recv / (1024**2), 2),
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except Exception as e:
            logger.error(f"Ошибка получения сетевой информации: {e}")
            return None

class BotManager:
    """Управление ботом"""
    
    def __init__(self):
        self.maintenance_mode = False
        self.blocked_users = set()
        self.bot_stats = {
            'messages_processed': 0,
            'errors_sent': 0,
            'uptime': start_time
        }

    def toggle_maintenance(self):
        """Переключение режима обслуживания"""
        self.maintenance_mode = not self.maintenance_mode
        return self.maintenance_mode

    def block_user(self, user_id: str):
        """Блокировка пользователя"""
        self.blocked_users.add(user_id)

    def unblock_user(self, user_id: str):
        """Разблокировка пользователя"""
        self.blocked_users.discard(user_id)

    def get_stats(self):
        """Получение статистики бота"""
        uptime = datetime.now() - self.bot_stats['uptime']
        return {
            **self.bot_stats,
            'uptime_str': str(uptime).split('.')[0],
            'maintenance_mode': self.maintenance_mode,
            'blocked_users_count': len(self.blocked_users)
        }

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
            short_ua = user_agent[:100] + '...' if len(user_agent) > 100 else user_agent
            message += f"🌐 <b>User Agent:</b>\n<code>{short_ua}</code>\n\n"
            
        if additional_data and isinstance(additional_data, dict) and additional_data:
            formatted_data = json.dumps(additional_data, ensure_ascii=False, indent=2)[:500]
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
        global error_count, platform_stats, recent_errors
        
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
            
            # Обновляем статистику
            error_count += 1
            platform = error_data.get('platform', 'unknown')
            if platform in platform_stats:
                platform_stats[platform] += 1
            
            # Добавляем в недавние ошибки
            recent_errors.append({
                'timestamp': datetime.now(),
                'platform': platform,
                'error_type': error_data.get('errorType', 'Unknown'),
                'user_phone': error_data.get('userPhone', 'Unknown')
            })
            
            # Оставляем только последние 50 ошибок
            if len(recent_errors) > 50:
                recent_errors = recent_errors[-50:]
            
            logger.info(f"✅ Ошибка отправлена админу: {error_data.get('platform')} - {error_data.get('errorType')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке сообщения админу: {e}")
            return False

# Создаем экземпляры
error_logger = ErrorLogger()
system_monitor = SystemMonitor()
bot_manager = BotManager()

# Функции для создания клавиатур
def get_main_keyboard():
    """Главная клавиатура админ-панели"""
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
            InlineKeyboardButton("🔄 Обновить", callback_data="refresh"),
            InlineKeyboardButton("❌ Закрыть", callback_data="close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_system_keyboard():
    """Клавиатура системного мониторинга"""
    keyboard = [
        [
            InlineKeyboardButton("💾 Память", callback_data="sys_memory"),
            InlineKeyboardButton("⚡ CPU", callback_data="sys_cpu")
        ],
        [
            InlineKeyboardButton("💿 Диск", callback_data="sys_disk"),
            InlineKeyboardButton("🌐 Сеть", callback_data="sys_network")
        ],
        [
            InlineKeyboardButton("🔄 Процессы", callback_data="sys_processes"),
            InlineKeyboardButton("🆙 Uptime", callback_data="sys_uptime")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="main"),
            InlineKeyboardButton("🔄 Обновить", callback_data="system")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_management_keyboard():
    """Клавиатура управления ботом"""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Перезагрузить", callback_data="mgmt_restart"),
            InlineKeyboardButton("⏸️ Пауза", callback_data="mgmt_pause")
        ],
        [
            InlineKeyboardButton("🧹 Очистить логи", callback_data="mgmt_clear_logs"),
            InlineKeyboardButton("📊 Сбросить статистику", callback_data="mgmt_reset_stats")
        ],
        [
            InlineKeyboardButton("🚫 Режим обслуживания", callback_data="mgmt_maintenance"),
            InlineKeyboardButton("📤 Тест ошибки", callback_data="mgmt_test_error")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="main"),
            InlineKeyboardButton("🔄 Обновить", callback_data="management")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Telegram бот handlers
async def start_command(update, context):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    
    if user_id != ADMIN_ID:
        logger.warning(f"🚫 Неавторизованный доступ от пользователя: {user_id}")
        return
    
    system_info = system_monitor.get_system_info()
    bot_stats = bot_manager.get_stats()
    
    message = (
        "🚀 <b>Savolia Error Logger Bot - Админ Панель</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Ошибок обработано: {error_count}\n"
        f"• Время работы: {bot_stats['uptime_str']}\n"
        f"• Режим обслуживания: {'🔴 ВКЛ' if bot_manager.maintenance_mode else '🟢 ВЫКЛ'}\n\n"
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

async def admin_panel_command(update, context):
    """Обработчик команды /panel"""
    await start_command(update, context)

async def callback_handler(update, context):
    """Обработчик callback запросов"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if user_id != ADMIN_ID:
        await query.answer("❌ Доступ запрещен")
        return
    
    await query.answer()
    
    if query.data == "close":
        await query.delete_message()
        return
    
    if query.data == "main":
        await start_command(query, context)
        return
        
    if query.data == "refresh":
        await start_command(query, context)
        return
    
    # Статистика
    if query.data == "stats":
        await show_statistics(query)
    
    # Система
    elif query.data == "system":
        await show_system_info(query)
    elif query.data.startswith("sys_"):
        await show_detailed_system_info(query, query.data[4:])
    
    # Управление
    elif query.data == "management":
        await show_management_panel(query)
    elif query.data.startswith("mgmt_"):
        await handle_management_action(query, query.data[5:])
    
    # Логи
    elif query.data == "logs":
        await show_logs(query)

async def show_statistics(query):
    """Показать детальную статистику"""
    global error_count, platform_stats, recent_errors
    
    bot_stats = bot_manager.get_stats()
    
    # Последние ошибки
    recent_text = ""
    if recent_errors:
        recent_text = "\n📋 <b>Последние ошибки:</b>\n"
        for i, error in enumerate(recent_errors[-5:], 1):
            time_str = error['timestamp'].strftime('%H:%M:%S')
            recent_text += f"{i}. {time_str} | {error['platform']} | {error['error_type'][:20]}\n"
    
    # Статистика по платформам
    platform_text = "\n🏢 <b>По платформам:</b>\n"
    for platform, count in platform_stats.items():
        icon = {'bot.ts': '🤖', 'savolia-frontend': '📱', 'savolia-web': '🌐'}.get(platform, '❓')
        platform_text += f"• {icon} {platform}: {count}\n"
    
    message = (
        f"📊 <b>Детальная статистика</b>\n\n"
        f"🔢 <b>Общие показатели:</b>\n"
        f"• Всего ошибок: {error_count}\n"
        f"• Время работы: {bot_stats['uptime_str']}\n"
        f"• Сообщений обработано: {bot_stats['messages_processed']}\n"
        f"• Заблокированных пользователей: {bot_stats['blocked_users_count']}\n"
        f"{platform_text}"
        f"{recent_text}"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="main")]
        ])
    )

async def show_system_info(query):
    """Показать информацию о системе"""
    system_info = system_monitor.get_system_info()
    
    if not system_info:
        await query.edit_message_text(
            "❌ Не удалось получить информацию о системе",
            reply_markup=get_system_keyboard()
        )
        return
    
    message = (
        f"🖥️ <b>Мониторинг системы</b>\n\n"
        f"⚡ <b>CPU:</b>\n"
        f"• Использование: {system_info['cpu']['percent']}%\n"
        f"• Ядер: {system_info['cpu']['count']}\n\n"
        f"💾 <b>Память:</b>\n"
        f"• Использовано: {system_info['memory']['used']} GB / {system_info['memory']['total']} GB\n"
        f"• Процент: {system_info['memory']['percent']}%\n\n"
        f"💿 <b>Диск:</b>\n"
        f"• Использовано: {system_info['disk']['used']} GB / {system_info['disk']['total']} GB\n"
        f"• Процент: {system_info['disk']['percent']}%\n\n"
        f"🆙 <b>Время работы:</b>\n"
        f"• Uptime: {system_info['uptime']}\n"
        f"• Загрузка: {system_info['boot_time']}"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=get_system_keyboard()
    )

async def show_detailed_system_info(query, info_type):
    """Показать детальную информацию о системе"""
    if info_type == "processes":
        processes = system_monitor.get_process_info()
        message = "🔄 <b>Топ процессы:</b>\n\n"
        
        for i, proc in enumerate(processes, 1):
            message += f"{i}. <code>{proc['name']}</code>\n"
            message += f"   PID: {proc['pid']} | CPU: {proc['cpu']}% | RAM: {proc['memory']}%\n\n"
            
    elif info_type == "network":
        net_info = system_monitor.get_network_info()
        if net_info:
            message = (
                f"🌐 <b>Сетевая статистика:</b>\n\n"
                f"📤 <b>Отправлено:</b>\n"
                f"• Данных: {net_info['bytes_sent']} MB\n"
                f"• Пакетов: {net_info['packets_sent']}\n\n"
                f"📥 <b>Получено:</b>\n"
                f"• Данных: {net_info['bytes_recv']} MB\n"
                f"• Пакетов: {net_info['packets_recv']}"
            )
        else:
            message = "❌ Не удалось получить сетевую информацию"
    else:
        message = "❌ Неизвестный тип информации"
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="system")]
        ])
    )

async def show_management_panel(query):
    """Показать панель управления"""
    bot_stats = bot_manager.get_stats()
    
    message = (
        f"⚙️ <b>Панель управления</b>\n\n"
        f"🤖 <b>Статус бота:</b>\n"
        f"• Режим обслуживания: {'🔴 ВКЛ' if bot_manager.maintenance_mode else '🟢 ВЫКЛ'}\n"
        f"• Время работы: {bot_stats['uptime_str']}\n"
        f"• Заблокированных пользователей: {bot_stats['blocked_users_count']}\n\n"
        f"🛠️ Выберите действие:"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=get_management_keyboard()
    )

async def handle_management_action(query, action):
    """Обработка действий управления"""
    global error_count, platform_stats, recent_errors
    
    if action == "restart":
        await query.edit_message_text(
            "🔄 <b>Перезагрузка бота...</b>\n\n⚠️ Бот будет недоступен несколько секунд.",
            parse_mode='HTML'
        )
        # В реальном приложении здесь был бы код перезагрузки
        await asyncio.sleep(2)
        await query.edit_message_text(
            "✅ <b>Бот успешно перезагружен!</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="management")]
            ])
        )
        
    elif action == "pause":
        await query.edit_message_text(
            "⏸️ <b>Бот приостановлен</b>\n\nОбработка новых ошибок временно остановлена.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Возобновить", callback_data="mgmt_resume")],
                [InlineKeyboardButton("🔙 Назад", callback_data="management")]
            ])
        )
        
    elif action == "resume":
        await query.edit_message_text(
            "▶️ <b>Бот возобновлен</b>\n\nОбработка ошибок продолжена.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="management")]
            ])
        )
        
    elif action == "clear_logs":
        recent_errors.clear()
        await query.edit_message_text(
            "🧹 <b>Логи очищены</b>\n\nВсе записи о недавних ошибках удалены.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="management")]
            ])
        )
        
    elif action == "reset_stats":
        error_count = 0
        platform_stats = {'bot.ts': 0, 'savolia-frontend': 0, 'savolia-web': 0}
        bot_manager.bot_stats['messages_processed'] = 0
        bot_manager.bot_stats['errors_sent'] = 0
        
        await query.edit_message_text(
            "📊 <b>Статистика сброшена</b>\n\nВсе счетчики обнулены.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="management")]
            ])
        )
        
    elif action == "maintenance":
        mode = bot_manager.toggle_maintenance()
        status = "включен" if mode else "выключен"
        icon = "🔴" if mode else "🟢"
        
        await query.edit_message_text(
            f"🚫 <b>Режим обслуживания {status}</b>\n\n{icon} Статус: {'ВКЛ' if mode else 'ВЫКЛ'}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="management")]
            ])
        )
        
    elif action == "test_error":
        # Отправляем тестовую ошибку
        test_error = {
            'platform': 'admin-panel',
            'userPhone': 'ADMIN TEST',
            'userId': 'admin',
            'device': 'Admin Panel',
            'osVersion': 'System',
            'errorType': 'Test Error',
            'errorMessage': 'Это тестовая ошибка для проверки админ-панели',
            'timestamp': datetime.now().isoformat(),
            'additionalData': {'test': True, 'source': 'admin_panel'}
        }
        
        success = await error_logger.send_error_to_admin(test_error)
        
        if success:
            await query.edit_message_text(
                "📤 <b>Тестовая ошибка отправлена</b>\n\nПроверьте, пришло ли сообщение.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="management")]
                ])
            )
        else:
            await query.edit_message_text(
                "❌ <b>Ошибка отправки</b>\n\nНе удалось отправить тестовую ошибку.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="management")]
                ])
            )

async def show_logs(query):
    """Показать логи"""
    if not recent_errors:
        message = "📝 <b>Логи ошибок</b>\n\n❌ Нет записей об ошибках."
    else:
        message = f"📝 <b>Логи ошибок</b> (последние {min(len(recent_errors), 20)})\n\n"
        
        for i, error in enumerate(recent_errors[-20:], 1):
            time_str = error['timestamp'].strftime('%d.%m %H:%M:%S')
            platform_icon = {'bot.ts': '🤖', 'savolia-frontend': '📱', 'savolia-web': '🌐'}.get(error['platform'], '❓')
            
            message += f"{i}. {time_str} | {platform_icon} {error['platform']}\n"
            message += f"   {error['error_type'][:30]} | {error['user_phone'][:15]}\n\n"
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🧹 Очистить", callback_data="mgmt_clear_logs")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main")]
        ])
    )

async def handle_message(update, context):
    """Обработчик обычных сообщений"""
    user_id = str(update.effective_user.id)
    
    if user_id != ADMIN_ID:
        logger.warning(f"🚫 Неавторизованное сообщение от пользователя: {user_id}")
        return

# Flask API endpoints (без изменений)
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
        
        # Проверка режима обслуживания
        if bot_manager.maintenance_mode:
            return jsonify({
                'success': False,
                'error': 'Бот находится в режиме обслуживания'
            }), 503
        
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
            bot_manager.bot_stats['messages_processed'] += 1
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
    system_info = system_monitor.get_system_info()
    bot_stats = bot_manager.get_stats()
    
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat(),
        'service': 'Savolia Error Logger Bot',
        'uptime': bot_stats['uptime_str'],
        'errors_processed': error_count,
        'maintenance_mode': bot_manager.maintenance_mode,
        'system': {
            'cpu_percent': system_info['cpu']['percent'] if system_info else None,
            'memory_percent': system_info['memory']['percent'] if system_info else None,
            'disk_percent': system_info['disk']['percent'] if system_info else None
        }
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """API для получения статистики"""
    bot_stats = bot_manager.get_stats()
    system_info = system_monitor.get_system_info()
    
    return jsonify({
        'bot_stats': bot_stats,
        'system_stats': system_info,
        'error_count': error_count,
        'platform_stats': platform_stats,
        'recent_errors_count': len(recent_errors)
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
        application.add_handler(CommandHandler("panel", admin_panel_command))
        application.add_handler(CallbackQueryHandler(callback_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Запуск бота
        logger.info("🚀 Savolia Error Logger Bot с админ-панелью запущен")
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
    logger.info(f"📊 Статистика: GET /api/stats")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)