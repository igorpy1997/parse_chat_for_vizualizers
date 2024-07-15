import os

from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest, InviteToChannelRequest, CreateChannelRequest, \
    LeaveChannelRequest
from telethon.errors import FloodWaitError, ChannelPrivateError, UserPrivacyRestrictedError
import asyncio
from spellchecker import SpellChecker
import pymorphy2
import re
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from telethon.tl.functions.messages import UpdateDialogFilterRequest, GetDialogFiltersRequest, ExportChatInviteRequest
from telethon.tl.types import DialogFilter, UpdateDialogFilter, InputDialogPeer, InputPeerChannel, InputPeerUser

from db_script import delete_listened_chat, add_listened_chat, init_target_chat
from dotenv import load_dotenv
load_dotenv()
# Ваши API ID и API Hash
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')



class MultiChatParser:
    def __init__(self, phone_number, user_id):
        self.chat_links = []
        self.client = TelegramClient(f'multi_chat_parser_session_{user_id}', api_id, api_hash)
        self.chats = []
        self.user_id = user_id
        self.target_chat = init_target_chat(self.user_id) if init_target_chat(self.user_id) != "No chat" else None
        self.phone_number = phone_number
        # Создаём объект SpellChecker для русского языка
        self.spell = SpellChecker(language='ru')

        # Создаём объект MorphAnalyzer для лемматизации русского языка
        self.morph = pymorphy2.MorphAnalyzer()

    async def update_chats(self):
        await self.client.disconnect()
        await self.start()

    @staticmethod
    async def send_message(client, target_chat, text):
        await client.send_message(target_chat, text)

    async def add_chat(self, chat_link, target_chat_link):
        try:
            chat = await self.client.get_entity(chat_link)
            await self.client(JoinChannelRequest(chat))
            print(f'Successfully joined {chat_link}')
            self.chats.append(chat)
            # Add the chat link to the list of chat links
            self.chat_links.append(chat_link)
            # Add the chat link to the list of listened chats in the database
            add_listened_chat(self.user_id, chat_link, target_chat_link)
        except ChannelPrivateError:
            print(f'Cannot join private chat: {chat_link}')
        except FloodWaitError as e:
            print(f'Rate limit hit. Please wait for {e.seconds} seconds.')
        except UserPrivacyRestrictedError:
            print(f'Cannot join due to privacy restrictions: {chat_link}')
        except Exception as e:
            print(f'Failed to join or get entity for {chat_link}: {e}')

    async def delete_chat(self, chat_link):
        try:
            chat = await self.client.get_entity(chat_link)
            if chat in self.chats:
                await self.client(LeaveChannelRequest(chat))
                self.chats.remove(chat)
                self.chat_links.remove(chat_link)
                # Remove the chat link from the list of listened chats in the database
                delete_listened_chat(chat_link)
                print(f'Successfully left and removed {chat_link}')
        except Exception as e:
            print(f'Failed to leave or remove entity for {chat_link}: {e}')


    async def get_listened_chats(self):
        chat_info = []
        for chat_link in self.chat_links:
            try:
                chat = await self.client.get_entity(chat_link)
                chat_info.append(f'{chat_link} - "{chat.title}"')
            except Exception as e:
                print(f'Failed to get entity for {chat_link}: {e}')
        return chat_info


    async def setup_chat(self, chat_name):

        await self.client.start(phone=self.phone_number)

        try:
            # Создание новой супергруппы
            new_channel = await self.client(CreateChannelRequest(
                title=chat_name,
                about='Чат для сбора сообщений',
                megagroup=True
            ))

            new_channel_id = new_channel.chats[0].id
            access_hash = new_channel.chats[0].access_hash

            # Получение ссылки на приглашение
            invite = await self.client(ExportChatInviteRequest(
                peer=await self.client.get_input_entity(new_channel.chats[0])
            ))

            invite_link = invite.link
            self.target_chat = invite_link
            print(f'Invite link for chat {chat_name}: {invite_link}')

            return invite_link

        except Exception as e:
            print(f'Failed to create chat {chat_name}: {e}')
            return None


    async def start(self):
        # Подключаемся к Telegram
        await self.client.start(phone=self.phone_number)

        for link in self.chat_links:
            try:
                chat = await self.client.get_entity(link)
                await self.client(JoinChannelRequest(chat))
                print(f'Successfully joined {link}')
                self.chats.append(chat)
            except ChannelPrivateError:
                print(f'Cannot join private chat: {link}')
            except FloodWaitError as e:
                print(f'Rate limit hit. Please wait for {e.seconds} seconds.')
            except UserPrivacyRestrictedError:
                print(f'Cannot join due to privacy restrictions: {link}')
            except Exception as e:
                print(f'Failed to join or get entity for {link}: {e}')

        @self.client.on(events.NewMessage(chats=self.chats))
        async def handler(event):
            await self.on_new_message(event.message)

        print('Listening to chats:', self.chat_links)
        await self.client.run_until_disconnected()

    async def on_new_message(self, message):
        if self.target_chat is None:
            print("Target chat is not set. Cannot send message.")
            return

        text = message.text
        chat_title = (await self.client.get_entity(message.peer_id)).title
        username = message.sender.username if message.sender.username else "No username"

        text_without_links = re.sub(r'http\S+|www.\S+', '', text)

        # Удаляем лишние пробелы, возникшие из-за удаления ссылок
        text_without_links = ' '.join(text_without_links.split())

        formatted_text = f"[{chat_title} / @{username}]: {text}"
        print(text)

        try:
            # Определяем язык текста
            lang = detect(text_without_links)
        except LangDetectException as e:
            print(f'Language detection error: {e}')
            return
        print(lang)

        if lang == 'ru':
            # Если текст на русском языке, выполняем действия
            corrected_text = self.correct_text(text_without_links)
            lemmatized_text = self.lemmatize_text(corrected_text)
            if self.check_for_keywords(lemmatized_text):
                if await self.is_duplicate_message(text):
                    print("Duplicate message found. Not sending the message.")
                else:
                    await self.send_message(self.client, self.target_chat, formatted_text)
        else:
            # Если текст не на русском языке, проверяем на ключевые слова для этого языка
            if self.check_keywords_not_ru(lang, text_without_links):
                if await self.is_duplicate_message(text):
                    print("Duplicate message found. Not sending the message.")
                else:
                    await self.send_message(self.client, self.target_chat, formatted_text)
                print(f'Text contains keywords in {text}')
                # Здесь можете выполнить нужные действия для этого языка
            else:
                print(f'No keywords found in {text}')

            print(f'Non-Russian message: {text}')

    async def is_duplicate_message(self, text):
        async for msg in self.client.iter_messages(self.target_chat, limit=100):
            if text == msg.text:
                return True
        return False


    def correct_text(self, text):
        words = text.split()
        corrected_words = []
        for word in words:
            if len(word) > 4:
                corrected_word = self.spell.correction(word)
                if corrected_word:
                    corrected_words.append(corrected_word)
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)
        return ' '.join(corrected_words)

    def lemmatize_text(self, text):
        words = text.split()
        lemmatized_words = []
        for word in words:
            parsed_word = self.morph.parse(word)[0]
            lemmatized_words.append(parsed_word.normal_form)
        return ' '.join(lemmatized_words)

    def check_keywords_not_ru(self, language_code, text):
        keywords_file = f'keywords_{language_code}.txt'

        try:
            with open(keywords_file, 'r', encoding='utf-8') as file:
                regex_patterns = file.read().strip().split('\n')
                # Join patterns with '|' for OR condition in regex
                regex_pattern = '|'.join(regex_patterns)

                # Compile regex pattern
                regex = re.compile(regex_pattern, re.IGNORECASE | re.UNICODE)

                # Check if any keyword matches in the text
                if re.search(regex, text):
                    return True
                else:
                    return False
        except FileNotFoundError:
            print(f'Keywords file for language {language_code} not found.')
            return False

    def check_for_keywords(self, text):
        search_terms = [
            r'\bискать\b', r'\bнуждаться\b', r'\bтребовать\b', r'\bнуждаться в\b',
            r'\bнаходиться в поиске\b', r'\bв поиске\b', r'\bмочь\b',
            r'\bделать\b', r'\bмочь сделать\b', r'\bмочь нарисовать\b',
            r'\bтребоваться\b', r'\bнужный\b', r'\в поиск\b', r'\bнужно сделать\b',
            r'\bнужно\b'
        ]

        terms = [
            r'\bдизайнер\b', r'\bвизуализатор\b', r'\b3д\b', r'\b3d\b',
            r'\bдизайнер 3д\b', r'\bдизайнер 3d\b', r'\bвизуализация\b',
            r'\bвизуализатор 3д\b', r'\bвизуализатор 3d\b', r'\bинтерьер\b',
            r'\bмоделлер\b', r'\бхудожник\b', r'\визуализатора\b',
            r'\бвизуализировать\b', r'\бнарисовать\b',
        ]

        for search_term in search_terms:
            for term in terms:
                if re.search(fr'{search_term}.*{term}', text):
                    return True
        return False

    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start())

    async def parse_chat(self, chat_link):
        await self.client.start()

        try:
            chat = await self.client.get_entity(chat_link)
            await self.client(JoinChannelRequest(chat))
            print(f'Successfully joined {chat_link}')
        except ChannelPrivateError:
            print(f'Cannot join private chat: {chat_link}')
            return
        except FloodWaitError as e:
            print(f'Rate limit hit. Please wait for {e.seconds} seconds.')
            return
        except UserPrivacyRestrictedError:
            print(f'Cannot join due to privacy restrictions: {chat_link}')
            return
        except Exception as e:
            print(f'Failed to join or get entity for {chat_link}: {e}')
            return

        async for message in self.client.iter_messages(chat):
            text = message.text
            if text and re.search('[а-яА-Я]', text):
                corrected_text = self.correct_text(text)
                lemmatized_text = self.lemmatize_text(corrected_text)
                if not self.check_for_keywords(lemmatized_text):
                    print(f'Message does not match: {lemmatized_text}')
            else:
                print(f'Non-Russian message: {text}')

    def run_single_chat(self, chat_link):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.parse_chat(chat_link))