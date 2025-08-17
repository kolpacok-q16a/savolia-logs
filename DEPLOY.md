# Инструкция по деплою Savolia Error Logger Bot

## 🚀 Быстрый деплой на Render

1. **Подготовка репозитория:**
   ```bash
   cd /Users/jasur/Downloads/savolia-logs
   git init
   git add .
   git commit -m "Initial commit: Savolia Error Logger Bot"
   git remote add origin YOUR_GITHUB_REPO_URL
   git push -u origin main
   ```

2. **Деплой на Render:**
   - Перейдите на https://render.com
   - Создайте новый Web Service
   - Подключите ваш GitHub репозиторий
   - Настройки:
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python error_logger_bot.py`
     - **Environment:** Python 3

3. **Проверка:**
   - URL бота: `https://YOUR_SERVICE_NAME.onrender.com`
   - Health check: `GET /health`
   - API endpoint: `POST /api/log-error`

## 🔧 Локальное тестирование

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск бота
python error_logger_bot.py
```

## 📱 Интеграция в платформы

### 1. Web Site (savolia-web)
Уже интегрирован в `/public/index.html`. Error Reporter автоматически отправляет ошибки.

### 2. Telegram Bot (bot.ts)
Добавьте в ваш bot.ts:

```typescript
async function reportError(error: Error, userId: string, context: any) {
  try {
    await fetch('https://savolia-error-logger.onrender.com/api/log-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: 'bot.ts',
        userPhone: context.userPhone || 'Telegram User',
        userId: userId,
        errorType: error.name,
        errorMessage: error.message,
        stackTrace: error.stack,
        additionalData: context
      })
    });
  } catch (e) {
    console.error('Failed to report error:', e);
  }
}

// Использование:
try {
  // ваш код
} catch (error) {
  await reportError(error, ctx.from.id, { chatId: ctx.chat.id });
}
```

### 3. Mini App (savolia-frontend)
Добавьте в ваше мини-приложение:

```javascript
// В index.js или main.js
import ErrorReporter from './error-reporter.js';

const errorReporter = new ErrorReporter({
  platform: 'savolia-frontend',
  apiUrl: 'https://savolia-error-logger.onrender.com/api/log-error'
});

// Автоматический перехват ошибок
window.addEventListener('error', (event) => {
  errorReporter.reportError({
    type: 'JavaScript Error',
    message: event.message,
    stack: event.error?.stack
  });
});
```

## ⚙️ Конфигурация

### Переменные окружения (опционально):
- `PORT` - порт для API (по умолчанию 3333)
- `BOT_TOKEN` - уже встроен в код
- `ADMIN_ID` - уже встроен в код

### Безопасность:
- Только админ (ID: 7752180805) может взаимодействовать с ботом
- API открыт для всех платформ Savolia
- Автоматическая валидация входящих данных

## 📊 Мониторинг

### Команды бота:
- `/start` - Информация о боте
- `/status` - Статус системы
- `/help` - Справка

### API endpoints:
- `GET /health` - Проверка статуса
- `POST /api/log-error` - Отправка ошибок

## 🔍 Формат сообщений

Бот автоматически форматирует и отправляет вам:

```
🚨 ОШИБКА В SAVOLIA

📍 Платформа: 🌐 Web Site
📱 Номер пользователя: +998901234567
💻 Устройство: iPhone 15 Pro
⚙️ ОС: iOS 17.2
❌ Тип ошибки: JavaScript Error
🕐 Время: 17.08.2025 14:30:25

🔗 URL: https://savolia.uz/chat

📝 Описание ошибки:
Cannot read property 'length' of undefined

🔍 Stack Trace:
TypeError: Cannot read property 'length' of undefined
    at ChatComponent.sendMessage (chat.js:125:8)
    at HTMLButtonElement.<anonymous> (chat.js:89:12)
```

## ✅ Готово!

После деплоя все ошибки из всех платформ будут автоматически приходить в ваш Telegram.