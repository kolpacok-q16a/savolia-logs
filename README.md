# Savolia Error Logger Bot

Бот для автоматического логирования и оповещения об ошибках во всех платформах Savolia.

## Функции

- 🤖 Получение ошибок от Telegram Bot (bot.ts)
- 📱 Получение ошибок от Mini App (savolia-frontend)  
- 🌐 Получение ошибок от Web Site (savolia-web)
- 📊 Автоматический парсинг информации об устройстве
- 🔔 Мгновенное уведомление админа в Telegram
- 🛡️ Безопасность - только админ получает сообщения

## Формат ошибки

Бот отправляет админу детальную информацию:
- Платформа (bot.ts/frontend/web)
- Номер пользователя
- Устройство и ОС (автоопределение)
- Тип и описание ошибки
- Stack trace
- Время возникновения
- URL (если применимо)
- User Agent
- Дополнительные данные

## API

### POST /api/log-error

Отправка ошибки в бот:

```json
{
  "platform": "savolia-web",
  "userPhone": "+998901234567",
  "userId": "user123",
  "errorType": "JavaScript Error",
  "errorMessage": "Cannot read property 'length' of undefined",
  "stackTrace": "Error: Cannot read property...",
  "url": "https://savolia.uz/chat",
  "userAgent": "Mozilla/5.0...",
  "additionalData": {
    "component": "ChatComponent",
    "action": "sendMessage"
  }
}
```

### GET /health

Проверка статуса сервиса.

## Развертывание

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите бота:
```bash
python error_logger_bot.py
```

## Docker

```bash
docker build -t savolia-error-logger .
docker run -p 3333:3333 savolia-error-logger
```

## Команды бота

- `/start` - Приветствие и информация
- `/status` - Статус системы
- `/help` - Справка

## Безопасность

- Только админ (ID: 7752180805) может взаимодействовать с ботом
- Другие пользователи не получают никакого ответа
- API защищен от злоупотреблений

## Интеграция

Для интеграции в ваши проекты используйте API endpoint `/api/log-error` для отправки ошибок.