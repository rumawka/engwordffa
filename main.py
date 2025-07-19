import os
import asyncio
import logging
import json
import aiohttp
import random
from datetime import datetime, time
from typing import Dict, List, Optional
import pytz

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена из переменной окружения
BOT_TOKEN = os.getenv('7814440652:AAFjykovjRaHZjobm7bL7xEeXfARucfJBQ0')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM
class UserState(StatesGroup):
    choosing_level = State()

# Уровни английского языка
LEVELS = {
    'a1': 'A1 - Beginner',
    'a2': 'A2 - Elementary', 
    'b1': 'B1 - Intermediate',
    'b2': 'B2 - Upper-Intermediate',
    'c1': 'C1 - Advanced',
    'c2': 'C2 - Proficiency'
}

# Хранилище пользователей (в реальном проекте используйте базу данных)
users_data: Dict[int, Dict] = {}

class WordService:
    """Сервис для получения слов через API"""
    
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_random_words(self, level: str, count: int = 5) -> List[Dict[str, str]]:
        """Получение случайных слов для указанного уровня"""
        try:
            # Используем WordsAPI или похожие сервисы
            # Здесь пример с mock данными для разных уровней
            words_by_level = {
                'a1': [
                    {'word': 'cat', 'translation': 'кот, кошка', 'definition': 'A small domesticated carnivorous mammal'},
                    {'word': 'dog', 'translation': 'собака', 'definition': 'A domesticated carnivorous mammal'},
                    {'word': 'house', 'translation': 'дом', 'definition': 'A building for human habitation'},
                    {'word': 'water', 'translation': 'вода', 'definition': 'A colorless, transparent liquid'},
                    {'word': 'food', 'translation': 'еда', 'definition': 'Any nutritious substance that people eat'},
                    {'word': 'book', 'translation': 'книга', 'definition': 'A written or printed work'},
                    {'word': 'car', 'translation': 'машина', 'definition': 'A road vehicle with four wheels'},
                    {'word': 'tree', 'translation': 'дерево', 'definition': 'A woody perennial plant'},
                ],
                'a2': [
                    {'word': 'beautiful', 'translation': 'красивый', 'definition': 'Pleasing the senses or mind aesthetically'},
                    {'word': 'important', 'translation': 'важный', 'definition': 'Of great significance or value'},
                    {'word': 'different', 'translation': 'разный', 'definition': 'Not the same as another'},
                    {'word': 'difficult', 'translation': 'трудный', 'definition': 'Needing much effort to accomplish'},
                    {'word': 'comfortable', 'translation': 'удобный', 'definition': 'Providing physical ease and relaxation'},
                    {'word': 'interesting', 'translation': 'интересный', 'definition': 'Arousing curiosity or interest'},
                ],
                'b1': [
                    {'word': 'accomplish', 'translation': 'достигать', 'definition': 'To achieve or complete successfully'},
                    {'word': 'approximately', 'translation': 'приблизительно', 'definition': 'Close to the actual, but not completely accurate'},
                    {'word': 'benefit', 'translation': 'выгода', 'definition': 'An advantage or profit gained from something'},
                    {'word': 'challenge', 'translation': 'вызов', 'definition': 'A call to take part in a contest or competition'},
                    {'word': 'circumstances', 'translation': 'обстоятельства', 'definition': 'A fact or condition connected with an event'},
                    {'word': 'convenient', 'translation': 'удобный', 'definition': 'Fitting in well with needs or activities'},
                ],
                'b2': [
                    {'word': 'accumulate', 'translation': 'накапливать', 'definition': 'To gather together or acquire an increasing number'},
                    {'word': 'adequate', 'translation': 'достаточный', 'definition': 'Satisfactory or acceptable in quality or quantity'},
                    {'word': 'ambassador', 'translation': 'посол', 'definition': 'An accredited diplomat sent by a country'},
                    {'word': 'assumption', 'translation': 'предположение', 'definition': 'A thing that is accepted as true without proof'},
                    {'word': 'controversy', 'translation': 'противоречие', 'definition': 'Prolonged public disagreement or heated discussion'},
                    {'word': 'deteriorate', 'translation': 'ухудшаться', 'definition': 'To become progressively worse'},
                ],
                'c1': [
                    {'word': 'abstraction', 'translation': 'абстракция', 'definition': 'The quality of dealing with ideas rather than events'},
                    {'word': 'ambiguous', 'translation': 'двусмысленный', 'definition': 'Open to more than one interpretation'},
                    {'word': 'articulate', 'translation': 'четко выражать', 'definition': 'To express thoughts clearly and effectively'},
                    {'word': 'coherent', 'translation': 'связный', 'definition': 'Logical and consistent'},
                    {'word': 'comprehensive', 'translation': 'всеобъемлющий', 'definition': 'Complete and including everything'},
                    {'word': 'contemplate', 'translation': 'размышлять', 'definition': 'To think about something deeply'},
                ],
                'c2': [
                    {'word': 'epitome', 'translation': 'воплощение', 'definition': 'A perfect example of a particular quality'},
                    {'word': 'facade', 'translation': 'фасад', 'definition': 'An outward appearance maintained to conceal reality'},
                    {'word': 'inherent', 'translation': 'присущий', 'definition': 'Existing as a natural basic part of something'},
                    {'word': 'juxtapose', 'translation': 'сопоставлять', 'definition': 'To place close together for contrasting effect'},
                    {'word': 'nuance', 'translation': 'нюанс', 'definition': 'A subtle difference in expression or meaning'},
                    {'word': 'paradigm', 'translation': 'парадигма', 'definition': 'A typical example or pattern of something'},
                ]
            }
            
            level_words = words_by_level.get(level, words_by_level['a1'])
            selected_words = random.sample(level_words, min(count, len(level_words)))
            return selected_words
            
        except Exception as e:
            logger.error(f"Error getting words: {e}")
            # Fallback слова
            return [
                {'word': 'hello', 'translation': 'привет', 'definition': 'Used as a greeting'},
                {'word': 'world', 'translation': 'мир', 'definition': 'The earth and all its inhabitants'},
            ]

word_service = WordService()

def get_level_keyboard():
    """Создание клавиатуры выбора уровня"""
    keyboard = []
    for level_code, level_name in LEVELS.items():
        keyboard.append([InlineKeyboardButton(text=level_name, callback_data=f"level_{level_code}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_main_keyboard():
    """Создание основной клавиатуры"""
    keyboard = [
        [InlineKeyboardButton(text="📚 Получить слова сейчас", callback_data="get_words_now")],
        [InlineKeyboardButton(text="⚙️ Изменить уровень", callback_data="change_level")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    if user_id not in users_data:
        users_data[user_id] = {'level': None, 'last_words_date': None}
    
    welcome_text = (
        "🎓 Добро пожаловать в бота для изучения английского языка!\n\n"
        "📅 Каждый день в 10:00 по московскому времени я буду присылать вам новые слова для изучения.\n\n"
        "Сначала выберите ваш уровень английского языка:"
    )
    
    await message.answer(welcome_text, reply_markup=get_level_keyboard())
    await state.set_state(UserState.choosing_level)

@dp.callback_query(F.data.startswith("level_"))
async def set_level(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора уровня"""
    level = callback_query.data.replace("level_", "")
    user_id = callback_query.from_user.id
    
    users_data[user_id]['level'] = level
    level_name = LEVELS[level]
    
    await callback_query.message.edit_text(
        f"✅ Отлично! Ваш уровень установлен: {level_name}\n\n"
        f"Теперь вы будете получать слова каждый день в 10:00 по московскому времени.\n\n"
        f"Что хотите сделать?",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()
    await callback_query.answer()

@dp.callback_query(F.data == "change_level")
async def change_level(callback_query: types.CallbackQuery, state: FSMContext):
    """Изменение уровня"""
    await callback_query.message.edit_text(
        "Выберите новый уровень английского языка:",
        reply_markup=get_level_keyboard()
    )
    await state.set_state(UserState.choosing_level)
    await callback_query.answer()

@dp.callback_query(F.data == "get_words_now")
async def get_words_now(callback_query: types.CallbackQuery):
    """Получить слова прямо сейчас"""
    user_id = callback_query.from_user.id
    
    if user_id not in users_data or not users_data[user_id]['level']:
        await callback_query.answer("❌ Сначала выберите уровень!", show_alert=True)
        return
    
    level = users_data[user_id]['level']
    words = await word_service.get_random_words(level, 5)
    
    words_text = format_words_message(words, level)
    
    await callback_query.message.edit_text(
        words_text,
        reply_markup=get_main_keyboard(),
        parse_mode='HTML'
    )
    await callback_query.answer()

@dp.callback_query(F.data == "info")
async def show_info(callback_query: types.CallbackQuery):
    """Показать информацию"""
    user_id = callback_query.from_user.id
    user_level = users_data.get(user_id, {}).get('level', 'не выбран')
    level_name = LEVELS.get(user_level, 'не выбран')
    
    info_text = (
        f"ℹ️ <b>Информация о боте</b>\n\n"
        f"👤 <b>Ваш уровень:</b> {level_name}\n"
        f"⏰ <b>Время отправки:</b> 10:00 по московскому времени\n"
        f"📚 <b>Количество слов в день:</b> 5\n\n"
        f"<b>Доступные команды:</b>\n"
        f"/start - Перезапустить бота\n"
        f"/help - Показать справку\n\n"
        f"<b>Уровни английского:</b>\n"
        f"A1 - Начальный\n"
        f"A2 - Элементарный\n"
        f"B1 - Средний\n"
        f"B2 - Выше среднего\n"
        f"C1 - Продвинутый\n"
        f"C2 - Профессиональный"
    )
    
    await callback_query.message.edit_text(
        info_text,
        reply_markup=get_main_keyboard(),
        parse_mode='HTML'
    )
    await callback_query.answer()

@dp.message(Command("help"))
async def help_command(message: types.Message):
    """Команда помощи"""
    help_text = (
        "🆘 <b>Справка</b>\n\n"
        "Этот бот поможет вам изучать английский язык каждый день!\n\n"
        "<b>Основные функции:</b>\n"
        "• Ежедневная отправка новых слов в 10:00 МСК\n"
        "• Выбор уровня английского (A1-C2)\n"
        "• Получение слов по запросу\n\n"
        "<b>Команды:</b>\n"
        "/start - Запустить бота\n"
        "/help - Показать эту справку\n\n"
        "Нажмите на кнопки ниже для взаимодействия с ботом!"
    )
    
    await message.answer(help_text, reply_markup=get_main_keyboard(), parse_mode='HTML')

def format_words_message(words: List[Dict[str, str]], level: str) -> str:
    """Форматирование сообщения со словами"""
    level_name = LEVELS.get(level, level.upper())
    today = datetime.now().strftime("%d.%m.%Y")
    
    message = f"📚 <b>Слова на сегодня ({today})</b>\n"
    message += f"🎯 <b>Уровень:</b> {level_name}\n\n"
    
    for i, word_data in enumerate(words, 1):
        word = word_data['word']
        translation = word_data['translation']
        definition = word_data.get('definition', '')
        
        message += f"<b>{i}. {word.capitalize()}</b>\n"
        message += f"🇷🇺 {translation}\n"
        if definition:
            message += f"📖 <i>{definition}</i>\n"
        message += "\n"
    
    message += "💡 <b>Совет:</b> Попробуйте составить предложения с этими словами!"
    
    return message

async def send_daily_words():
    """Отправка ежедневных слов всем пользователям"""
    logger.info("Starting daily words distribution...")
    
    for user_id, user_data in users_data.items():
        if user_data.get('level'):
            try:
                level = user_data['level']
                words = await word_service.get_random_words(level, 5)
                words_text = format_words_message(words, level)
                
                await bot.send_message(
                    user_id,
                    words_text,
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )
                
                # Обновляем дату последней отправки
                users_data[user_id]['last_words_date'] = datetime.now().date().isoformat()
                
                logger.info(f"Words sent to user {user_id}")
                
            except Exception as e:
                logger.error(f"Error sending words to user {user_id}: {e}")
    
    logger.info("Daily words distribution completed")

async def schedule_daily_task():
    """Планировщик ежедневных задач"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    target_time = time(10, 0)  # 10:00
    
    while True:
        try:
            now = datetime.now(moscow_tz)
            target_datetime = moscow_tz.localize(
                datetime.combine(now.date(), target_time)
            )
            
            # Если время уже прошло, планируем на завтра
            if now >= target_datetime:
                target_datetime = target_datetime.replace(day=target_datetime.day + 1)
            
            # Вычисляем время до отправки
            time_until_send = (target_datetime - now).total_seconds()
            
            logger.info(f"Next daily words scheduled in {time_until_send/3600:.2f} hours")
            
            await asyncio.sleep(time_until_send)
            await send_daily_words()
            
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
            await asyncio.sleep(3600)  # Повторяем через час при ошибке

async def main():
    """Основная функция"""
    try:
        # Запускаем планировщик в отдельной задаче
        scheduler_task = asyncio.create_task(schedule_daily_task())
        
        logger.info("Bot is starting...")
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Закрываем сессию HTTP
        await word_service.close_session()
        # Отменяем планировщик
        if 'scheduler_task' in locals():
            scheduler_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
