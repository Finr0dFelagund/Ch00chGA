import asyncio
import logging
import time

import aiosqlite

from AI_module import database

logger = logging.getLogger(__name__)

_chat_locks = {}

#Сериализация обращений в рамках одного чата
def chat_lock(chat_id: int) -> asyncio.Lock:
    """Возвращает лок чата для сериализации обращений к его данным."""
    if chat_id not in _chat_locks:
        _chat_locks[chat_id] = asyncio.Lock()
    return _chat_locks[chat_id]


def should_store_message(message) -> bool:
    """True, если текст сообщения стоит сохранить в историю чата."""
    text = getattr(message, "text", None)
    if not text or not text.strip():
        return False
    if text.lstrip().startswith("/"):
        return False
    return True


async def append_message(chat_id: int, role: str, user_name: str, text: str):
    """Добавляет сообщение в историю и обновляет время активности чата."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        await db.execute(
            "INSERT INTO chat_history (chat_id, role, user_name, text) VALUES (?, ?, ?, ?)",
            (chat_id, role, user_name, text),
        )
        await db.execute(
            "INSERT INTO chat_meta (chat_id, last_message_time) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET last_message_time = ?",
            (chat_id, time.time(), time.time()),
        )
        await db.commit()


async def count_messages(chat_id: int) -> int:
    """Число сообщений в истории чата."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM chat_history WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 0


async def get_recent_messages(chat_id: int, limit: int = 100):
    """Последние сообщения чата в хронологическом порядке."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT role, user_name, text FROM chat_history "
            "WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return list(reversed(rows))


async def get_oldest_messages(chat_id: int, limit: int = 50):
    """Старые сообщения чата (до limit) — кандидаты на сжатие в саммари."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT id, user_name, text FROM chat_history "
            "WHERE chat_id = ? ORDER BY id ASC LIMIT ?",
            (chat_id, limit),
        ) as cursor:
            return await cursor.fetchall()


async def get_summary(chat_id: int) -> str:
    """Саммари чата либо заглушка для пустой истории."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT summary FROM chat_meta WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row and row[0]:
        return row[0]
    return "История пуста. Диалог только начался."


async def commit_compression(chat_id: int, ids, summary: str):
    """Удаляет сжатые сообщения и сохраняет новое саммари в одной транзакции."""
    if not ids:
        return
    placeholders = ",".join(["?"] * len(ids))
    db = await aiosqlite.connect(database.DB_NAME)
    try:
        await db.execute(
            f"DELETE FROM chat_history WHERE chat_id = ? AND id IN ({placeholders})",
            (chat_id, *ids),
        )
        await db.execute(
            "INSERT INTO chat_meta (chat_id, summary) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET summary = excluded.summary",
            (chat_id, summary),
        )
        await db.commit()
    except Exception:
        logger.exception("Ошибка транзакции сжатия")
        await db.rollback()
    finally:
        await db.close()


async def get_personality(chat_id: int) -> str:
    """Личность чата либо пустая строка, если она не задана."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT personality FROM chat_meta WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row and row[0]:
        return row[0]
    return ""


async def set_personality(chat_id: int, personality: str) -> str:
    """Сохраняет личность чата и возвращает её."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        await db.execute(
            "INSERT INTO chat_meta (chat_id, personality) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET personality = ?",
            (chat_id, personality.strip(), personality.strip()),
        )
        await db.commit()
    return personality.strip()


async def clear_history(chat_id: int):
    """Очищает историю чата и сбрасывает саммари."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        await db.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
        await db.execute("UPDATE chat_meta SET summary = '' WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def delete_last_messages(chat_id: int, limit: int):
    """Удаляет последние limit сообщений истории чата."""
    if limit <= 0:
        return
    async with aiosqlite.connect(database.DB_NAME) as db:
        await db.execute(
            "DELETE FROM chat_history WHERE id IN ("
            "SELECT id FROM chat_history WHERE chat_id = ? ORDER BY id DESC LIMIT ?)",
            (chat_id, limit),
        )
        await db.commit()
