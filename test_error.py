#!/usr/bin/env python3
"""
Тестирование Error Logger Bot
Отправляет тестовую ошибку для проверки работы системы
"""

import requests
import json
from datetime import datetime

def test_error_logging():
    """Отправка тестовой ошибки"""
    
    # URL API (измените на ваш deployed URL)
    api_url = 'http://localhost:3333/api/log-error'  # Для локального тестирования
    # api_url = 'https://savolia-error-logger.onrender.com/api/log-error'  # Для production
    
    # Тестовые данные ошибки
    test_error = {
        'platform': 'savolia-web',
        'userPhone': '+998901234567',
        'userId': 'test_user_123',
        'errorType': 'Test Error',
        'errorMessage': 'Это тестовая ошибка для проверки работы Error Logger Bot',
        'stackTrace': '''TypeError: Cannot read property 'test' of undefined
    at testFunction (test.js:10:15)
    at HTMLButtonElement.<anonymous> (test.js:5:8)
    at HTMLButtonElement.dispatch (jquery.min.js:2:43064)''',
        'url': 'https://savolia.uz/test',
        'userAgent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'timestamp': datetime.now().isoformat(),
        'additionalData': {
            'testMode': True,
            'component': 'TestComponent',
            'action': 'buttonClick',
            'viewport': {
                'width': 1920,
                'height': 1080
            }
        }
    }
    
    try:
        print('🧪 Отправка тестовой ошибки...')
        print(f'📡 URL: {api_url}')
        print(f'📱 Пользователь: {test_error["userPhone"]}')
        print(f'❌ Тип ошибки: {test_error["errorType"]}')
        
        response = requests.post(
            api_url,
            headers={'Content-Type': 'application/json'},
            json=test_error,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print('✅ Тестовая ошибка успешно отправлена!')
            print(f'📨 Ответ: {result.get("message", "OK")}')
            print('\n🔔 Проверьте Telegram бот - должно прийти уведомление!')
            
        else:
            print(f'❌ Ошибка HTTP {response.status_code}')
            print(f'📄 Ответ: {response.text}')
            
    except requests.exceptions.RequestException as e:
        print(f'❌ Ошибка сети: {e}')
        print('💡 Убедитесь, что бот запущен (python error_logger_bot.py)')
        
    except Exception as e:
        print(f'❌ Неожиданная ошибка: {e}')

def test_health_check():
    """Проверка health endpoint"""
    
    api_url = 'http://localhost:3333/health'  # Для локального тестирования
    # api_url = 'https://savolia-error-logger.onrender.com/health'  # Для production
    
    try:
        print('\n🔍 Проверка health endpoint...')
        response = requests.get(api_url, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            print('✅ Сервис работает!')
            print(f'📊 Статус: {result.get("status")}')
            print(f'🕐 Время: {result.get("timestamp")}')
            print(f'🏷️ Сервис: {result.get("service")}')
        else:
            print(f'❌ Health check failed: HTTP {response.status_code}')
            
    except Exception as e:
        print(f'❌ Health check error: {e}')

if __name__ == '__main__':
    print('🚀 Тестирование Savolia Error Logger Bot\n')
    
    # Проверка health endpoint
    test_health_check()
    
    # Отправка тестовой ошибки
    test_error_logging()
    
    print('\n📋 Что должно произойти:')
    print('1. ✅ Health check должен вернуть статус OK')
    print('2. ✅ API должен принять тестовую ошибку')
    print('3. 📱 В Telegram должно прийти сообщение с тестовой ошибкой')
    print('4. 🤖 Сообщение должно прийти только админу (ID: 7752180805)')
    print('\n🔧 Если что-то не работает:')
    print('- Проверьте, что бот запущен: python error_logger_bot.py')
    print('- Убедитесь, что токен бота правильный')
    print('- Проверьте сетевое соединение')