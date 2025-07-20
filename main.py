import os
import asyncio
import json
import logging
from datetime import datetime, time
import pytz
import aiohttp
import sqlite3
from typing import List, Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import schedule
import threading

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = os.getenv('BOT_TOKEN')
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Уровни сложности
LEVELS = {
    'A1': 'beginner',
    'A2': 'elementary', 
    'B1': 'intermediate',
    'B2': 'upper-intermediate',
    'C1': 'advanced',
    'C2': 'proficiency'
}

class DatabaseManager:
    def __init__(self, db_name="english_bot.db"):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                level TEXT DEFAULT 'A1',
                daily_words_count INTEGER DEFAULT 5,
                learned_words TEXT DEFAULT '[]'
            )
        ''')
        
        # Таблица слов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                level TEXT NOT NULL,
                definition TEXT,
                examples TEXT,
                UNIQUE(word, level)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, level: str = 'A1'):
        """Добавление нового пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, level)
            VALUES (?, ?)
        ''', (user_id, level))
        conn.commit()
        conn.close()
    
    def update_user_level(self, user_id: int, level: str):
        """Обновление уровня пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET level = ? WHERE user_id = ?
        ''', (level, user_id))
        conn.commit()
        conn.close()
    
    def get_user_info(self, user_id: int) -> Dict:
        """Получение информации о пользователе"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT level, daily_words_count, learned_words
            FROM users WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'level': result[0],
                'daily_words_count': result[1],
                'learned_words': json.loads(result[2])
            }
        return {'level': 'A1', 'daily_words_count': 5, 'learned_words': []}
    
    def add_learned_word(self, user_id: int, word: str):
        """Добавление изученного слова"""
        user_info = self.get_user_info(user_id)
        learned_words = user_info['learned_words']
        
        if word not in learned_words:
            learned_words.append(word)
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET learned_words = ? WHERE user_id = ?
            ''', (json.dumps(learned_words), user_id))
            conn.commit()
            conn.close()
    
    def save_words(self, words: List[Dict], level: str):
        """Сохранение слов в базу данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        for word_data in words:
            cursor.execute('''
                INSERT OR REPLACE INTO words (word, translation, level, definition, examples)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                word_data['word'],
                word_data['translation'], 
                level,
                word_data.get('definition', ''),
                json.dumps(word_data.get('examples', []))
            ))
        
        conn.commit()
        conn.close()
    
    def get_words_for_level(self, level: str, exclude_words: List[str] = None, limit: int = 5) -> List[Dict]:
        """Получение слов для определенного уровня"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        exclude_condition = ""
        params = [level]
        
        if exclude_words:
            placeholders = ','.join('?' for _ in exclude_words)
            exclude_condition = f" AND word NOT IN ({placeholders})"
            params.extend(exclude_words)
        
        params.append(limit)
        
        cursor.execute(f'''
            SELECT word, translation, definition, examples
            FROM words 
            WHERE level = ?{exclude_condition}
            ORDER BY RANDOM()
            LIMIT ?
        ''', params)
        
        results = cursor.fetchall()
        conn.close()
        
        words = []
        for row in results:
            words.append({
                'word': row[0],
                'translation': row[1],
                'definition': row[2],
                'examples': json.loads(row[3]) if row[3] else []
            })
        
        return words

class WordAPI:
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        """Получение HTTP сессии"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
    
    async def fetch_words_from_api(self, level: str, count: int = 50) -> List[Dict]:
        """Загрузка слов через API (используем Free Dictionary API)"""
        # Базовые слова для разных уровней
        level_words = {
            'A1': ['hello', 'good', 'water', 'food', 'house', 'family', 'friend', 'work', 'time', 'day'],
            'A2': ['happy', 'important', 'problem', 'different', 'information', 'business', 'service', 'money', 'school', 'student'],
            'B1': ['environment', 'experience', 'technology', 'government', 'community', 'opportunity', 'relationship', 'development', 'education', 'management'],
            'B2': ['sophisticated', 'comprehensive', 'fundamental', 'significant', 'alternative', 'contribute', 'demonstrate', 'establish', 'investigate', 'participate'],
            'C1': ['contemporary', 'paradigm', 'phenomenon', 'methodology', 'interpretation', 'correlation', 'implementation', 'specifications', 'infrastructure', 'prerequisites'],
            'C2': ['juxtaposition', 'quintessential', 'ubiquitous', 'perspicacious', 'serendipitous', 'ineffable', 'mellifluous', 'ephemeral', 'sanguine', 'facetious']
        }
        
        words = []
        base_words = level_words.get(level, level_words['A1'])
        
        session = await self.get_session()
        
        for word in base_words[:count]:
            try:
                # Используем Free Dictionary API
                url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            word_info = data[0]
                            meanings = word_info.get('meanings', [])
                            
                            if meanings:
                                definition = meanings[0].get('definitions', [{}])[0].get('definition', '')
                                
                                # Простой перевод (можно заменить на более точный API)
                                translation = await self.get_translation(word)
                                
                                words.append({
                                    'word': word,
                                    'translation': translation,
                                    'definition': definition,
                                    'examples': [meanings[0].get('definitions', [{}])[0].get('example', '')]
                                })
                
                await asyncio.sleep(0.1)  # Пауза между запросами
                
            except Exception as e:
                logger.error(f"Ошибка при получении слова {word}: {e}")
                # Добавляем базовое слово если API не отвечает
                words.append({
                    'word': word,
                    'translation': 'перевод',  # Базовый перевод
                    'definition': f'Definition for {word}',
                    'examples': [f'Example with {word}']
                })
        
        return words
    
    async def get_translation(self, word: str, target_lang: str = 'ru') -> str:
        """Получение перевода слова"""
        # Простой словарь переводов для демонстрации
        translations = {
            'hello': 'привет', 'good': 'хороший', 'water': 'вода', 'food': 'еда',
            'house': 'дом', 'family': 'семья', 'friend': 'друг', 'work': 'работа',
            'time': 'время', 'day': 'день', 'happy': 'счастливый', 'important': 'важный',
            'problem': 'проблема', 'different': 'разный', 'information': 'информация',
            'business': 'бизнес', 'service': 'сервис', 'money': 'деньги',
            'school': 'школа', 'student': 'студент'
        }
        
        return translations.get(word.lower(), 'перевод')

class EnglishLearningBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.db = DatabaseManager()
        self.word_api = WordAPI()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("level", self.show_levels))
        self.application.add_handler(CommandHandler("words", self.get_daily_words))
        self.application.add_handler(CommandHandler("translate", self.translate_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        self.db.add_user(user_id)
        
        keyboard = [
            [InlineKeyboardButton("🎯 Выбрать уровень", callback_data="choose_level")],
            [InlineKeyboardButton("📚 Получить слова", callback_data="get_words")],
            [InlineKeyboardButton("🔄 Перевести слово", callback_data="translate")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = """
🎓 Добро пожаловать в бота для изучения английского языка!

Функции бота:
📚 Ежедневная отправка слов в 10:00 МСК
🎯 Выбор уровня от A1 до C2
🔄 Перевод слов (EN↔RU)
✅ Отметка изученных слов
📈 Дополнительные слова при необходимости

Выберите действие:
        """
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def show_levels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать уровни сложности"""
        await self.choose_level(update, context, edit=False)
    
    async def choose_level(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit=True):
        """Выбор уровня сложности"""
        keyboard = []
        for level, description in LEVELS.items():
            keyboard.append([InlineKeyboardButton(f"{level} - {description}", callback_data=f"level_{level}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "🎯 Выберите ваш уровень английского языка:"
        
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            if update.callback_query:
                await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def get_daily_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ежедневных слов"""
        user_id = update.effective_user.id
        user_info = self.db.get_user_info(user_id)
        
        # Загружаем слова из API если их нет в базе
        words = self.db.get_words_for_level(user_info['level'], user_info['learned_words'], 5)
        
        if len(words) < 3:  # Если слов мало, загружаем новые
            await self.load_words_for_level(user_info['level'])
            words = self.db.get_words_for_level(user_info['level'], user_info['learned_words'], 5)
        
        if not words:
            await update.message.reply_text("😔 Не удалось загрузить слова. Попробуйте позже.")
            return
        
        message_text = f"📚 Ваши слова на уровне {user_info['level']}:\n\n"
        
        for i, word_data in enumerate(words, 1):
            message_text += f"{i}. **{word_data['word']}** - {word_data['translation']}\n"
            if word_data['definition']:
                message_text += f"   _{word_data['definition']}_\n"
            if word_data['examples']:
                message_text += f"   💭 {word_data['examples'][0]}\n"
            message_text += "\n"
        
        keyboard = [
            [InlineKeyboardButton("✅ Изучил эти слова", callback_data="learned_words")],
            [InlineKeyboardButton("➕ Дополнительные слова", callback_data="more_words")],
            [InlineKeyboardButton("🔄 Перевести слово", callback_data="translate")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def load_words_for_level(self, level: str):
        """Загрузка слов для уровня из API"""
        try:
            words = await self.word_api.fetch_words_from_api(level, 20)
            self.db.save_words(words, level)
            logger.info(f"Загружено {len(words)} слов для уровня {level}")
        except Exception as e:
            logger.error(f"Ошибка загрузки слов для уровня {level}: {e}")
    
    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда перевода"""
        await update.message.reply_text(
            "🔄 Отправьте слово для перевода:\n"
            "📝 Английское слово → русский перевод\n" 
            "📝 Русское слово → английский перевод"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text
        
        # Проверяем, является ли это словом для перевода
        if text and len(text.split()) == 1:
            translation = await self.translate_word(text)
            await update.message.reply_text(f"🔄 {text} → {translation}")
        else:
            await update.message.reply_text(
                "Отправьте одно слово для перевода или используйте команды:\n"
                "/words - получить слова для изучения\n"
                "/level - выбрать уровень\n"
                "/translate - режим перевода"
            )
    
    async def translate_word(self, word: str) -> str:
        """Перевод слова"""
        # Простая проверка языка по символам
        is_english = all(ord(char) < 128 for char in word if char.isalpha())
        
        if is_english:
            # Переводим с английского на русский
            translation = await self.word_api.get_translation(word)
        else:
            # Переводим с русского на английский (базовый словарь)
            ru_to_en = {
                'привет': 'hello', 'хороший': 'good', 'вода': 'water', 
                'еда': 'food', 'дом': 'house', 'семья': 'family',
                'друг': 'friend', 'работа': 'work', 'время': 'time'
            }
            translation = ru_to_en.get(word.lower(), 'translation')
        
        return translation
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "choose_level":
            await self.choose_level(update, context)
        
        elif data.startswith("level_"):
            level = data.split("_")[1]
            self.db.update_user_level(user_id, level)
            await self.load_words_for_level(level)  # Предзагружаем слова
            await query.edit_message_text(f"✅ Установлен уровень {level}")
        
        elif data == "get_words":
            await self.get_daily_words(update, context)
        
        elif data == "learned_words":
            user_info = self.db.get_user_info(user_id)
            words = self.db.get_words_for_level(user_info['level'], user_info['learned_words'], 5)
            
            for word_data in words:
                self.db.add_learned_word(user_id, word_data['word'])
            
            await query.edit_message_text("✅ Отлично! Слова отмечены как изученные.")
        
        elif data == "more_words":
            await self.get_daily_words(update, context)
        
        elif data == "translate":
            await query.edit_message_text(
                "🔄 Отправьте слово для перевода:\n"
                "📝 Английское слово → русский перевод\n"
                "📝 Русское слово → английский перевод"
            )
    
    async def send_daily_words_to_all(self):
        """Отправка ежедневных слов всем пользователям"""
        try:
            conn = sqlite3.connect(self.db.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            conn.close()
            
            for (user_id,) in users:
                try:
                    user_info = self.db.get_user_info(user_id)
                    words = self.db.get_words_for_level(user_info['level'], user_info['learned_words'], 5)
                    
                    if len(words) < 3:
                        await self.load_words_for_level(user_info['level'])
                        words = self.db.get_words_for_level(user_info['level'], user_info['learned_words'], 5)
                    
                    if words:
                        message_text = f"🌅 Доброе утро! Ваши слова на уровне {user_info['level']}:\n\n"
                        
                        for i, word_data in enumerate(words, 1):
                            message_text += f"{i}. **{word_data['word']}** - {word_data['translation']}\n"
                            if word_data['definition']:
                                message_text += f"   _{word_data['definition']}_\n\n"
                        
                        keyboard = [
                            [InlineKeyboardButton("✅ Изучил эти слова", callback_data="learned_words")],
                            [InlineKeyboardButton("➕ Дополнительные слова", callback_data="more_words")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await self.application.bot.send_message(
                            chat_id=user_id,
                            text=message_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                    
                    await asyncio.sleep(0.1)  # Пауза между отправками
                
                except Exception as e:
                    logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка массовой рассылки: {e}")
    
    def schedule_daily_words(self):
        """Планировщик ежедневных слов"""
        def run_schedule():
            schedule.every().day.at("07:00").do(
                lambda: asyncio.create_task(self.send_daily_words_to_all())
            )  # 07:00 UTC = 10:00 MSK
            
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        threading.Thread(target=run_schedule, daemon=True).start()
    
    async def run(self):
        """Запуск бота"""
        # Запускаем планировщик
        self.schedule_daily_words()
        
        # Предзагружаем слова для всех уровней
        for level in LEVELS.keys():
            await self.load_words_for_level(level)
        
        # Запускаем бота
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("Бот запущен и готов к работе!")
        
        try:
            await self.application.updater.idle()
        finally:
            await self.word_api.close_session()
            await self.application.stop()

# Главная функция
async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    bot = EnglishLearningBot(BOT_TOKEN)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
