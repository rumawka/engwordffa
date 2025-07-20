import asyncio
import json
import logging
import os
import random
from datetime import datetime, time
from typing import Dict, List, Optional

import aiohttp
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WORDS_API_KEY = os.getenv('WORDS_API_KEY')  # RapidAPI ключ для WordsAPI
TRANSLATE_API_KEY = os.getenv('TRANSLATE_API_KEY')  # Yandex Translate API ключ

# Хранение данных пользователей в памяти
user_data: Dict[int, Dict] = {}

class EnglishLearningBot:
    def __init__(self):
        self.moscow_tz = pytz.timezone('Europe/Moscow')
        
    def get_user_data(self, user_id: int) -> Dict:
        """Получить данные пользователя"""
        if user_id not in user_data:
            user_data[user_id] = {
                'level': None,
                'learned_words': set(),
                'daily_words': [],
                'last_daily_update': None
            }
        return user_data[user_id]
    
    async def fetch_words_by_level(self, level: str, count: int = 10) -> List[Dict]:
        """Получение слов с WordsAPI по уровню сложности"""
        try:
            headers = {
                'X-RapidAPI-Key': WORDS_API_KEY,
                'X-RapidAPI-Host': 'wordsapiv1.p.rapidapi.com'
            }
            
            # Параметры поиска слов по уровням
            level_params = {
                'A1': {'frequencyMin': 7, 'frequencyMax': 7, 'letterPattern': '[a-z]{3,6}'},
                'A2': {'frequencyMin': 6, 'frequencyMax': 7, 'letterPattern': '[a-z]{4,7}'},
                'B1': {'frequencyMin': 5, 'frequencyMax': 6, 'letterPattern': '[a-z]{5,8}'},
                'B2': {'frequencyMin': 4, 'frequencyMax': 5, 'letterPattern': '[a-z]{6,9}'},
                'C1': {'frequencyMin': 3, 'frequencyMax': 4, 'letterPattern': '[a-z]{7,10}'},
                'C2': {'frequencyMin': 1, 'frequencyMax': 3, 'letterPattern': '[a-z]{8,12}'}
            }
            
            words = []
            params = level_params.get(level, level_params['A1'])
            
            async with aiohttp.ClientSession() as session:
                # Получаем случайные слова
                for _ in range(count * 2):  # Берем больше для фильтрации
                    try:
                        url = "https://wordsapiv1.p.rapidapi.com/words/"
                        async with session.get(
                            url,
                            headers=headers,
                            params={
                                'random': 'true',
                                'frequencyMin': params['frequencyMin'],
                                'frequencyMax': params['frequencyMax']
                            }
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                word = data.get('word', '').lower()
                                
                                if word and len(word) >= 3:
                                    # Получаем определение слова
                                    definition = await self.get_word_definition(word, session, headers)
                                    if definition:
                                        # Получаем перевод слова
                                        translation = await self.translate_text(word, 'ru')
                                        
                                        words.append({
                                            'word': word,
                                            'definition': definition,
                                            'translation': translation
                                        })
                                        
                                        if len(words) >= count:
                                            break
                                            
                    except Exception as e:
                        logger.error(f"Ошибка получения слова: {e}")
                        continue
                        
            return words[:count] if words else await self.get_fallback_words(level, count)
            
        except Exception as e:
            logger.error(f"Ошибка API слов: {e}")
            return await self.get_fallback_words(level, count)
    
    async def get_word_definition(self, word: str, session: aiohttp.ClientSession, headers: Dict) -> Optional[str]:
        """Получить определение слова"""
        try:
            url = f"https://wordsapiv1.p.rapidapi.com/words/{word}/definitions"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    definitions = data.get('definitions', [])
                    if definitions:
                        return definitions[0].get('definition', '')
        except:
            pass
        return None
    
    async def get_fallback_words(self, level: str, count: int) -> List[Dict]:
        """Резервные слова если API недоступно"""
        fallback_words = {
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
                {'word': 'beautiful', 'definition': 'pleasing the senses or mind aesthetically', 'translation': 'красивый'},
                {'word': 'important', 'definition': 'of great significance or value', 'translation': 'важный'},
                {'word': 'different', 'definition': 'not the same as another', 'translation': 'разный'},
                {'word': 'interesting', 'definition': 'arousing curiosity or interest', 'translation': 'интересный'},
                {'word': 'difficult', 'definition': 'needing much effort to accomplish', 'translation': 'сложный'},
                {'word': 'comfortable', 'definition': 'providing physical ease and relaxation', 'translation': 'удобный'},
                {'word': 'expensive', 'definition': 'costing a lot of money', 'translation': 'дорогой'},
                {'word': 'dangerous', 'definition': 'able or likely to cause harm', 'translation': 'опасный'},
                {'word': 'wonderful', 'definition': 'inspiring delight, pleasure, or admiration', 'translation': 'чудесный'},
                {'word': 'terrible', 'definition': 'extremely bad or serious', 'translation': 'ужасный'}
            ]
        }
        
        # Добавляем слова для остальных уровней
        fallback_words['B1'] = fallback_words['A2']  # Упрощенно
        fallback_words['B2'] = fallback_words['A2']
        fallback_words['C1'] = fallback_words['A2']
        fallback_words['C2'] = fallback_words['A2']
        
        words = fallback_words.get(level, fallback_words['A1'])
        return random.sample(words, min(count, len(words)))
    
      	    async def translate_text(self, text: str, target_lang: str = 'ru') -> str:
        """Перевод текста через LibreTranslate (бесплатный, без ключа)"""
        try:
            url = "https://libretranslate.com/translate"
            headers = {'Content-Type': 'application/json'}
            payload = {
                'q': text,
                'source': 'en' if target_lang == 'ru' else 'ru',
                'target': target_lang,
                'format': 'text'
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('translatedText', '')
                    else:
                        logger.error(f"Ошибка LibreTranslate: статус {response.status}")
        except Exception as e:
            logger.error(f"Ошибка LibreTranslate: {e}")

        # Резервный перевод
        simple_translations = {
            'hello': 'привет', 'cat': 'кот', 'dog': 'собака', 'house': 'дом',
            'car': 'машина', 'book': 'книга', 'water': 'вода', 'food': 'еда',
            'table': 'стол', 'chair': 'стул', 'window': 'окно', 'beautiful': 'красивый',
            'important': 'важный', 'different': 'разный', 'interesting': 'интересный',
            'difficult': 'сложный', 'comfortable': 'удобный', 'expensive': 'дорогой',
            'dangerous': 'опасный', 'wonderful': 'чудесный', 'terrible': 'ужасный',
            'привет': 'hello', 'кот': 'cat', 'собака': 'dog', 'дом': 'house'
        }
        return simple_translations.get(text.lower(), f"Перевод для '{text}' недоступен")

    def format_words_text(self, words: List[Dict], level: str, title: str = "слова") -> str:
        """Форматирование текста со словами с переводами"""
        words_text = f"📚 Ваши {title} ({level}):\n\n"
        for i, word_info in enumerate(words, 1):
            translation = word_info.get('translation', 'нет перевода')
            words_text += f"{i}. **{word_info['word']}** ({translation})\n"
            words_text += f"   📖 {word_info['definition']}\n\n"
        return words_text

# Инициализация бота
bot = EnglishLearningBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [InlineKeyboardButton("A1 (Beginner)", callback_data="level_A1")],
        [InlineKeyboardButton("A2 (Elementary)", callback_data="level_A2")],
        [InlineKeyboardButton("B1 (Intermediate)", callback_data="level_B1")],
        [InlineKeyboardButton("B2 (Upper-Intermediate)", callback_data="level_B2")],
        [InlineKeyboardButton("C1 (Advanced)", callback_data="level_C1")],
        [InlineKeyboardButton("C2 (Proficiency)", callback_data="level_C2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """🎓 Добро пожаловать в English Learning Bot!

Выберите ваш уровень английского языка:

• A1-A2: Начинающий
• B1-B2: Средний  
• C1-C2: Продвинутый

Бот будет отправлять вам слова каждый день в 10:00 по московскому времени!
Теперь к каждому слову добавляется русский перевод! 🌟

📚 Доступные команды:
/start - начать работу
/translate - перевести слово
/more - получить дополнительные слова
/level - изменить уровень
/test_daily - тест ежедневной отправки"""

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора уровня"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    level = query.data.replace("level_", "")
    
    user_info = bot.get_user_data(user_id)
    user_info['level'] = level
    
    # Показываем индикатор загрузки
    await query.edit_message_text("⏳ Загружаю слова с переводами...")
    
    # Загружаем первые слова
    words = await bot.fetch_words_by_level(level, 5)
    user_info['daily_words'] = words
    user_info['last_daily_update'] = datetime.now(bot.moscow_tz).date()
    
    # Создаем клавиатуру для управления
    keyboard = [
        [InlineKeyboardButton("🔄 Получить еще слова", callback_data="more_words")],
        [InlineKeyboardButton("💬 Перевести слово", callback_data="translate_mode")],
        [InlineKeyboardButton("📊 Изменить уровень", callback_data="change_level")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    words_text = f"✅ Уровень {level} установлен!\n\n"
    words_text += bot.format_words_text(words, level, "слова на сегодня")
    
    await query.edit_message_text(words_text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_more_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить дополнительные слова"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = bot.get_user_data(user_id)
    
    if not user_info['level']:
        await query.edit_message_text("❌ Сначала выберите уровень командой /start")
        return
    
    # Показываем индикатор загрузки
    await query.edit_message_text("⏳ Загружаю новые слова с переводами...")
    
    # Отмечаем текущие слова как изученные
    for word_info in user_info['daily_words']:
        user_info['learned_words'].add(word_info['word'])
    
    # Загружаем новые слова
    new_words = await bot.fetch_words_by_level(user_info['level'], 5)
    # Фильтруем уже изученные слова
    new_words = [w for w in new_words if w['word'] not in user_info['learned_words']]
    
    if not new_words:
        new_words = await bot.fetch_words_by_level(user_info['level'], 5)
    
    user_info['daily_words'] = new_words
    
    keyboard = [
        [InlineKeyboardButton("🔄 Получить еще слова", callback_data="more_words")],
        [InlineKeyboardButton("💬 Перевести слово", callback_data="translate_mode")],
        [InlineKeyboardButton("📊 Изменить уровень", callback_data="change_level")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    words_text = f"🆕 "
    words_text += bot.format_words_text(new_words, user_info['level'], "новые слова")
    words_text += f"📈 Изучено слов: {len(user_info['learned_words'])}"
    
    await query.edit_message_text(words_text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_translate_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Режим перевода"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад к словам", callback_data="back_to_words")]
    ]
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
    
    if not user_info['daily_words']:
        await query.edit_message_text("❌ Сначала выберите уровень командой /start")
        return
    
    keyboard = [
        [InlineKeyboardButton("🔄 Получить еще слова", callback_data="more_words")],
        [InlineKeyboardButton("💬 Перевести слово", callback_data="translate_mode")],
        [InlineKeyboardButton("📊 Изменить уровень", callback_data="change_level")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    words_text = bot.format_words_text(user_info['daily_words'], user_info['level'], "текущие слова")
    
    await query.edit_message_text(words_text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_change_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить уровень"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("A1 (Beginner)", callback_data="level_A1")],
        [InlineKeyboardButton("A2 (Elementary)", callback_data="level_A2")],
        [InlineKeyboardButton("B1 (Intermediate)", callback_data="level_B1")],
        [InlineKeyboardButton("B2 (Upper-Intermediate)", callback_data="level_B2")],
        [InlineKeyboardButton("C1 (Advanced)", callback_data="level_C1")],
        [InlineKeyboardButton("C2 (Proficiency)", callback_data="level_C2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 Выберите новый уровень английского языка:",
        reply_markup=reply_markup
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (для перевода)"""
    text = update.message.text
    user_id = update.message.from_user.id
    
    # Определяем язык и переводим
    if any(ord(char) > 127 for char in text):  # Содержит кириллицу
        translation = await bot.translate_text(text, 'en')
        await update.message.reply_text(f"🔄 **{text}** → {translation}", parse_mode='Markdown')
    else:  # Английский текст
        translation = await bot.translate_text(text, 'ru')
        await update.message.reply_text(f"🔄 **{text}** → {translation}", parse_mode='Markdown')

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
    
    if not user_info['level']:
        await update.message.reply_text("❌ Сначала выберите уровень командой /start")
        return
    
    # Показываем индикатор загрузки
    loading_msg = await update.message.reply_text("⏳ Загружаю новые слова с переводами...")
    
    # Отмечаем текущие слова как изученные
    for word_info in user_info['daily_words']:
        user_info['learned_words'].add(word_info['word'])
    
    # Загружаем новые слова
    new_words = await bot.fetch_words_by_level(user_info['level'], 5)
    user_info['daily_words'] = new_words
    
    words_text = f"🆕 "
    words_text += bot.format_words_text(new_words, user_info['level'], "новые слова")
    words_text += f"📈 Изучено слов: {len(user_info['learned_words'])}"
    
    await loading_msg.edit_text(words_text, parse_mode='Markdown')

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /level"""
    keyboard = [
        [InlineKeyboardButton("A1 (Beginner)", callback_data="level_A1")],
        [InlineKeyboardButton("A2 (Elementary)", callback_data="level_A2")],
        [InlineKeyboardButton("B1 (Intermediate)", callback_data="level_B1")],
        [InlineKeyboardButton("B2 (Upper-Intermediate)", callback_data="level_B2")],
        [InlineKeyboardButton("C1 (Advanced)", callback_data="level_C1")],
        [InlineKeyboardButton("C2 (Proficiency)", callback_data="level_C2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 Выберите ваш уровень английского языка:",
        reply_markup=reply_markup
    )

async def test_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /test_daily для тестирования ежедневных слов"""
    user_id = update.message.from_user.id
    user_info = bot.get_user_data(user_id)
    
    if not user_info['level']:
        await update.message.reply_text("❌ Сначала выберите уровень командой /start")
        return
    
    # Показываем индикатор загрузки
    loading_msg = await update.message.reply_text("⏳ Тест загрузки: получаю слова с переводами...")
    
    # Принудительно загружаем новые слова
    new_words = await bot.fetch_words_by_level(user_info['level'], 5)
    user_info['daily_words'] = new_words
    user_info['last_daily_update'] = datetime.now(bot.moscow_tz).date()
    
    words_text = f"🧪 ТЕСТ: "
    words_text += bot.format_words_text(new_words, user_info['level'], "ваши слова на сегодня")
    words_text += "Это тест ежедневной отправки! 📚"
    
    await loading_msg.edit_text(words_text, parse_mode='Markdown')

async def daily_words_job(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная отправка слов в 10:00 по Москве"""
    try:
        for user_id, user_info in user_data.items():
            if user_info['level'] and user_info.get('daily_words'):
                # Проверяем, нужно ли обновить слова на сегодня
                today = datetime.now(bot.moscow_tz).date()
                if user_info['last_daily_update'] != today:
                    # Загружаем новые слова
                    new_words = await bot.fetch_words_by_level(user_info['level'], 5)
                    user_info['daily_words'] = new_words
                    user_info['last_daily_update'] = today
                
                # Формируем сообщение
                words_text = f"🌅 Доброе утро! "
                words_text += bot.format_words_text(user_info['daily_words'], user_info['level'], "ваши слова на сегодня")
                words_text += "Удачного изучения! 📚"
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=words_text,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Ошибка в ежедневной задаче: {e}")

def main():
    """Запуск бота"""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    try:
        # Создание приложения с JobQueue
        application = Application.builder().token(TOKEN).build()
        
        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("translate", translate_command))
        application.add_handler(CommandHandler("more", more_command))
        application.add_handler(CommandHandler("level", level_command))
        application.add_handler(CommandHandler("test_daily", test_daily_command))
        
        # Обработчики callback-кнопок
        application.add_handler(CallbackQueryHandler(handle_level_selection, pattern="^level_"))
        application.add_handler(CallbackQueryHandler(handle_more_words, pattern="^more_words$"))
        application.add_handler(CallbackQueryHandler(handle_translate_mode, pattern="^translate_mode$"))
        application.add_handler(CallbackQueryHandler(handle_back_to_words, pattern="^back_to_words$"))
        application.add_handler(CallbackQueryHandler(handle_change_level, pattern="^change_level$"))
        
        # Обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        
        # Настройка ежедневной задачи (10:00 по Москве)
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
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        raise

if __name__ == '__main__':
    main()
