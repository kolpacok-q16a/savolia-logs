const TelegramBot = require('node-telegram-bot-api');
const express = require('express');
const cors = require('cors');
const moment = require('moment');
const UAParser = require('ua-parser-js');

// Конфигурация
const BOT_TOKEN = '8087171595:AAGcTv_TiNAY-Mv8CSyaIwk2tzYnnEM4Dsk';
const ADMIN_ID = '7752180805'; // Только админ получает сообщения
const PORT = process.env.PORT || 3333;

// Инициализация бота
const bot = new TelegramBot(BOT_TOKEN, { polling: true });
const app = express();

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

console.log('🚀 Savolia Error Logger Bot запущен');
console.log(`👤 Админ ID: ${ADMIN_ID}`);
console.log(`🌐 Сервер запущен на порту: ${PORT}`);

// Класс для обработки ошибок
class ErrorLogger {
  constructor() {
    this.platforms = {
      'bot.ts': '🤖 Telegram Bot',
      'savolia-frontend': '📱 Mini App (Telegram)',
      'savolia-web': '🌐 Web Site'
    };
  }

  // Форматирование сообщения об ошибке
  formatErrorMessage(errorData) {
    const {
      platform,
      userPhone,
      device,
      osVersion,
      errorType,
      errorMessage,
      stackTrace,
      timestamp,
      url,
      userId,
      userAgent,
      additionalData
    } = errorData;

    const platformIcon = this.platforms[platform] || '❓ Unknown Platform';
    const formattedTime = moment(timestamp).format('DD.MM.YYYY HH:mm:ss');
    
    let message = `🚨 <b>ОШИБКА В SAVOLIA</b>\n\n`;
    message += `📍 <b>Платформа:</b> ${platformIcon}\n`;
    message += `📱 <b>Номер пользователя:</b> <code>${userPhone || 'Не указан'}</code>\n`;
    
    if (userId) {
      message += `🆔 <b>User ID:</b> <code>${userId}</code>\n`;
    }
    
    message += `💻 <b>Устройство:</b> ${device || 'Неизвестно'}\n`;
    message += `⚙️ <b>ОС:</b> ${osVersion || 'Неизвестно'}\n`;
    message += `❌ <b>Тип ошибки:</b> ${errorType || 'Общая ошибка'}\n`;
    message += `🕐 <b>Время:</b> ${formattedTime}\n\n`;
    
    if (url) {
      message += `🔗 <b>URL:</b> <code>${url}</code>\n\n`;
    }
    
    message += `📝 <b>Описание ошибки:</b>\n<code>${errorMessage}</code>\n\n`;
    
    if (stackTrace) {
      // Обрезаем слишком длинный stack trace
      const shortStack = stackTrace.length > 1000 
        ? stackTrace.substring(0, 1000) + '...\n[Обрезано]' 
        : stackTrace;
      message += `🔍 <b>Stack Trace:</b>\n<pre>${shortStack}</pre>\n\n`;
    }
    
    if (userAgent) {
      message += `🌐 <b>User Agent:</b>\n<code>${userAgent}</code>\n\n`;
    }
    
    if (additionalData && Object.keys(additionalData).length > 0) {
      message += `📊 <b>Дополнительные данные:</b>\n<pre>${JSON.stringify(additionalData, null, 2)}</pre>`;
    }
    
    return message;
  }

  // Парсинг User Agent для получения информации об устройстве
  parseUserAgent(userAgent) {
    if (!userAgent) return { device: 'Неизвестно', osVersion: 'Неизвестно' };
    
    const parser = new UAParser(userAgent);
    const result = parser.getResult();
    
    const device = `${result.device.vendor || ''} ${result.device.model || result.browser.name || 'Unknown'}`.trim();
    const osVersion = `${result.os.name || 'Unknown'} ${result.os.version || ''}`.trim();
    
    return { device, osVersion };
  }

  // Отправка ошибки админу
  async sendErrorToAdmin(errorData) {
    try {
      const message = this.formatErrorMessage(errorData);
      
      await bot.sendMessage(ADMIN_ID, message, {
        parse_mode: 'HTML',
        disable_web_page_preview: true
      });
      
      console.log(`✅ Ошибка отправлена админу: ${errorData.platform} - ${errorData.errorType}`);
      return true;
    } catch (error) {
      console.error('❌ Ошибка при отправке сообщения админу:', error);
      return false;
    }
  }
}

const errorLogger = new ErrorLogger();

// API эндпоинт для получения ошибок
app.post('/api/log-error', async (req, res) => {
  try {
    const {
      platform,
      userPhone,
      userId,
      errorType,
      errorMessage,
      stackTrace,
      url,
      userAgent,
      additionalData
    } = req.body;

    // Валидация обязательных полей
    if (!platform || !errorMessage) {
      return res.status(400).json({
        success: false,
        error: 'Обязательные поля: platform, errorMessage'
      });
    }

    // Парсинг User Agent для получения информации об устройстве
    const deviceInfo = errorLogger.parseUserAgent(userAgent);

    // Формирование данных ошибки
    const errorData = {
      platform,
      userPhone: userPhone || 'Не указан',
      userId,
      device: deviceInfo.device,
      osVersion: deviceInfo.osVersion,
      errorType: errorType || 'Runtime Error',
      errorMessage,
      stackTrace,
      timestamp: new Date().toISOString(),
      url,
      userAgent,
      additionalData
    };

    // Отправка ошибки админу
    const sent = await errorLogger.sendErrorToAdmin(errorData);

    if (sent) {
      res.json({
        success: true,
        message: 'Ошибка успешно зарегистрирована'
      });
    } else {
      res.status(500).json({
        success: false,
        error: 'Не удалось отправить ошибку'
      });
    }

  } catch (error) {
    console.error('❌ Ошибка в API:', error);
    res.status(500).json({
      success: false,
      error: 'Внутренняя ошибка сервера'
    });
  }
});

// Health check эндпоинт
app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    timestamp: new Date().toISOString(),
    service: 'Savolia Error Logger Bot'
  });
});

// Обработка сообщений от пользователей
bot.on('message', async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id.toString();

  // Только админ может взаимодействовать с ботом
  if (userId !== ADMIN_ID) {
    // Не отвечаем ничем другим пользователям
    console.log(`🚫 Неавторизованный доступ от пользователя: ${userId}`);
    return;
  }

  // Команды для админа
  if (msg.text === '/start') {
    await bot.sendMessage(chatId, 
      '🚀 <b>Savolia Error Logger Bot</b>\n\n' +
      '🔍 Этот бот отслеживает ошибки во всех платформах Savolia:\n' +
      '• 🤖 Telegram Bot (bot.ts)\n' +
      '• 📱 Mini App (savolia-frontend)\n' +
      '• 🌐 Web Site (savolia-web)\n\n' +
      '📊 <b>Доступные команды:</b>\n' +
      '/status - Статус бота\n' +
      '/help - Справка\n\n' +
      '🔔 Все ошибки будут автоматически пересылаться сюда.',
      { parse_mode: 'HTML' }
    );
  } else if (msg.text === '/status') {
    await bot.sendMessage(chatId,
      '✅ <b>Статус системы:</b>\n\n' +
      `🤖 Бот: Активен\n` +
      `🌐 API: Работает на порту ${PORT}\n` +
      `🕐 Время работы: ${moment().format('DD.MM.YYYY HH:mm:ss')}\n` +
      `📊 Платформы: ${Object.keys(errorLogger.platforms).length}`,
      { parse_mode: 'HTML' }
    );
  } else if (msg.text === '/help') {
    await bot.sendMessage(chatId,
      '📖 <b>Справка по Error Logger Bot</b>\n\n' +
      '<b>Формат ошибки:</b>\n' +
      '• Платформа (bot.ts/frontend/web)\n' +
      '• Номер пользователя\n' +
      '• Устройство и ОС\n' +
      '• Тип и описание ошибки\n' +
      '• Stack trace\n' +
      '• Время возникновения\n\n' +
      '<b>API Endpoint:</b>\n' +
      '<code>POST /api/log-error</code>\n\n' +
      'Все ошибки автоматически форматируются и отправляются в этот чат.',
      { parse_mode: 'HTML' }
    );
  }
});

// Обработка ошибок бота
bot.on('error', (error) => {
  console.error('❌ Ошибка Telegram бота:', error);
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n🛑 Завершение работы Error Logger Bot...');
  bot.stopPolling();
  process.exit(0);
});

// Запуск сервера
app.listen(PORT, () => {
  console.log(`🌐 API сервер запущен на http://localhost:${PORT}`);
  console.log(`📡 Эндпоинт для ошибок: POST /api/log-error`);
});