#Схема таблиц статистики (общая SQLite-база проекта).
import aiosqlite

from AI_module import database

_DDL = [
    '''
    CREATE TABLE IF NOT EXISTS stats_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        chat_id INTEGER NOT NULL,
        user_id INTEGER,
        user_name TEXT,
        is_command INTEGER DEFAULT 0
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS stats_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        chat_id INTEGER NOT NULL,
        user_id INTEGER,
        command TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS stats_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        chat_id INTEGER NOT NULL,
        should INTEGER,
        reason TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS stats_videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        chat_id INTEGER NOT NULL,
        user_id INTEGER,
        user_name TEXT,
        platform TEXT,
        status TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS stats_llm_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        chat_id INTEGER,
        tag TEXT,
        prompt_tokens INTEGER,
        completion_tokens INTEGER
    )
    ''',
    'CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON stats_messages(chat_id, ts)',
    'CREATE INDEX IF NOT EXISTS idx_commands_chat_ts ON stats_commands(chat_id, ts)',
    'CREATE INDEX IF NOT EXISTS idx_decisions_chat_ts ON stats_decisions(chat_id, ts)',
    'CREATE INDEX IF NOT EXISTS idx_videos_chat_ts ON stats_videos(chat_id, ts)',
    'CREATE INDEX IF NOT EXISTS idx_usage_chat_ts ON stats_llm_usage(chat_id, ts)',
]


async def init_db():
    """Создаёт таблицы статистики и индексы, если их ещё нет."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        for statement in _DDL:
            await db.execute(statement)
        await db.commit()
