/**
 * Интеграция Error Logger для Telegram Bot (bot.ts)
 * Автоматическая отправка ошибок в Error Logger Bot
 */

interface ErrorContext {
  userId?: string;
  chatId?: number;
  userPhone?: string;
  username?: string;
  messageText?: string;
  commandName?: string;
  [key: string]: any;
}

interface ErrorData {
  platform: string;
  userPhone?: string;
  userId?: string;
  errorType: string;
  errorMessage: string;
  stackTrace?: string;
  url?: string;
  userAgent?: string;
  timestamp?: string;
  additionalData?: any;
}

class TelegramErrorReporter {
  private apiUrl: string;
  private platform: string;
  private enabled: boolean;

  constructor(config: {
    apiUrl?: string;
    platform?: string;
    enabled?: boolean;
  } = {}) {
    this.apiUrl = config.apiUrl || 'https://savolia-error-logger.onrender.com/api/log-error';
    this.platform = config.platform || 'bot.ts';
    this.enabled = config.enabled ?? true;
    
    console.log('🔍 Telegram Error Reporter инициализирован:', {
      platform: this.platform,
      enabled: this.enabled
    });
  }

  /**
   * Отправка ошибки в Error Logger Bot
   */
  async reportError(
    error: Error | string, 
    context: ErrorContext = {},
    additionalData: any = {}
  ): Promise<boolean> {
    if (!this.enabled) {
      return false;
    }

    try {
      const errorMessage = typeof error === 'string' ? error : error.message;
      const stackTrace = typeof error === 'object' && error.stack ? error.stack : undefined;
      const errorType = typeof error === 'object' && error.name ? error.name : 'Telegram Bot Error';

      const payload: ErrorData = {
        platform: this.platform,
        userPhone: context.userPhone || context.username || `Telegram User ${context.userId}`,
        userId: context.userId?.toString(),
        errorType,
        errorMessage,
        stackTrace,
        timestamp: new Date().toISOString(),
        additionalData: {
          ...additionalData,
          telegramContext: {
            chatId: context.chatId,
            username: context.username,
            messageText: context.messageText?.substring(0, 100), // Обрезаем длинные сообщения
            commandName: context.commandName
          },
          botInfo: {
            platform: 'telegram',
            nodeVersion: process.version,
            environment: process.env.NODE_ENV || 'unknown'
          }
        }
      };

      const response = await fetch(this.apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        console.log('📤 Ошибка отправлена в Error Logger:', errorType);
        return true;
      } else {
        console.error('❌ Не удалось отправить ошибку в Error Logger:', response.status);
        return false;
      }

    } catch (reportingError) {
      console.error('❌ Ошибка при отправке в Error Logger:', reportingError);
      return false;
    }
  }

  /**
   * Wrapper для обработки ошибок с автоматической отправкой
   */
  async handleWithErrorReporting<T>(
    operation: () => Promise<T>,
    context: ErrorContext = {},
    errorHandler?: (error: Error) => void
  ): Promise<T | null> {
    try {
      return await operation();
    } catch (error) {
      // Отправляем ошибку в Error Logger
      await this.reportError(error as Error, context);
      
      // Вызываем кастомный обработчик, если он есть
      if (errorHandler) {
        errorHandler(error as Error);
      }

      return null;
    }
  }

  /**
   * Decorator для методов с автоматической отправкой ошибок
   */
  withErrorReporting(context: ErrorContext = {}) {
    return (target: any, propertyName: string, descriptor: PropertyDescriptor) => {
      const method = descriptor.value;

      descriptor.value = async function (...args: any[]) {
        try {
          return await method.apply(this, args);
        } catch (error) {
          // Отправляем ошибку в Error Logger
          const reporter = new TelegramErrorReporter();
          await reporter.reportError(error as Error, {
            ...context,
            methodName: propertyName,
            className: target.constructor.name
          });

          throw error; // Пробрасываем ошибку дальше
        }
      };
    };
  }

  /**
   * Включение/выключение отправки ошибок
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    console.log(`🔄 Error Reporter ${enabled ? 'включен' : 'выключен'}`);
  }
}

// Глобальный экземпляр для использования в bot.ts
export const telegramErrorReporter = new TelegramErrorReporter();

// Примеры использования:

/**
 * 1. Простая отправка ошибки:
 * 
 * import { telegramErrorReporter } from './telegram-bot-integration';
 * 
 * try {
 *   // ваш код
 * } catch (error) {
 *   await telegramErrorReporter.reportError(error, {
 *     userId: ctx.from.id.toString(),
 *     chatId: ctx.chat.id,
 *     userPhone: ctx.from.phone_number,
 *     username: ctx.from.username,
 *     commandName: 'start'
 *   });
 * }
 */

/**
 * 2. Использование wrapper'а:
 * 
 * const result = await telegramErrorReporter.handleWithErrorReporting(
 *   () => someRiskyOperation(),
 *   { userId: ctx.from.id.toString(), chatId: ctx.chat.id },
 *   (error) => ctx.reply('Произошла ошибка, мы уже работаем над ее исправлением')
 * );
 */

/**
 * 3. Использование как middleware для команд:
 * 
 * bot.command('start', async (ctx) => {
 *   await telegramErrorReporter.handleWithErrorReporting(
 *     async () => {
 *       // логика команды start
 *       await ctx.reply('Добро пожаловать!');
 *     },
 *     {
 *       userId: ctx.from.id.toString(),
 *       chatId: ctx.chat.id,
 *       username: ctx.from.username,
 *       commandName: 'start',
 *       messageText: ctx.message.text
 *     },
 *     (error) => ctx.reply('⚠️ Произошла ошибка. Попробуйте позже.')
 *   );
 * });
 */

/**
 * 4. Decorator для классов:
 * 
 * class BotService {
 *   @telegramErrorReporter.withErrorReporting({ service: 'BotService' })
 *   async processMessage(message: string) {
 *     // ваш код
 *   }
 * }
 */

export default TelegramErrorReporter;