import sqlite3

def create_db():
    conn = sqlite3.connect('telegram_parser.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_chats (
            user_id INTEGER PRIMARY KEY,
            chat_link TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listened_chats (
            user_id INTEGER,
            chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_link TEXT NOT NULL,
            target_chat_link TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

create_db()