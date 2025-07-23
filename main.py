import asyncio
import json
import logging
import os
import random
from datetime import datetime, time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

import aiohttp
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# Конфигурация логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WORDS_FILE = 'words_cefr.json'
TRANSLATION_TIMEOUT = 10  # секунд
MAX_WORDS_PER_REQUEST = 10

@dataclass
class UserData:
    """Класс для хранения данных пользователя"""
    level: Optional[str] = None
    learned_words: Set[str] = field(default_factory=set)
    daily_words: List[Dict] = field(default_factory=list)
    last_daily_update: Optional[datetime] = None

# Хранение данных пользователей в памяти
user_data: Dict[int, UserData] = {}

class EnglishLearningBot:
    """Основной класс бота для изучения английского"""
    
    def __init__(self, words_file: str = WORDS_FILE):
        self.moscow_tz = pytz.timezone('Europe/Moscow')
        self.level_word_bank = self._load_word_bank(words_file)
        self.session: Optional[aiohttp.ClientSession] = None

    def _load_word_bank(self, words_file: str) -> Dict[str, List[str]]:
        """Загрузка словаря из файла с обработкой ошибок"""
        try:
            with open(words_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл {words_file} не найден")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в файле {words_file}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке {words_file}: {e}")
            return {}

    async def get_session(self) -> aiohttp.ClientSession:
        """Получение или создание HTTP сессии"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=TRANSLATION_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close_session(self):
        """Закрытие HTTP сессии"""
        if self.session and not self.session.closed:
            await self.session.close()

    def get_user_data(self, user_id: int) -> UserData:
        """Получить данные пользователя"""
        if user_id not in user_data:
            user_data[user_id] = UserData()
        return user_data[user_id]

    async def fetch_words_by_level(self, level: str, count: int = 5) -> List[Dict]:
        """
        Получение слов из локального JSON-словаря с переводом
        
        Args:
            level: Уровень CEFR (A1, A2, B1, B2, C1, C2)
            count: Количество слов для получения
            
        Returns:
            Список словарей с информацией о словах
        """
        count = min(count, MAX_WORDS_PER_REQUEST)
        
        try:
            word_list = self.level_word_bank.get(level.upper(), [])
            if not word_list:
                logger.warning(f"Слова для уровня {level} не найдены")
                return await self._get_fallback_words(level, count)

            # Перемешиваем и выбираем нужное количество
            selected_words = random.sample(word_list, min(count, len(word_list)))

            words = []
            for word in selected_words:
                translation = await self.translate_text(word, 'ru')
                words.append({
                    'word': word,
                    'definition': "-",
                    'translation': translation
                })
            return words
            
        except Exception as e:
            logger.error(f"Ошибка загрузки слов для уровня {level}: {e}")
            return await self._get_fallback_words(level, count)

    async def translate_text(self, text: str, target_lang: str = 'ru') -> str:
        """
        Перевод текста через MyMemory Translation API
        
        Args:
            text: Текст для перевода
            target_lang: Целевой язык ('ru' или 'en')
            
        Returns:
            Переведенный текст
        """
        if not text or not text.strip():
            return "Пустой текст"

        try:
            session = await self.get_session()
            url = "https://api.mymemory.translated.net/get"
            params = {
                'q': text.strip(),
                'langpair': f'en|{target_lang}' if target_lang == 'ru' else f'ru|en'
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    translated = data.get('responseData', {}).get('translatedText', '')
                    return translated if translated else f"Перевод для '{text}' недоступен"
                else:
                    logger.warning(f"API вернул статус {response.status} для текста '{text}'")
                    
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при переводе текста '{text}'")
        except Exception as e:
            logger.error(f"Ошибка при переводе '{text}': {e}")

        return f"Перевод для '{text}' недоступен"

    async def _get_fallback_words(self, level: str, count: int) -> List[Dict]:
        """Резервные слова если основной источник недоступен"""
        fallback_words_by_level = {
            'A1': [
                {'word': 'cat', 'definition': 'a small domesticated carnivorous mammal', 'translation': 'кот'},
                {'word': 'dog', 'definition': 'a domesticated carnivorous mammal', 'translation': 'собака'},
                {'word': 'house', 'definition': 'a building for human habitation', 'translation': 'дом'},
                {'word': 'car', 'definition': 'a road vehicle powered by a motor', 'translation': 'машина'},
                {'word': 'book', 'definition': 'a written or printed work consisting of pages', 'translation': 'книга'},
                {'word': 'water', 'definition': 'a colorless, transparent, odorless liquid', 'translation': 'вода'},
                {'word': 'food', 'definition': 'any nutritious substance that people eat', 'translation': 'еда'},
                {'word': 'table', 'definition': 'a piece of furniture with a flat top', 'translation': 'стол'},
                {'word': 'chair', 'definition': 'a separate seat for one person', 'translation': 'стул'},
                {'word': 'window', 'definition': 'an opening in a wall fitted with glass', 'translation': 'окно'}
            ],
            'A2': [
                {'word': 'school', 'definition': 'an institution for learning', 'translation': 'школа'},
                {'word': 'friend', 'definition': 'a person you like and know well', 'translation': 'друг'},
                {'word': 'family', 'definition': 'a group of related people', 'translation': 'семья'},
                {'word': 'work', 'definition': 'activity involving effort', 'translation': 'работа'},
                {'word': 'money', 'definition': 'medium of exchange', 'translation': 'деньги'}
            ]
        }

        # Используем слова A1 для всех уровней, если конкретный уровень не найден
        base_words = fallback_words_by_level.get(level, fallback_words_by_level['A1'])
        return random.sample(base_words, min(count, len(base_words)))

    def format_words_text(self, words: List[Dict], level: str, title: str = "слова") -> str:
        """Форматирование текста со словами"""
        if not words:
            return f"📚 {title} ({level}): список пуст\n\n"
            
        words_text = f"📚 Ваши {title} ({level}):\n\n"
        for i, word_info in enumerate(words, 1):
            word = word_info.get('word', 'неизвестно')
            translation = word_info.get('translation', 'нет перевода')
            words_text += f"{i}. **{word}** → {translation}\n"
        return words_text

    def _detect_language(self, text: str) -> str:
        """Определение языка текста (простое определение по наличию кириллицы)"""
        return 'ru' if any(ord(char) > 127 for char in text) else 'en'

# Инициализация бота
bot = EnglishLearningBot()

def create_level_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры выбора уровня"""
    keyboard = [
        [InlineKeyboardButton("A1 (Beginner)", callback_data="level_A1")],
        [InlineKeyboardButton("A2 (Elementary)", callback_data="level_A2")],
        [InlineKeyboardButton("B1 (Intermediate)", callback_data="level_B1")],
        [InlineKeyboardButton("B2 (Upper-Intermediate)", callback_data="level_B2")],
        [InlineKeyboardButton("C1 (Advanced)", callback_data="level_C1")],
        [InlineKeyboardButton("C2 (Proficiency)", callback_data="level_C2")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_main_keyboard() -> InlineKeyboardMarkup:
    """Создание основной клавиатуры управления"""
    keyboard = [
        [InlineKeyboardButton("🔄 Получить еще слова", callback_data="more_words")],
        [InlineKeyboardButton("💬 Перевести слово", callback_data="translate_mode")],
        [InlineKeyboardButton("📊 Изменить уровень", callback_data="change_level")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_text = """🎓 Добро пожаловать в English Learning Bot!

Выберите ваш уровень английского языка:

• A1-A2: Начинающий
• B1-B2: Средний  
• C1-C2: Продвинутый

Бот будет отправлять вам слова каждый день в 10:00 по московскому времени!
К каждому слову добавляется русский перевод! 🌟

📚 Доступные команды:
/start - начать работу
/translate - перевести слово
/more - получить дополнительные слова
/level - изменить уровень
/stats - статистика изучения
/test_daily - тест ежедневной отправки"""

    await update.message.reply_text(welcome_text, reply_markup=create_level_keyboard())

async def handle_level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора уровня"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    level = query.data.replace("level_", "")
    
    user_info = bot.get_user_data(user_id)
    user_info.level = level
    
    # Показываем индикатор загрузки
    await query.edit_message_text("⏳ Загружаю слова с переводами...")
    
    try:
        # Загружаем первые слова
        words = await bot.fetch_words_by_level(level, 5)
        user_info.daily_words = words
        user_info.last_daily_update = datetime.now(bot.moscow_tz).date()
        
        words_text = f"✅ Уровень {level} установлен!\n\n"
        words_text += bot.format_words_text(words, level, "слова на сегодня")
        
        await query.edit_message_text(
            words_text, 
            parse_mode='Markdown', 
            reply_markup=create_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при установке уровня для пользователя {user_id}: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при загрузке слов. Попробуйте еще раз.",
            reply_markup=create_level_keyboard()
        )

async def handle_more_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить дополнительные слова"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = bot.get_user_data(user_id)
    
    if not user_info.level:
        await query.edit_message_text("❌ Сначала выберите уровень командой /start")
        return
    
    # Показываем индикатор загрузки
    await query.edit_message_text("⏳ Загружаю новые слова с переводами...")
    
    try:
        # Отмечаем текущие слова как изученные
        for word_info in user_info.daily_words:
            if 'word' in word_info:
                user_info.learned_words.add(word_info['word'])
        
        # Загружаем новые слова
        new_words = await bot.fetch_words_by_level(user_info.level, 5)
        
        # Фильтруем уже изученные слова
        filtered_words = [w for w in new_words if w.get('word') not in user_info.learned_words]
        
        if not filtered_words:
            # Если все слова уже изучены, берем любые
            filtered_words = new_words
        
        user_info.daily_words = filtered_words
        
        words_text = "🆕 " + bot.format_words_text(
            filtered_words, user_info.level, "новые слова"
        )
        words_text += f"\n📈 Изучено слов: {len(user_info.learned_words)}"
        
        await query.edit_message_text(
            words_text, 
            parse_mode='Markdown', 
            reply_markup=create_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении новых слов для пользователя {user_id}: {e}")
        await query.edit_message_text("❌ Ошибка при загрузке новых слов. Попробуйте позже.")

async def handle_translate_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Режим перевода"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("🔙 Назад к словам", callback_data="back_to_words")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💬 Режим перевода активирован!\n\n"
        "Напишите слово на английском или русском языке, и я переведу его.\n\n"
        "Например: cat или кот",
        reply_markup=reply_markup
    )

async def handle_back_to_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к словам"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = bot.get_user_data(user_id)
    
    if not user_info.daily_words:
        await query.edit_message_text("❌ Сначала выберите уровень командой /start")
        return
    
    words_text = bot.format_words_text(user_info.daily_words, user_info.level, "текущие слова")
    
    await query.edit_message_text(
        words_text, 
        parse_mode='Markdown', 
        reply_markup=create_main_keyboard()
    )

async def handle_change_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить уровень"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📊 Выберите новый уровень английского языка:",
        reply_markup=create_level_keyboard()
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (для перевода)"""
    if not update.message or not update.message.text:
        return
        
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ Пустое сообщение")
        return
    
    try:
        # Определяем язык и переводим
        source_lang = bot._detect_language(text)
        target_lang = 'en' if source_lang == 'ru' else 'ru'
        
        translation = await bot.translate_text(text, target_lang)
        
        await update.message.reply_text(
            f"🔄 **{text}** → {translation}", 
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка при переводе текста '{text}': {e}")
        await update.message.reply_text("❌ Ошибка при переводе. Попробуйте позже.")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /translate"""
    await update.message.reply_text(
        "💬 Напишите слово на английском или русском языке для перевода.\n\n"
        "Например: cat или кот"
    )

async def more_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /more"""
    user_id = update.message.from_user.id
    user_info = bot.get_user_data(user_id)
    
    if not user_info.level:
        await update.message.reply_text("❌ Сначала выберите уровень командой /start")
        return
    
    try:
        # Показываем индикатор загрузки
        loading_msg = await update.message.reply_text("⏳ Загружаю новые слова с переводами...")
        
        # Отмечаем текущие слова как изученные
        for word_info in user_info.daily_words:
            if 'word' in word_info:
                user_info.learned_words.add(word_info['word'])
        
        # Загружаем новые слова
        new_words = await bot.fetch_words_by_level(user_info.level, 5)
        user_info.daily_words = new_words
        
        words_text = "🆕 " + bot.format_words_text(
            new_words, user_info.level, "новые слова"
        )
        words_text += f"\n📈 Изучено слов: {len(user_info.learned_words)}"
        
        await loading_msg.edit_text(words_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в команде /more для пользователя {user_id}: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке слов. Попробуйте позже.")

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /level"""
    await update.message.reply_text(
        "📊 Выберите ваш уровень английского языка:",
        reply_markup=create_level_keyboard()
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - показать статистику"""
    user_id = update.message.from_user.id
    user_info = bot.get_user_data(user_id)
    
    if not user_info.level:
        await update.message.reply_text("❌ Сначала выберите уровень командой /start")
        return
    
    stats_text = f"""📊 **Ваша статистика:**

🎯 Текущий уровень: {user_info.level}
📚 Изучено слов: {len(user_info.learned_words)}
📅 Последнее обновление: {user_info.last_daily_update or 'никогда'}
🔤 Слов на сегодня: {len(user_info.daily_words)}
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def test_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /test_daily для тестирования ежедневных слов"""
    user_id = update.message.from_user.id
    user_info = bot.get_user_data(user_id)
    
    if not user_info.level:
        await update.message.reply_text("❌ Сначала выберите уровень командой /start")
        return
    
    try:
        # Показываем индикатор загрузки
        loading_msg = await update.message.reply_text("⏳ Тест загрузки: получаю слова с переводами...")
        
        # Принудительно загружаем новые слова
        new_words = await bot.fetch_words_by_level(user_info.level, 5)
        user_info.daily_words = new_words
        user_info.last_daily_update = datetime.now(bot.moscow_tz).date()
        
        words_text = "🧪 ТЕСТ: " + bot.format_words_text(
            new_words, user_info.level, "ваши слова на сегодня"
        )
        words_text += "\nЭто тест ежедневной отправки! 📚"
        
        await loading_msg.edit_text(words_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в тестовой команде для пользователя {user_id}: {e}")
        await update.message.reply_text("❌ Ошибка при тестировании. Попробуйте позже.")

async def daily_words_job(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная отправка слов в 10:00 по Москве"""
    try:
        today = datetime.now(bot.moscow_tz).date()
        
        for user_id, user_info in user_data.items():
            try:
                if not user_info.level:
                    continue
                    
                # Проверяем, нужно ли обновить слова на сегодня
                if user_info.last_daily_update != today:
                    # Загружаем новые слова
                    new_words = await bot.fetch_words_by_level(user_info.level, 5)
                    user_info.daily_words = new_words
                    user_info.last_daily_update = today
                
                # Формируем сообщение
                words_text = "🌅 Доброе утро! " + bot.format_words_text(
                    user_info.daily_words, user_info.level, "ваши слова на сегодня"
                )
                words_text += "\nУдачного изучения! 📚"
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=words_text,
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка в ежедневной задаче: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик глобальных ошибок"""
    logger.error(f"Необработанная ошибка: {context.error}")
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Произошла неожиданная ошибка. Попробуйте позже или обратитесь к администратору."
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")

def main():
    """Запуск бота"""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    try:
        # Создание приложения
        application = Application.builder().token(TOKEN).build()
        
        # Регистрация обработчиков команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("translate", translate_command))
        application.add_handler(CommandHandler("more", more_command))
        application.add_handler(CommandHandler("level", level_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("test_daily", test_daily_command))
        
        # Обработчики callback-кнопок
        application.add_handler(CallbackQueryHandler(handle_level_selection, pattern="^level_"))
        application.add_handler(CallbackQueryHandler(handle_more_words, pattern="^more_words$"))
        application.add_handler(CallbackQueryHandler(handle_translate_mode, pattern="^translate_mode$"))
        application.add_handler(CallbackQueryHandler(handle_back_to_words, pattern="^back_to_words$"))
        application.add_handler(CallbackQueryHandler(handle_change_level, pattern="^change_level$"))
        
        # Обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Настройка ежедневной задачи (10:00 по Москве = 07:00 UTC)
        try:
            job_queue = application.job_queue
            if job_queue:
                job_queue.run_daily(
                    daily_words_job,
                    time=time(hour=7, minute=0),  # 10:00 МСК = 07:00 UTC
                    days=(0, 1, 2, 3, 4, 5, 6)   # Каждый день
                )
                logger.info("Ежедневная задача настроена на 10:00 МСК")
            else:
                logger.warning("JobQueue недоступна - ежедневные уведомления отключены")
        except Exception as e:
            logger.error(f"Ошибка настройки JobQueue: {e}")
            logger.info("Бот продолжит работу без автоматических уведомлений")
        
        # Запуск бота
        logger.info("Бот запущен!")
        application.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        raise
    finally:
        # Закрытие ресурсов
        asyncio.run(bot.close_session())

if __name__ == '__main__':
    main()
