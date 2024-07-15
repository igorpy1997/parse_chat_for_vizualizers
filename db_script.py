import sqlite3

# Функция для добавления записи в базу данных
def add_user_chat(user_id, chat_link):
    conn = sqlite3.connect('telegram_parser.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO user_chats (user_id, chat_link) VALUES (?, ?)
        ON CONFLICT(user_id) DO NOTHING
    ''', (user_id, chat_link))

    conn.commit()
    conn.close()

# Функция для получения ссылки на чат по user_id
def get_chat_link(user_id):
    conn = sqlite3.connect('telegram_parser.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT chat_link FROM user_chats WHERE user_id = ?
    ''', (user_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    else:
        return None

# Функция для добавления чата в таблицу listened_chats
def add_listened_chat(user_id, chat_link, target_chat_link):
    conn = sqlite3.connect('telegram_parser.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO listened_chats (user_id, chat_link, target_chat_link)
        VALUES (?, ?, ?)
    ''', (user_id, chat_link, target_chat_link))

    conn.commit()
    conn.close()

# Функция для удаления чата из таблицы listened_chats
def delete_listened_chat(chat_link):
    conn = sqlite3.connect('telegram_parser.db')
    cursor = conn.cursor()

    cursor.execute('''
        DELETE FROM listened_chats WHERE chat_link = ?
    ''', (chat_link,))

    conn.commit()
    conn.close()

import sqlite3


def get_all_user_chats():
    conn = sqlite3.connect('telegram_parser.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, chat_link FROM listened_chats
    ''')

    rows = cursor.fetchall()
    conn.close()

    user_chats = {}
    for row in rows:
        user_id, chat_link = row
        if user_id not in user_chats:
            user_chats[user_id] = []
        user_chats[user_id].append(chat_link)

    return user_chats

    def init_target_chat(self):
        # Получаем целевой чат из базы данных user_chats
        conn = sqlite3.connect('telegram_parser.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT chat_link FROM user_chats WHERE user_id = ?
        ''', (self.user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            self.target_chat = row[0]
            print(f"Target chat initialized for user {self.user_id}: {self.target_chat}")
        else:
            print(f"No target chat found for user {self.user_id}")

def init_target_chat(user_id):
    # Получаем целевой чат из базы данных user_chats
    conn = sqlite3.connect('telegram_parser.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT chat_link FROM user_chats WHERE user_id = ?
    ''', (user_id,))

    row = cursor.fetchone()
    conn.close()
    if row:
        print(f"Target chat initialized for user {user_id}: {row[0]}")
        return row[0]
    else:
        print(f"No target chat found for user {user_id}")
        return "No chat"

