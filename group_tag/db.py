#Схема таблиц групп участников (общая SQLite-база проекта).
#chat_members — реестр известных участников чата (источник для /all):
#пополняется сообщениями участников и событиями входа.
#chat_tag_meta / chat_tag_members — именованные теги участников. Участник может
#быть известен только по @нику (user_id = NULL) — тогда его тегают текстом «@ник».
import aiosqlite
from AI_module import database

_DDL = [
    '''
    CREATE TABLE IF NOT EXISTS chat_members (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT,
        username TEXT,
        is_bot INTEGER NOT NULL DEFAULT 0,
        last_seen REAL,
        PRIMARY KEY (chat_id, user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS chat_tag_meta (
        chat_id INTEGER NOT NULL,
        tag_key TEXT NOT NULL,
        tag_name TEXT NOT NULL,
        created_ts REAL,
        PRIMARY KEY (chat_id, tag_key)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS chat_tag_members (
        chat_id INTEGER NOT NULL,
        tag_key TEXT NOT NULL,
        user_id INTEGER,
        user_name TEXT,
        username TEXT,
        PRIMARY KEY (chat_id, tag_key, user_id)
    )
    ''',
    'CREATE INDEX IF NOT EXISTS idx_tag_members_user ON chat_tag_members(chat_id, user_id)',
]


async def _migrate_tag_members(db):
    """Пересоздаёт chat_tag_members, если в ней user_id был NOT NULL (до внешних
    участников по нику). Старые строки сохраняются."""
    async with db.execute("PRAGMA table_info(chat_tag_members)") as cursor:
        columns = await cursor.fetchall()
    user_column = next((column for column in columns if column[1] == "user_id"), None)
    if user_column is None or user_column[3] == 0:
        return
    await db.execute("ALTER TABLE chat_tag_members RENAME TO chat_tag_members_old")
    await db.execute(
        '''
        CREATE TABLE chat_tag_members (
            chat_id INTEGER NOT NULL,
            tag_key TEXT NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            username TEXT,
            PRIMARY KEY (chat_id, tag_key, user_id)
        )
        '''
    )
    await db.execute(
        "INSERT INTO chat_tag_members (chat_id, tag_key, user_id, user_name, username) "
        "SELECT chat_id, tag_key, user_id, user_name, username FROM chat_tag_members_old"
    )
    await db.execute("DROP TABLE chat_tag_members_old")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tag_members_user ON chat_tag_members(chat_id, user_id)")


async def init_db():
    """Создаёт таблицы групп участников, если их ещё нет, и мигрирует старую схему."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        for statement in _DDL:
            await db.execute(statement)
        await _migrate_tag_members(db)
        await db.commit()
