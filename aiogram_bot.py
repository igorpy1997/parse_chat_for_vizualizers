import json
import logging
import asyncio
import os
import re
import sys
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile

from db_create import create_db
from db_script import get_chat_link, add_user_chat, delete_listened_chat, add_listened_chat, get_all_user_chats
from state_check_middleware import StateCheckMiddleware
from telethon_back import MultiChatParser
from dotenv import load_dotenv
load_dotenv()

phone_number = os.getenv('PHONE_NUMBER')
Token = os.getenv('TOKEN')
print(f"TOKEN: {Token}")
if Token is None:
    raise ValueError("TOKEN environment variable is not set")
# Вывод всех переменных окружения для проверки
for key, value in os.environ.items():
    print(f"{key}: {value}")

dp = Dispatcher()
router = Router()
storage = MemoryStorage()
dp.include_router(router)

bot = Bot(Token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

parsers = {}

async def initialize_parsers():
    user_chats = get_all_user_chats()
    for user_id, chat_links in user_chats.items():
        parser = MultiChatParser(phone_number, user_id)
        parser.chat_links = chat_links
        parsers[user_id] = parser
        asyncio.create_task(parser.start())


@router.message(Command('list_chats'), F.text != "/cancel")
async def list_chats(message: types.Message, state: FSMContext):
    await state.set_state(Form.help_command)
    user_id = message.from_user.id
    if user_id in parsers:
        chat_info = await parsers[user_id].get_listened_chats()
        if chat_info:
            response = "Вы отслеживаете следующие чаты:\n" + "\n".join(chat_info)
        else:
            response = "Вы не отслеживаете ни одного чата."
    else:
        response = "Для вас не настроен парсер."
    await state.clear()
    await message.answer(response)



# Определяем состояния для FSM
class Form(StatesGroup):
    name = State()
    surname = State()
    password = State()
    chat_name = State()
    add_chat_name = State()
    delete_chat_name = State()
    help_command = State()

# Обработчик команды /start
@router.message(Command('start'), F.text != "/cancel")
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    create_db()
    chat_link = get_chat_link(user_id)
    if chat_link:
        await message.answer(f"Вы уже зарегистрированы. Ссылка на ваш чат: {chat_link}")
    else:
        await message.answer("Здравствуйте! Пожалуйста, введите ваше имя.")
        await state.update_data(user_id=user_id)
        await state.set_state(Form.name)


# Обработчик для получения имени
@router.message(Form.name, F.text != "/cancel")
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите вашу фамилию.")
    await state.set_state(Form.surname)

# Обработчик для получения фамилии
@router.message(Form.surname, F.text != "/cancel")
async def process_surname(message: types.Message, state: FSMContext):
    await state.update_data(surname=message.text)
    await message.answer("Введите пароль.")
    await state.set_state(Form.password)

# Обработчик для получения пароля
@router.message(Form.password, F.text != "/cancel")
async def process_password(message: types.Message, state: FSMContext):
    if message.text == "vlad_blaga":
        await message.answer("Пароль верный. Введите имя чата, куда будут пересылаться сообщения.")
        await state.set_state(Form.chat_name)
    else:
        await message.answer("Неверный пароль. Попробуйте снова.")
        await state.clear()


# Обработчик для получения имени чата
@router.message(Form.chat_name, F.text != "/cancel")
async def process_chat_name(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    chat_name = message.text
    user_id = user_data['user_id']

    # Создание папки и настройка парсера
    parser = MultiChatParser(phone_number, user_id)
    link = await parser.setup_chat(chat_name)
    parsers[user_id] = parser

    if link:
        # Сохраняем ссылку в базу данных
        add_user_chat(user_id, link)
        await message.answer(f"Чат {chat_name} настроен для парсинга сообщений. Ссылка на чат: {link}")
    else:
        await message.answer(f"Не удалось создать чат {chat_name}. Попробуйте позже.")

    await state.clear()


@router.message(Command('add_chat'), F.text != "/cancel")
async def add_chat(message: types.Message, state: FSMContext):
    await message.answer("Введите ссылку на новый чат.")
    await state.set_state(Form.add_chat_name)


@router.message(Form.add_chat_name, F.text != "/cancel")
async def process_add_chat(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    chat_link = message.text

    target_chat_link = get_chat_link(user_id)

    if target_chat_link:
        await parsers[user_id].add_chat(chat_link, target_chat_link)
        await message.answer(f"Чат {chat_link} добавлен и теперь будет отслеживаться.")
        await state.clear()
        await parsers[user_id].update_chats()
    else:
        await message.answer("Целевой чат для этого пользователя не настроен.")

    await state.clear()


# Обработчик команды /delete_chat
@router.message(Command('delete_chat'), F.text != "/cancel")
async def delete_chat(message: types.Message, state: FSMContext):
    await message.answer("Введите ссылку на чат, который нужно удалить.")
    await state.set_state(Form.delete_chat_name)


@router.message(Form.delete_chat_name, F.text != "/cancel")
async def process_delete_chat(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    chat_link = message.text

    await parsers[user_id].delete_chat(chat_link)
    await message.answer(f"Чат {chat_link} удален из списка отслеживаемых.")
    await state.clear()
    await parsers[user_id].update_chats()



@router.message(Command('help'), F.text != "/cancel")
async def help_command(message: types.Message, state: FSMContext):
    await state.set_state(Form.help_command)
    help_text = "Список доступных команд:\n" \
                "/start - Начать регистрацию или получить ссылку на зарегистрированный чат.\n" \
                "/list_chats - Показать список отслеживаемых чатов.\n" \
                "/add_chat - Добавить новый чат для отслеживания.\n" \
                "/delete_chat - Удалить чат из списка отслеживаемых.\n" \
                "/help - Показать это сообщение с описанием команд.\n"\
                "/cancel - Обнулить все команды"
    await state.clear()
    await message.answer(help_text)

@router.message(Command('cancel'))
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    await state.set_state(Form.help_command)
    if current_state is None:
        await state.clear()
        await message.answer("Нет активных операций для отмены.")
        return

    await state.clear()
    await message.answer("Текущая операция отменена.")


async def main() -> None:
    await initialize_parsers()
    dp.message.middleware(StateCheckMiddleware())
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())