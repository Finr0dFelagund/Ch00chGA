#Реестр известных участников чата: источник списка для команды /all.
#Пополняется каждым сообщением участника (note_user), событиями входа
#(add_from_event) и на старте из статистики сообщений. Выход участника
#(remove_user) под общим per-chat локом чистит реестр и все теги чата.
import time

import aiosqlite

from AI_module import database, memory

_INSERT_MEMBER = '''
    INSERT INTO chat_members (chat_id, user_id, user_name, username, is_bot, last_seen)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(chat_id, user_id) DO UPDATE SET
        user_name = excluded.user_name,
        username = COALESCE(excluded.username, chat_members.username),
        is_bot = excluded.is_bot,
        last_seen = excluded.last_seen
'''


def clean_username(username) -> str | None:
    """Ник без ведущего '@'; None для пустого значения."""
    if not username:
        return None
    value = str(username).strip().lstrip("@")
    return value or None


async def _upsert(chat_id: int, user_id: int, user_name=None, username=None, is_bot=False):
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute(
                _INSERT_MEMBER,
                (chat_id, user_id, user_name, clean_username(username), 1 if is_bot else 0, time.time()),
            )
            await db.commit()


async def note_user(chat_id: int, user_id: int, user_name=None, username=None, is_bot=False):
    """Запоминает участника по его сообщению в чате."""
    if not user_id or is_bot:
        return
    await _upsert(chat_id, user_id, user_name, username)


async def add_from_event(chat_id: int, user_id: int, user_name=None, username=None):
    """Добавляет участника в реестр по событию входа в чат."""
    if not user_id:
        return
    await _upsert(chat_id, user_id, user_name, username)


async def remove_user(chat_id: int, user_id: int):
    """Убирает участника из реестра и всех тегов чата."""
    if not user_id:
        return
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute("DELETE FROM chat_members WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            await db.execute(
                "DELETE FROM chat_tag_members WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
            )
            await db.commit()


async def list_members(chat_id: int):
    """Список участников реестра чата: кортежи (user_id, user_name, username)."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, user_name, username FROM chat_members "
            "WHERE chat_id = ? AND is_bot = 0 ORDER BY user_id",
            (chat_id,),
        ) as cursor:
            return await cursor.fetchall()


async def set_username(chat_id: int, user_id: int, username):
    """Обновляет ник участника (после проверки членства на старте)."""
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute(
                "UPDATE chat_members SET username = ? WHERE chat_id = ? AND user_id = ?",
                (clean_username(username), chat_id, user_id),
            )
            await db.commit()


async def backfill_from_stats(chat_id: int):
    """Добавляет в реестр участников, оставивших след в истории, но ещё не известных."""
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO chat_members (chat_id, user_id, user_name, username, is_bot, last_seen)
                SELECT ?, user_id, MAX(user_name), NULL, 0, NULL
                FROM stats_messages
                WHERE chat_id = ? AND user_id IS NOT NULL
                GROUP BY user_id
                """,
                (chat_id, chat_id),
            )
            await db.commit()

