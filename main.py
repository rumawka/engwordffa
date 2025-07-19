import os
import asyncio
import logging
import json
import aiohttp
import random
import re
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
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM
class UserState(StatesGroup):
    choosing_level = State()
    translate_mode = State()

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
        # Большой словарь для перевода отдельных слов
        self.translation_dict = {
            # A1 уровень
            'cat': 'кот, кошка', 'dog': 'собака', 'house': 'дом', 'water': 'вода',
            'food': 'еда', 'book': 'книга', 'car': 'машина', 'tree': 'дерево',
            'man': 'мужчина', 'woman': 'женщина', 'child': 'ребенок', 'boy': 'мальчик',
            'girl': 'девочка', 'mother': 'мать', 'father': 'отец', 'family': 'семья',
            'friend': 'друг', 'school': 'школа', 'work': 'работа', 'home': 'дом',
            'table': 'стол', 'chair': 'стул', 'bed': 'кровать', 'door': 'дверь',
            'window': 'окно', 'phone': 'телефон', 'computer': 'компьютер',
            'money': 'деньги', 'time': 'время', 'day': 'день', 'night': 'ночь',
            'morning': 'утро', 'evening': 'вечер', 'week': 'неделя', 'month': 'месяц',
            'year': 'год', 'today': 'сегодня', 'tomorrow': 'завтра', 'yesterday': 'вчера',
            'good': 'хороший', 'bad': 'плохой', 'big': 'большой', 'small': 'маленький',
            'new': 'новый', 'old': 'старый', 'young': 'молодой', 'hot': 'горячий',
            'cold': 'холодный', 'happy': 'счастливый', 'sad': 'грустный',
            'love': 'любить', 'like': 'нравиться', 'want': 'хотеть', 'need': 'нуждаться',
            'go': 'идти', 'come': 'приходить', 'see': 'видеть', 'look': 'смотреть',
            'hear': 'слышать', 'speak': 'говорить', 'say': 'сказать', 'tell': 'рассказать',
            'know': 'знать', 'think': 'думать', 'understand': 'понимать',
            'eat': 'есть', 'drink': 'пить', 'sleep': 'спать', 'wake': 'просыпаться',
            'walk': 'гулять', 'run': 'бегать', 'sit': 'сидеть', 'stand': 'стоять',
            
            # A2 уровень
            'beautiful': 'красивый', 'important': 'важный', 'different': 'разный',
            'difficult': 'трудный', 'comfortable': 'удобный', 'interesting': 'интересный',
            'dangerous': 'опасный', 'easy': 'легкий', 'expensive': 'дорогой',
            'cheap': 'дешевый', 'free': 'бесплатный', 'busy': 'занятый',
            'tired': 'уставший', 'hungry': 'голодный', 'thirsty': 'жаждущий',
            'angry': 'злой', 'worried': 'обеспокоенный', 'excited': 'взволнованный',
            'surprised': 'удивленный', 'confused': 'смущенный',
            'travel': 'путешествовать', 'visit': 'посещать', 'stay': 'оставаться',
            'move': 'двигаться', 'stop': 'останавливать', 'start': 'начинать',
            'finish': 'заканчивать', 'continue': 'продолжать', 'change': 'менять',
            'help': 'помогать', 'ask': 'спрашивать', 'answer': 'отвечать',
            'explain': 'объяснять', 'learn': 'учиться', 'teach': 'преподавать',
            'study': 'изучать', 'practice': 'практиковать', 'remember': 'помнить',
            'forget': 'забывать', 'choose': 'выбирать', 'decide': 'решать',
            'try': 'пытаться', 'succeed': 'успешно завершать', 'fail': 'терпеть неудачу',
            
            # B1 уровень
            'accomplish': 'достигать', 'approximately': 'приблизительно',
            'benefit': 'выгода', 'challenge': 'вызов', 'circumstances': 'обстоятельства',
            'convenient': 'удобный', 'develop': 'развивать', 'environment': 'окружающая среда',
            'equipment': 'оборудование', 'experience': 'опыт', 'immediate': 'немедленный',
            'individual': 'индивидуальный', 'opportunity': 'возможность',
            'particular': 'особенный', 'previous': 'предыдущий', 'recognize': 'узнавать',
            'require': 'требовать', 'situation': 'ситуация', 'specific': 'конкретный',
            'suggest': 'предлагать', 'traditional': 'традиционный',
            'adventure': 'приключение', 'attitude': 'отношение', 'confidence': 'уверенность',
            'creative': 'творческий', 'curious': 'любопытный', 'enthusiasm': 'энтузиазм',
            'flexible': 'гибкий', 'independent': 'независимый', 'patient': 'терпеливый',
            'reliable': 'надежный', 'responsible': 'ответственный', 'sensitive': 'чувствительный',
            
            # B2 уровень
            'accumulate': 'накапливать', 'adequate': 'достаточный',
            'ambassador': 'посол', 'assumption': 'предположение',
            'controversy': 'противоречие', 'deteriorate': 'ухудшаться',
            'eliminate': 'устранять', 'fundamental': 'фундаментальный',
            'implement': 'реализовывать', 'inevitable': 'неизбежный',
            'monopoly': 'монополия', 'negotiate': 'вести переговоры',
            'perspective': 'перспектива', 'priority': 'приоритет',
            'reluctant': 'неохотный', 'significant': 'значительный',
            'straightforward': 'прямолинейный', 'substantial': 'существенный',
            'suspend': 'приостанавливать', 'tremendous': 'огромный',
            'underestimate': 'недооценивать', 'viable': 'жизнеспособный',
            'allocate': 'выделять', 'analyze': 'анализировать', 'appreciate': 'ценить',
            'collaborate': 'сотрудничать', 'compensate': 'компенсировать',
            'constitute': 'составлять', 'demonstrate': 'демонстрировать',
            'distribute': 'распространять', 'evaluate': 'оценивать',
            'generate': 'генерировать', 'integrate': 'интегрировать',
            
            # C1 уровень
            'abstraction': 'абстракция', 'ambiguous': 'двусмысленный',
            'articulate': 'четко выражать', 'coherent': 'связный',
            'comprehensive': 'всеобъемлющий', 'contemplate': 'размышлять',
            'contingent': 'зависящий от обстоятельств', 'discrimination': 'дискриминация',
            'elaborate': 'детально разрабатывать', 'explicit': 'явный',
            'facilitate': 'способствовать', 'hypothesis': 'гипотеза',
            'implicit': 'подразумеваемый', 'incentive': 'стимул',
            'integrity': 'целостность', 'manipulate': 'манипулировать',
            'paradigm': 'парадигма', 'precede': 'предшествовать',
            'presumably': 'предположительно', 'protocol': 'протокол',
            'scrutinize': 'тщательно изучать', 'suppress': 'подавлять',
            'tentative': 'предварительный', 'turbulence': 'турбулентность',
            'undermine': 'подрывать', 'versatile': 'универсальный',
            
            # C2 уровень
            'epitome': 'воплощение', 'facade': 'фасад', 'inherent': 'присущий',
            'juxtapose': 'сопоставлять', 'nuance': 'нюанс', 'paradox': 'парадокс',
            'permeate': 'пропитывать', 'quintessential': 'типичный',
            'ramification': 'разветвление', 'sophisticated': 'сложный',
            'tangible': 'осязаемый', 'ubiquitous': 'повсеместный',
            'vindicate': 'оправдывать', 'whimsical': 'причудливый',
            'xenophobia': 'ксенофобия', 'yearning': 'тоска', 'zealous': 'ревностный',
            'aesthetic': 'эстетический', 'conundrum': 'головоломка',
            'ephemeral': 'эфемерный', 'fastidious': 'придирчивый',
            'gregarious': 'общительный', 'insidious': 'коварный',
            'melancholy': 'меланхолия', 'ostentatious': 'показной',
            'pensive': 'задумчивый', 'quixotic': 'донкихотский',
            'resilient': 'стойкий', 'serendipity': 'счастливая случайность',
            'transcend': 'превосходить', 'utopia': 'утопия'
        }
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def translate_word(self, word: str) -> Optional[Dict[str, str]]:
        """Перевод отдельного слова"""
        word_lower = word.lower().strip()
        
        # Сначала проверяем наш внутренний словарь
        if word_lower in self.translation_dict:
            return {
                'word': word_lower,
                'translation': self.translation_dict[word_lower],
                'definition': f'Definition for "{word_lower}"',
                'source': 'internal'
            }
        
        # Можно добавить вызов внешнего API здесь
        try:
            # Пример с Free Dictionary API
            session = await self.get_session()
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word_lower}"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        entry = data[0]
                        meanings = entry.get('meanings', [])
                        
                        if meanings and len(meanings) > 0:
                            definition = meanings[0].get('definitions', [{}])[0].get('definition', '')
                            
                            # Простейший перевод через встроенный словарь или заглушка
                            translation = self._get_simple_translation(word_lower)
                            
                            return {
                                'word': word_lower,
                                'translation': translation,
                                'definition': definition,
                                'source': 'api'
                            }
        
        except Exception as e:
            logger.error(f"Error translating word '{word}': {e}")
        
        # Если ничего не найдено
        return None
    
    def _get_simple_translation(self, word: str) -> str:
        """Простейший перевод для неизвестных слов"""
        # Можно добавить базовые переводы или использовать машинный перевод
        common_translations = {
            'hello': 'привет',
            'world': 'мир',
            'apple': 'яблоко',
            'orange': 'апельсин',
            'banana': 'банан',
            'red': 'красный',
            'blue': 'синий',
            'green': 'зеленый',
            'black': 'черный',
            'white': 'белый',
            'yes': 'да',
            'no': 'нет',
            'please': 'пожалуйста',
            'thank': 'спасибо',
            'sorry': 'извините'
        }
        
        return common_translations.get(word, f"Перевод для '{word}' не найден")
    
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
        [InlineKeyboardButton(text="🔍 Перевести слово", callback_data="translate_mode")],
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

@dp.callback_query(F.data == "translate_mode")
async def translate_mode(callback_query: types.CallbackQuery, state: FSMContext):
    """Режим перевода слов"""
    keyboard = [[InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback_query.message.edit_text(
        "🔍 <b>Режим перевода</b>\n\n"
        "Напишите английское слово, и я переведу его на русский язык.\n\n"
        "Например: <code>cat</code>, <code>beautiful</code>, <code>understand</code>\n\n"
        "💡 <i>В моём словаре более 200 слов разных уровней сложности!</i>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    await state.set_state(UserState.translate_mode)
    await callback_query.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback_query.message.edit_text(
        "🏠 Главное меню\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )
    await state.clear()
    await callback_query.answer()

@dp.message(UserState.translate_mode)
async def handle_translation_request(message: types.Message, state: FSMContext):
    """Обработка запроса на перевод"""
    word = message.text.strip()
    
    # Проверяем, что это действительно одно слово на английском
    if not re.match(r'^[a-zA-Z]+
    """Показать информацию"""
    user_id = callback_query.from_user.id
    user_level = users_data.get(user_id, {}).get('level', 'не выбран')
    level_name = LEVELS.get(user_level, 'не выбран')
    
    info_text = (
        f"ℹ️ <b>Информация о боте</b>\n\n"
        f"👤 <b>Ваш уровень:</b> {level_name}\n"
        f"⏰ <b>Время отправки:</b> 10:00 по московскому времени\n"
        f"📚 <b>Количество слов в день:</b> 5\n"
        f"🔍 <b>Словарь:</b> 200+ слов для перевода\n\n"
        f"<b>Доступные команды:</b>\n"
        f"/start - Перезапустить бота\n"
        f"/help - Показать справку\n"
        f"/translate [слово] - Быстрый перевод\n\n"
        f"<b>Функции:</b>\n"
        f"📖 Ежедневные слова по уровню\n"
        f"🔍 Перевод любых слов\n"
        f"⚙️ Настройка уровня английского\n"
        f"📊 Слова с переводом и определениями\n\n"
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

@dp.message(Command("translate"))
async def translate_command(message: types.Message):
    """Быстрый перевод через команду /translate"""
    # Извлекаем слово из команды
    text_parts = message.text.split()
    
    if len(text_parts) < 2:
        await message.answer(
            "🔍 <b>Команда перевода</b>\n\n"
            "Использование: <code>/translate слово</code>\n\n"
            "Примеры:\n"
            "• <code>/translate cat</code>\n"
            "• <code>/translate beautiful</code>\n"
            "• <code>/translate understand</code>\n\n"
            "Или используйте кнопку '🔍 Перевести слово' в главном меню!",
            reply_markup=get_main_keyboard(),
            parse_mode='HTML'
        )
        return
    
    word = text_parts[1].strip()
    
    # Проверяем корректность слова
    if not re.match(r'^[a-zA-Z]+
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
    asyncio.run(main()), word):
        keyboard = [[InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await message.answer(
            "❌ <b>Некорректный ввод</b>\n\n"
            "Пожалуйста, введите одно английское слово без цифр и специальных символов.\n\n"
            "Примеры правильного ввода:\n"
            "✅ <code>cat</code>\n"
            "✅ <code>beautiful</code>\n"
            "✅ <code>understand</code>\n\n"
            "❌ <code>hello world</code> (несколько слов)\n"
            "❌ <code>cat123</code> (с цифрами)\n"
            "❌ <code>привет</code> (не английский)",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    # Показываем индикатор загрузки
    loading_message = await message.answer("🔍 Ищу перевод...")
    
    # Получаем перевод
    translation_data = await word_service.translate_word(word)
    
    keyboard = [
        [InlineKeyboardButton(text="🔍 Перевести ещё", callback_data="translate_mode")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    if translation_data:
        response_text = (
            f"📖 <b>Перевод слова</b>\n\n"
            f"🇬🇧 <b>{translation_data['word'].capitalize()}</b>\n"
            f"🇷🇺 <i>{translation_data['translation']}</i>\n\n"
        )
        
        if translation_data.get('definition'):
            response_text += f"📝 <b>Определение:</b>\n<i>{translation_data['definition']}</i>\n\n"
        
        response_text += "💡 Попробуйте составить предложение с этим словом!"
        
    else:
        response_text = (
            f"😔 <b>Слово не найдено</b>\n\n"
            f"К сожалению, я не смог найти перевод для слова <b>'{word}'</b>\n\n"
            f"📚 Попробуйте другое слово или проверьте правильность написания.\n\n"
            f"💡 <b>Доступные слова:</b> cat, dog, house, beautiful, important и многие другие!"
        )
    
    # Удаляем сообщение загрузки и отправляем результат
    await loading_message.delete()
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
    asyncio.run(main()), word):
        await message.answer(
            "❌ <b>Некорректное слово</b>\n\n"
            "Пожалуйста, введите одно английское слово без цифр и символов.\n\n"
            "Правильно: <code>/translate cat</code>\n"
            "Неправильно: <code>/translate hello123</code>",
            reply_markup=get_main_keyboard(),
            parse_mode='HTML'
        )
        return
    
    # Показываем процесс перевода
    loading_message = await message.answer("🔍 Перевожу...")
    
    # Получаем перевод
    translation_data = await word_service.translate_word(word)
    
    if translation_data:
        response_text = (
            f"📖 <b>Быстрый перевод</b>\n\n"
            f"🇬🇧 <b>{translation_data['word'].capitalize()}</b>\n"
            f"🇷🇺 <i>{translation_data['translation']}</i>\n\n"
        )
        
        if translation_data.get('definition'):
            response_text += f"📝 <b>Определение:</b>\n<i>{translation_data['definition']}</i>\n\n"
        
        response_text += "💡 Используйте /translate [слово] для быстрого перевода!"
        
    else:
        response_text = (
            f"😔 <b>Слово '{word}' не найдено</b>\n\n"
            f"Попробуйте другое слово или используйте режим перевода из меню."
        )
    
    # Удаляем загрузку и показываем результат
    await loading_message.delete()
    await message.answer(
        response_text,
        reply_markup=get_main_keyboard(),
        parse_mode='HTML'
    )
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
    asyncio.run(main()), word):
        keyboard = [[InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await message.answer(
            "❌ <b>Некорректный ввод</b>\n\n"
            "Пожалуйста, введите одно английское слово без цифр и специальных символов.\n\n"
            "Примеры правильного ввода:\n"
            "✅ <code>cat</code>\n"
            "✅ <code>beautiful</code>\n"
            "✅ <code>understand</code>\n\n"
            "❌ <code>hello world</code> (несколько слов)\n"
            "❌ <code>cat123</code> (с цифрами)\n"
            "❌ <code>привет</code> (не английский)",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    # Показываем индикатор загрузки
    loading_message = await message.answer("🔍 Ищу перевод...")
    
    # Получаем перевод
    translation_data = await word_service.translate_word(word)
    
    keyboard = [
        [InlineKeyboardButton(text="🔍 Перевести ещё", callback_data="translate_mode")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    if translation_data:
        response_text = (
            f"📖 <b>Перевод слова</b>\n\n"
            f"🇬🇧 <b>{translation_data['word'].capitalize()}</b>\n"
            f"🇷🇺 <i>{translation_data['translation']}</i>\n\n"
        )
        
        if translation_data.get('definition'):
            response_text += f"📝 <b>Определение:</b>\n<i>{translation_data['definition']}</i>\n\n"
        
        response_text += "💡 Попробуйте составить предложение с этим словом!"
        
    else:
        response_text = (
            f"😔 <b>Слово не найдено</b>\n\n"
            f"К сожалению, я не смог найти перевод для слова <b>'{word}'</b>\n\n"
            f"📚 Попробуйте другое слово или проверьте правильность написания.\n\n"
            f"💡 <b>Доступные слова:</b> cat, dog, house, beautiful, important и многие другие!"
        )
    
    # Удаляем сообщение загрузки и отправляем результат
    await loading_message.delete()
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
