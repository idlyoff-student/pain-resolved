import asyncio
import logging
import aiohttp
import random
try:
    from aiogram.client.session.aiohttp import AiohttpSession
except Exception:
    from aiogram.client.session import AiohttpSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import BOT_TOKEN, LOG_LEVEL, LOG_FILE
from database import Database
from scheduler import SchedulerService
from selenium_service import SeleniumService

logging.basicConfig(level=LOG_LEVEL, filename=LOG_FILE, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

encouraging_phrases = [
    "Ты стараешься, и это уже достойно уважения 💛",
    "Пусть сегодня будет чуть легче, чем вчера 🤍",
    "Ты делаешь столько, сколько можешь — и этого достаточно 🌿",
    "Не забывай беречь себя в этом ритме учёбы 🌸",
    "Даже маленький шаг — это движение вперёд ✨",
    "Ты не обязан быть идеальным, чтобы быть ценным 💫",
    "Твоя усталость — это знак, что ты много работаешь 🌷",
    "Разреши себе немного отдыха, ты заслужил 🕊️",
    "Ты справляешься лучше, чем тебе кажется 🤍",
    "Каждый твой день — это вклад в твоё будущее 🌼",
    "Ошибки не делают тебя хуже, они помогают расти 🌱",
    "Ты уже проделал большую работу, не обесценивай её 💛",
    "Иногда медленно — это тоже хорошо 🌿",
    "Ты имеешь право на паузу и восстановление 🌸",
    "Твои усилия важны, даже если их не все замечают 🤍",
    "Ты движешься в своём темпе, и это нормально ✨",
    "Пусть у тебя получится всё, что ты задумал 🌷",
    "Ты сильнее, чем думаешь о себе 💫",
    "Не забывай гордиться даже маленькими победами 🌼",
    "Ты достоин спокойствия и уверенности 🕊️",
    "Сегодня ты сделал достаточно 🌿",
    "Твоё старание обязательно принесёт плоды 🌱",
    "Ты не один в своих переживаниях 🤍",
    "Позволь себе быть несовершенным и продолжать 💛",
    "Твоя забота о своём будущем уже многое говорит о тебе ✨",
    "Ты справишься, шаг за шагом 🌸",
    "Пусть в твоём дне найдётся место для радости 🌷",
    "Ты заслуживаешь поддержки и тепла 💫",
    "Каждый новый день — это новый шанс 🌼",
    "Береги себя, ты важен 🤍"
]

user_menu_messages = {}

bot = None
session = None
dp = Dispatcher(storage=MemoryStorage())
db = Database()
scheduler = None
selenium = SeleniumService()


class UserState(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()
    waiting_for_times = State()
    waiting_for_new_login = State()
    waiting_for_new_password = State()


def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="О боте", callback_data="status")],
    ])


def status_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_reply_menu")]
    ])


def settings_keyboard(auto_enabled: bool):
    status_emoji = "✅" if auto_enabled else "❌"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Изменить логин/пароль", callback_data="set_credentials")],
        [InlineKeyboardButton(text="⏰ Настроить время авто-входа", callback_data="set_times")],
        [
            InlineKeyboardButton(text="🤖 Авто-вход", callback_data="toggle_auto"),
            InlineKeyboardButton(text=status_emoji, callback_data="toggle_auto")
        ],
        [
            InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications_dev"),
            InlineKeyboardButton(text="❌", callback_data="notifications_dev")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_reply_menu")]
    ])
def retry_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попытаться снова", callback_data="retry_login")]
    ])
def reply_keyboard():
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Войти на Moodle"), KeyboardButton(text="⚙️ Настройки")], [KeyboardButton(text="❓ О боте")]], resize_keyboard=True)
    return kb

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass

    user = db.get_user(message.from_user.id)
    if user:
        phrase = random.choice(encouraging_phrases)
        welcome_text = f"Привет, {message.from_user.full_name}!\n{phrase}\n\nВыберите действие:"
        menu_msg = await message.answer(welcome_text, reply_markup=reply_keyboard())
        user_menu_messages[message.from_user.id] = menu_msg.message_id
        logger.info(f"Existing user {message.from_user.id} returned to main menu")
        return

    sent = await message.answer("👋 *Добро пожаловать\\!*\n\nЭтот бот автоматически проверяет наличие новых заданий на Moodle, который вы сможете очень легко настраивать под свой учебный процесс\\!\n\nСначала введите ваш *логин Moodle*:", parse_mode="MarkdownV2")
    await state.update_data(bot_message_id=sent.message_id)
    await state.set_state(UserState.waiting_for_login)


@dp.message(UserState.waiting_for_login)
async def handle_login_input(message: types.Message, state: FSMContext):
    await state.update_data(login=message.text.strip())
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    try:
        await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_msg_id, text="🔐 Теперь *введите пароль*:", parse_mode="MarkdownV2")
    except Exception as e:
        logger.warning(f"Failed to edit message (password prompt): {e}")
        await message.answer("🔐 Теперь *введите пароль*:", parse_mode="MarkdownV2")

    await state.set_state(UserState.waiting_for_password)


@dp.message(UserState.waiting_for_password)
async def handle_password_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    login = data.get('login')
    password = message.text.strip()
    user_id = message.from_user.id
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')

    try:
        await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_msg_id, text="🔎 Проверяю данные на Moodle, пожалуйста подождите...")
    except Exception as e:
        logger.warning(f"Failed to edit message (checking prompt): {e}")
        sent = await message.answer("🔎 *Проверяю данные на Moodle*, пожалуйста подождите...", parse_mode="MarkdownV2")
        bot_msg_id = sent.message_id
        await state.update_data(bot_message_id=bot_msg_id)

    loop = asyncio.get_running_loop()
    success, info = await loop.run_in_executor(None, selenium.perform_login, login, password)

    if not success:
        try:
            await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_msg_id, text=f"❌ Не удалось войти: неверный логин или пароль.", reply_markup=retry_keyboard())
        except Exception as e:
            logger.warning(f"Failed to edit message (login failed): {e}")
            await message.answer(f"❌ Не удалось войти: неверный логин или пароль.", reply_markup=retry_keyboard())
        await state.update_data(bot_message_id=bot_msg_id)
        await state.set_state(UserState.waiting_for_login)
        return

    # Проверка уникальности логина
    existing = db.get_user_by_login(login)
    if existing and existing != user_id:
        try:
            await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_msg_id, text=r"❌ Этот логин уже привязан к другому Telegram\-аккаунту\.", parse_mode="MarkdownV2", reply_markup=retry_keyboard())
        except Exception as e:
            logger.warning(f"Failed to edit message (login unique check): {e}")
            try:
                await message.answer(r"❌ Этот логин уже привязан к другому Telegram\-аккаунту\.", parse_mode="MarkdownV2", reply_markup=retry_keyboard())
            except Exception as e2:
                logger.warning(f"Failed to send message: {e2}")
                await message.answer("❌ Этот логин уже привязан к другому аккаунту")
        await state.update_data(bot_message_id=bot_msg_id)
        await state.set_state(UserState.waiting_for_login)
        return

    ok = db.add_or_update_user(user_id, login, password)
    if not ok:
        try:
            await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_msg_id, text="❌ Ошибка сохранения данных в базе.", reply_markup=retry_keyboard())
        except Exception as e:
            logger.warning(f"Failed to edit message (db save error): {e}")
            await message.answer("❌ Ошибка сохранения данных в базе.")
        await state.update_data(bot_message_id=bot_msg_id)
        await state.set_state(UserState.waiting_for_login)
        return

    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=bot_msg_id)
    except Exception as e:
        logger.warning(f"Failed to delete message: {e}")

    success_msg = await message.answer("✅ Успешный вход")
    await asyncio.sleep(5)
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=success_msg.message_id)
    except Exception:
        pass

    phrase = random.choice(encouraging_phrases)
    welcome_text = f"👋Привет, {message.from_user.full_name}!\n{phrase}\n\nВыберите действие:"
    menu_msg = await message.answer(welcome_text, reply_markup=reply_keyboard())
    user_menu_messages[message.from_user.id] = menu_msg.message_id
    logger.info(f"Saved menu message ID {menu_msg.message_id} for user {message.from_user.id}")
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "set_times")
async def set_times(callback: types.CallbackQuery, state: FSMContext):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Сначала добавьте логин и пароль.")
        return
    current_times = ', '.join(user['login_times']) if user['login_times'] else 'Не установлены'
    prompt_text = f"⏰ *Настройка времени входа*\n\nТекущие времена: `{current_times}`\n\n📝 Введите новые времена в формате HH:MM, разделенные запятой\n\n_Пример:_\n`09:00, 14:00, 18:30`"
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="back_to_settings", style="danger")]
    ])
    
    try:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=prompt_text,
            parse_mode="MarkdownV2",
            reply_markup=back_kb
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")
        await callback.message.answer(prompt_text, parse_mode="MarkdownV2", reply_markup=back_kb)
    
    await state.update_data(settings_message_id=callback.message.message_id)
    await state.set_state(UserState.waiting_for_times)


@dp.message(UserState.waiting_for_times)
async def process_times(message: types.Message, state: FSMContext):
    times = [t.strip() for t in message.text.split(',')]
    valid_times = []
    for t in times:
        try:
            h, m = map(int, t.split(':'))
            if 0 <= h <= 23 and 0 <= m <= 59:
                valid_times.append(t)
        except:
            pass
    if not valid_times:
        await message.answer("⚠️ Неверный формат\\. Используйте HH:MM\\.", parse_mode="MarkdownV2")
        return
    
    try:
        await message.delete()
    except Exception:
        pass
    
    db.update_login_times(message.from_user.id, valid_times)
    scheduler.update_user_schedule(message.from_user.id)
    
    data = await state.get_data()
    settings_msg_id = data.get('settings_message_id')
    success_text = f"✅ *Времена обновлены\\!*\n\nНовое расписание захода на Moodle: `{', '.join(valid_times)}`"
    
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=settings_msg_id,
            text=success_text,
            parse_mode="MarkdownV2"
        )
        success_msg_id = settings_msg_id
    except Exception as e:
        logger.warning(f"Failed to edit settings message: {e}")
        success_msg = await message.answer(success_text, parse_mode="MarkdownV2")
        success_msg_id = success_msg.message_id
    
    await asyncio.sleep(3)
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=success_msg_id)
    except Exception as e:
        logger.warning(f"Failed to delete success message: {e}")
    
    user = db.get_user(message.from_user.id)
    phrase = random.choice(encouraging_phrases)
    welcome_text = f"Привет, {message.from_user.full_name}!\n{phrase}\n\nВыберите действие:"
    menu_msg = await message.answer(welcome_text, reply_markup=reply_keyboard())
    user_menu_messages[message.from_user.id] = menu_msg.message_id
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "set_credentials")
async def set_credentials(callback: types.CallbackQuery, state: FSMContext):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Сначала добавьте логин и пароль.")
        return
    
    prompt_text = "🔐 *Изменение данных Moodle*\n\n📝 Введите новый *логин* Moodle:"
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="back_to_settings")]
    ])
    
    try:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=prompt_text,
            parse_mode="MarkdownV2",
            reply_markup=back_kb
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")
        await callback.message.answer(prompt_text, parse_mode="MarkdownV2", reply_markup=back_kb)
    
    await state.update_data(settings_message_id=callback.message.message_id)
    await state.set_state(UserState.waiting_for_new_login)

@dp.message(UserState.waiting_for_new_login)
async def process_new_login(message: types.Message, state: FSMContext):
    new_login = message.text.strip()
    
    try:
        await message.delete()
    except Exception:
        pass
    
    # Check if login is already taken
    existing = db.get_user_by_login(new_login)
    if existing and existing != message.from_user.id:
        data = await state.get_data()
        settings_msg_id = data.get('settings_message_id')
        error_text = "❌ Этот логин уже привязан к другому Telegram-аккаунту\\. Попробуйте другой логин\\."
        
        retry_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попытать другой логин", callback_data="back_to_settings")]
        ])
        
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=settings_msg_id,
                text=error_text,
                parse_mode="MarkdownV2",
                reply_markup=retry_kb
            )
        except Exception:
            await message.answer(error_text, parse_mode="MarkdownV2", reply_markup=retry_kb)
        await state.set_state(UserState.waiting_for_new_login)
        return
    
    await state.update_data(new_login=new_login)
    data = await state.get_data()
    settings_msg_id = data.get('settings_message_id')
    
    prompt_text = "🔐 Теперь введите новый *пароль*:"
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=settings_msg_id,
            text=prompt_text,
            parse_mode="MarkdownV2"
        )
    except Exception:
        await message.answer(prompt_text, parse_mode="MarkdownV2")
    
    await state.set_state(UserState.waiting_for_new_password)

@dp.message(UserState.waiting_for_new_password)
async def process_new_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_login = data.get('new_login')
    new_password = message.text.strip()
    user_id = message.from_user.id
    settings_msg_id = data.get('settings_message_id')
    
    try:
        await message.delete()
    except Exception:
        pass
    
    checking_text = "🔎 Проверяю новые данные на Moodle, пожалуйста подождите\\.\\.\\."
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=settings_msg_id,
            text=checking_text,
            parse_mode="MarkdownV2"
        )
    except Exception:
        await message.answer(checking_text, parse_mode="MarkdownV2")
    
    loop = asyncio.get_running_loop()
    success, info = await loop.run_in_executor(None, selenium.perform_login, new_login, new_password)
    
    if not success:
        error_text = "❌ Не удалось войти с новыми данными\\: неверный логин или пароль\\."
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=settings_msg_id,
                text=error_text,
                parse_mode="MarkdownV2"
            )
        except Exception:
            await message.answer(error_text, parse_mode="MarkdownV2")
        await state.set_state(UserState.waiting_for_new_login)
        return
    
    db.add_or_update_user(user_id, new_login, new_password)
    scheduler.update_user_schedule(user_id)
    
    success_text = f"✅ *Данные успешно обновлены\\!*"
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=settings_msg_id,
            text=success_text,
            parse_mode="MarkdownV2"
        )
        success_msg_id = settings_msg_id
    except Exception:
        success_msg = await message.answer(success_text, parse_mode="MarkdownV2")
        success_msg_id = success_msg.message_id
    
    await asyncio.sleep(3)
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=success_msg_id)
    except Exception as e:
        logger.warning(f"Failed to delete success message: {e}")
    
    user = db.get_user(user_id)
    phrase = random.choice(encouraging_phrases)
    welcome_text = f"Привет, {message.from_user.full_name}!\n{phrase}\n\nВыберите действие:"
    menu_msg = await message.answer(welcome_text, reply_markup=reply_keyboard())
    user_menu_messages[user_id] = menu_msg.message_id
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "toggle_auto")
async def toggle_auto(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Сначала добавьте логин и пароль.")
        return
    new_status = not user['auto_enabled']
    db.update_auto_enabled(callback.from_user.id, new_status)
    scheduler.update_user_schedule(callback.from_user.id)
    
    kb = settings_keyboard(new_status)
    try:
        await bot.edit_message_reply_markup(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=kb
        )
    except Exception as e:
        logger.warning(f"Failed to edit settings menu: {e}")
        await callback.answer()

@dp.callback_query(lambda c: c.data == "notifications_dev")
async def notifications_dev(callback: types.CallbackQuery):
    await callback.answer('Функция "Уведомления о заданиях" находится в разработке.', show_alert=True, parse_mode="MarkdownV2")


@dp.callback_query(lambda c: c.data == "status")
async def show_status(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        try:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=callback.message.message_id, text="Данные не найдены. Сначала запустите /start и пройдите авторизацию.")
        except Exception as e:
            logger.warning(f"Failed to edit message (no data found): {e}")
            await callback.message.answer("Данные не найдены. Сначала запустите /start и пройдите авторизацию.")
        return
    times = ', '.join(user['login_times']) if user['login_times'] else 'Не установлены'
    status = "Включен" if user['auto_enabled'] else "Выключен"
    text = f"Профиль:\nuser_id: {user['user_id']}\nАвто-вход: {status}\nВремена: {times}"
    try:
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=callback.message.message_id, text=text, reply_markup=status_back_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=status_back_keyboard())


@dp.callback_query(lambda c: c.data == "back_to_reply_menu")
async def back_to_reply_menu(callback: types.CallbackQuery):
    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    except Exception:
        pass
    
    user = db.get_user(callback.from_user.id)
    phrase = random.choice(encouraging_phrases)
    if user:
        welcome_text = f"Привет, {callback.from_user.full_name}!\n{phrase}\n\nВыберите действие:"
    else:
        welcome_text = f"{phrase}\n\nВыберите действие:"
    menu_msg = await callback.message.answer(welcome_text, reply_markup=reply_keyboard())
    user_menu_messages[callback.from_user.id] = menu_msg.message_id

@dp.callback_query(lambda c: c.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    user = db.get_user(callback.from_user.id)
    kb = settings_keyboard(user['auto_enabled'] if user else False)
    
    if user and user['login_times']:
        if isinstance(user['login_times'], list):
            times = ', '.join(user['login_times'])
        else:
            times = user['login_times']
    else:
        times = 'не установлено'
    
    settings_text = f"""⚙️ *Ваши настройки*

👤 *Имя:* {callback.from_user.full_name}

🔐 *Данные Moodle:*
• Логин: `{user['moodle_login']}`
• Пароль: ||{user['moodle_password']}||

⏰ *Расписание входа:*
`{times}`

_Что вы хотите изменить?_"""
    
    try:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=settings_text,
            parse_mode="MarkdownV2",
            reply_markup=kb
        )
    except Exception as e:
        logger.warning(f"Failed to edit settings message: {e}")
        await callback.message.answer(settings_text, parse_mode="MarkdownV2", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "check_status")
async def check_status(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Данные не найдены.")
        return
    times = ', '.join(user['login_times']) if user['login_times'] else 'Не установлены'
    status = "Включен" if user['auto_enabled'] else "Выключен"
    try:
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=callback.message.message_id, text=f"Авто-вход: {status}\nВремена: {times}")
    except Exception:
        await callback.message.answer(f"Авто-вход: {status}\nВремена: {times}")

@dp.callback_query(lambda c: c.data == "manual_login")
async def manual_login(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Сначала добавьте логин и пароль.")
        return
    running_msg = await callback.message.answer("Запускаю вход...")
    success, message = selenium.perform_login(user['moodle_login'], user['moodle_password'])
    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=running_msg.message_id)
    except Exception:
        pass
    if success:
        await callback.message.answer("✅ Вход выполнен успешно")
    else:
        await callback.message.answer(f"❌ Ошибка: {message}")


@dp.callback_query(lambda c: c.data == "retry_login")
async def retry_login(callback: types.CallbackQuery, state: FSMContext):
    bot_msg_id = callback.message.message_id
    try:
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=bot_msg_id, text="Введите ваш логин Moodle:")
    except Exception:
        await callback.message.answer("Введите ваш логин Moodle:")
    await state.update_data(bot_message_id=bot_msg_id)
    await state.set_state(UserState.waiting_for_login)


@dp.message(Command("menu"))
async def send_menu_command(message: types.Message):
    try:
        phrase = random.choice(encouraging_phrases)
        await message.answer(f"Привет еще раз, {callback.from_user.full_name}!{phrase}\nВыберите действие:", reply_markup=reply_keyboard())
        logger.info(f"Sent reply keyboard to {message.chat.id}")
    except Exception:
        logger.exception("Failed to send reply keyboard")
        try:
            await message.answer("Не удалось показать меню.")
        except Exception:
            pass


@dp.message(lambda m: m.text and "moodle" in m.text.lower())
async def text_run(message: types.Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    if message.from_user.id in user_menu_messages:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=user_menu_messages[message.from_user.id])
        except Exception:
            pass
    
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала добавьте логин и пароль (команда /start).")
        return
    running_msg = await message.answer("Запускаю вход...")
    loop = asyncio.get_running_loop()
    success, info = await loop.run_in_executor(None, selenium.perform_login, user['moodle_login'], user['moodle_password'])
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=running_msg.message_id)
    except Exception:
        pass
    if success:
        msg = await message.answer("✅ Вход выполнен успешно", reply_markup=status_back_keyboard())
    else:
        msg = await message.answer(f"❌ Ошибка: {info}", reply_markup=status_back_keyboard())


@dp.message(lambda m: m.text and "о боте" in m.text.lower())
async def text_about_bot(message: types.Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    if message.from_user.id in user_menu_messages:
        menu_id = user_menu_messages[message.from_user.id]
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=menu_id)
            logger.info(f"Deleted menu message {menu_id} for user {message.from_user.id}")
        except Exception as e:
            logger.warning(f"Failed to delete menu message {menu_id}: {e}")
    
    text = "ℹ️ *О боте*\n\nЭтот бот помогает автоматически проверять наличие новых заданий на платформе Moodle\\. Он может запускаться по расписанию или вручную, при этом посещая все ваши курсы для проверки новых материалов\\.\n\n Возникли вопросы или предложения по улучшению\\? Пишите мне в Telegram: @etcbin"
    await message.answer(text, parse_mode="MarkdownV2", reply_markup=status_back_keyboard())


@dp.message(lambda m: m.text and "настройки" in m.text.lower())
async def text_settings(message: types.Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    if message.from_user.id in user_menu_messages:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=user_menu_messages[message.from_user.id])
        except Exception:
            pass
    
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Данные не найдены. Сначала /start и авторизация.")
        return
    
    if user['login_times']:
        if isinstance(user['login_times'], list):
            times = ', '.join(user['login_times'])
        else:
            times = user['login_times']
    else:
        times = 'Не установлены'
    
    settings_text = f"""⚙️ *Ваши настройки*

👤 *Имя:* {message.from_user.full_name}

🔐 *Данные Moodle:*
• Логин: `{user['moodle_login']}`
• Пароль: ||{user['moodle_password']}||

⏰ *Расписание входа:*
`{times}`

_Что вы хотите изменить?_"""
    
    kb = settings_keyboard(user['auto_enabled'])
    await message.answer(settings_text, parse_mode="MarkdownV2", reply_markup=kb)

async def main():
    logger.info("Bot started")
    global scheduler, bot, session
    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=50)

    import inspect
    aiogram_session = None
    try:
        sig = inspect.signature(AiohttpSession.__init__)
        params = sig.parameters
        if 'timeout' in params or 'connector' in params:
            aiogram_session = AiohttpSession(timeout=timeout, connector=connector)
            bot = Bot(token=BOT_TOKEN, session=aiogram_session)
        else:
            session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            try:
                aiogram_session = AiohttpSession(session=session)
                bot = Bot(token=BOT_TOKEN, session=aiogram_session)
            except TypeError:
                await session.close()
                bot = Bot(token=BOT_TOKEN)
    except Exception:
        try:
            bot = Bot(token=BOT_TOKEN)
        except Exception:
            bot = None

    loop = asyncio.get_running_loop()
    scheduler = SchedulerService(loop=loop)
    try:
        await dp.start_polling(bot)
    finally:
        try:
            await aiogram_session.close()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
