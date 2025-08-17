/**
 * Savolia Error Reporter
 * Автоматическая отправка ошибок в Error Logger Bot
 */

class SavoliaErrorReporter {
  constructor(config = {}) {
    this.config = {
      apiUrl: config.apiUrl || 'https://savolia-error-logger.onrender.com/api/log-error',
      platform: config.platform || 'savolia-web',
      userId: config.userId || null,
      userPhone: config.userPhone || null,
      maxStackLength: config.maxStackLength || 2000,
      enableConsoleLogging: config.enableConsoleLogging ?? true,
      ...config
    };
    
    this.init();
  }

  init() {
    // Перехват глобальных ошибок JavaScript
    window.addEventListener('error', (event) => {
      this.handleError({
        errorType: 'JavaScript Error',
        errorMessage: event.message,
        stackTrace: event.error?.stack,
        url: event.filename,
        lineNumber: event.lineno,
        columnNumber: event.colno,
        additionalData: {
          type: 'window.error',
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno
        }
      });
    });

    // Перехват unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.handleError({
        errorType: 'Unhandled Promise Rejection',
        errorMessage: event.reason?.message || String(event.reason),
        stackTrace: event.reason?.stack,
        additionalData: {
          type: 'unhandledrejection',
          reason: String(event.reason)
        }
      });
    });

    // Перехват ошибок React (если используется)
    if (window.React) {
      this.setupReactErrorBoundary();
    }

    if (this.config.enableConsoleLogging) {
      console.log('🔍 Savolia Error Reporter инициализирован', {
        platform: this.config.platform,
        apiUrl: this.config.apiUrl
      });
    }
  }

  setupReactErrorBoundary() {
    // Перехват console.error для React ошибок
    const originalConsoleError = console.error;
    console.error = (...args) => {
      // Проверяем, является ли это React ошибкой
      const message = args.join(' ');
      if (message.includes('React') || message.includes('component')) {
        this.handleError({
          errorType: 'React Error',
          errorMessage: message,
          additionalData: {
            type: 'react.error',
            args: args
          }
        });
      }
      originalConsoleError.apply(console, args);
    };
  }

  async handleError(errorData) {
    try {
      const payload = {
        platform: this.config.platform,
        userPhone: this.config.userPhone,
        userId: this.config.userId,
        errorType: errorData.errorType,
        errorMessage: errorData.errorMessage,
        stackTrace: this.truncateStack(errorData.stackTrace),
        url: errorData.url || window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        additionalData: {
          ...errorData.additionalData,
          viewport: {
            width: window.innerWidth,
            height: window.innerHeight
          },
          screen: {
            width: screen.width,
            height: screen.height
          },
          referrer: document.referrer,
          title: document.title
        }
      };

      // Отправляем ошибку
      await this.sendError(payload);

      if (this.config.enableConsoleLogging) {
        console.log('📤 Ошибка отправлена в Error Logger:', errorData.errorType);
      }

    } catch (error) {
      if (this.config.enableConsoleLogging) {
        console.error('❌ Не удалось отправить ошибку в Error Logger:', error);
      }
    }
  }

  truncateStack(stack) {
    if (!stack) return null;
    return stack.length > this.config.maxStackLength 
      ? stack.substring(0, this.config.maxStackLength) + '\n[Обрезано...]'
      : stack;
  }

  async sendError(payload) {
    const response = await fetch(this.config.apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  // Ручная отправка ошибки
  reportError(errorData) {
    this.handleError({
      errorType: errorData.type || 'Manual Error',
      errorMessage: errorData.message,
      stackTrace: errorData.stack,
      additionalData: {
        type: 'manual',
        ...errorData.additionalData
      }
    });
  }

  // Обновление пользовательских данных
  updateUser(userData) {
    if (userData.userId) this.config.userId = userData.userId;
    if (userData.userPhone) this.config.userPhone = userData.userPhone;
  }

  // Отправка информации о производительности
  reportPerformance() {
    if (!window.performance) return;

    const navigation = performance.getEntriesByType('navigation')[0];
    if (navigation) {
      this.handleError({
        errorType: 'Performance Report',
        errorMessage: 'Медленная загрузка страницы',
        additionalData: {
          type: 'performance',
          loadTime: navigation.loadEventEnd - navigation.loadEventStart,
          domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
          firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime,
          firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime
        }
      });
    }
  }
}

// Автоматическая инициализация для веб-сайта
if (typeof window !== 'undefined') {
  window.SavoliaErrorReporter = SavoliaErrorReporter;
  
  // Автоинициализация с базовыми настройками
  window.addEventListener('DOMContentLoaded', () => {
    if (!window.savoliaErrorReporter) {
      window.savoliaErrorReporter = new SavoliaErrorReporter({
        platform: 'savolia-web'
      });
    }
  });
}

// Экспорт для Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SavoliaErrorReporter;
}