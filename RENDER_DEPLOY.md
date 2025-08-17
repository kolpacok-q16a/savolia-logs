# 🚀 Деплой на Render

## Быстрый деплой:

1. **Откройте Render.com:**
   - Перейдите на https://render.com
   - Войдите или зарегистрируйтесь

2. **Создайте новый Web Service:**
   - Нажмите "New" → "Web Service"
   - Подключите GitHub: https://github.com/jadev-a11y/savolia-logs
   - Выберите ветку: `main`

3. **Настройки деплоя:**
   ```
   Name: savolia-error-logger
   Region: Oregon (US West)
   Branch: main
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python error_logger_bot.py
   Instance Type: Free
   ```

4. **Переменные окружения (необязательно):**
   ```
   PORT=3333  # Render автоматически установит порт
   ```

5. **Нажмите "Create Web Service"**

## После деплоя:

✅ **URL вашего бота:** `https://savolia-error-logger.onrender.com`

✅ **API endpoint:** `https://savolia-error-logger.onrender.com/api/log-error`

✅ **Health check:** `https://savolia-error-logger.onrender.com/health`

## Обновление URL в веб-сайте:

После деплоя обновите URL в `/Users/jasur/Downloads/savolia-ai/savolia-web/public/index.html`:

```javascript
// Замените в строке 123:
this.apiUrl = 'https://YOUR_DEPLOYED_URL.onrender.com/api/log-error';
```

## Тестирование:

После деплоя запустите тест:
```bash
python test_error.py
# Измените URL в файле на ваш deployed URL
```

## 🎯 Результат:

После успешного деплоя все ошибки из всех платформ Savolia будут автоматически приходить в ваш Telegram!