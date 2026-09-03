#Операции с именованными тегами участников.
#Имя тега хранится как tag_key (нижний регистр); для показа сохраняется исходное
#написание (tag_name). Участники в теге — снимок (user_id, user_name, username)
#на момент добавления; текущий ник при тегании берётся из реестра.
#Участник, известный только по @нику, хранится с user_id = NULL.
#Записывающие операции сериализуются per-chat локом memory.chat_lock.
import time

import aiosqlite

from AI_module import database, memory

#Слова, занятые подкомандами /tag, не могут быть именами тегов.
RESERVED_NAMES = {"create", "list", "clear"}


def tag_key(tag_name: str) -> str:
    return tag_name.strip().lower()


async def create_tag(chat_id: int, tag_name: str) -> bool:
    """Создаёт пустой тег. Возвращает False, если тег уже существует."""
    key = tag_key(tag_name)
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            cursor = await db.execute(
                "SELECT 1 FROM chat_tag_meta WHERE chat_id = ? AND tag_key = ?", (chat_id, key)
            )
            exists = await cursor.fetchone()
            if exists:
                return False
            await db.execute(
                "INSERT INTO chat_tag_meta (chat_id, tag_key, tag_name, created_ts) VALUES (?, ?, ?, ?)",
                (chat_id, key, tag_name.strip(), time.time()),
            )
            await db.commit()
    return True


async def delete_tag(chat_id: int, tag_name: str) -> bool:
    """Удаляет тег вместе с его участниками. Возвращает False, если тега не было."""
    key = tag_key(tag_name)
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            cursor = await db.execute(
                "SELECT 1 FROM chat_tag_meta WHERE chat_id = ? AND tag_key = ?", (chat_id, key)
            )
            exists = await cursor.fetchone()
            if not exists:
                return False
            await db.execute("DELETE FROM chat_tag_meta WHERE chat_id = ? AND tag_key = ?", (chat_id, key))
            await db.execute("DELETE FROM chat_tag_members WHERE chat_id = ? AND tag_key = ?", (chat_id, key))
            await db.commit()
    return True


async def clear_tags(chat_id: int):
    """Удаляет все теги чата (реестр участников /all не трогается)."""
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute("DELETE FROM chat_tag_meta WHERE chat_id = ?", (chat_id,))
            await db.execute("DELETE FROM chat_tag_members WHERE chat_id = ?", (chat_id,))
            await db.commit()


async def add_members(chat_id: int, tag_name: str, members) -> int:
    """Добавляет участников (user_id, user_name, username) в тег.
    Возвращает число добавленных (повторные не считаются)."""
    key = tag_key(tag_name)
    async with memory.chat_lock(chat_id):
        before = await count_members(chat_id, tag_name)
        async with aiosqlite.connect(database.DB_NAME) as db:
            for user_id, user_name, username in members:
                if not user_id:
                    continue
                await db.execute(
                    "INSERT OR IGNORE INTO chat_tag_members "
                    "(chat_id, tag_key, user_id, user_name, username) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, key, user_id, user_name, username),
                )
                if username:
                    # Убираем прежнюю «внешнюю» запись по нику, чтобы не дублировать.
                    await db.execute(
                        "DELETE FROM chat_tag_members WHERE chat_id = ? AND tag_key = ? "
                        "AND user_id IS NULL AND lower(username) = ?",
                        (chat_id, key, username.lower()),
                    )
            await db.commit()
        return await count_members(chat_id, tag_name) - before


async def count_members(chat_id: int, tag_name: str) -> int:
    key = tag_key(tag_name)
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM chat_tag_members WHERE chat_id = ? AND tag_key = ?", (chat_id, key)
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 0


async def remove_members(chat_id: int, tag_name: str, user_ids) -> int:
    """Убирает участников по их id из тега. Возвращает число удалённых."""
    key = tag_key(tag_name)
    removed = 0
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            for user_id in user_ids:
                if user_id:
                    cursor = await db.execute(
                        "DELETE FROM chat_tag_members WHERE chat_id = ? AND tag_key = ? AND user_id = ?",
                        (chat_id, key, user_id),
                    )
                    removed += cursor.rowcount
            await db.commit()
    return removed


async def add_external_handles(chat_id: int, tag_name: str, handles) -> int:
    """Добавляет в тег участников, известных только по @нику (user_id = NULL).
    Возвращает число добавленных (повторные не считаются)."""
    key = tag_key(tag_name)
    added = 0
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            for handle in handles:
                if not handle:
                    continue
                cursor = await db.execute(
                    "SELECT 1 FROM chat_tag_members WHERE chat_id = ? AND tag_key = ? "
                    "AND lower(username) = ?",
                    (chat_id, key, handle.lower()),
                )
                if await cursor.fetchone():
                    continue
                await db.execute(
                    "INSERT INTO chat_tag_members (chat_id, tag_key, user_id, user_name, username) "
                    "VALUES (?, ?, NULL, NULL, ?)",
                    (chat_id, key, handle),
                )
                added += 1
            await db.commit()
    return added


async def remove_external_handles(chat_id: int, tag_name: str, handles) -> int:
    """Убирает из тега участников по @нику. Возвращает число удалённых."""
    key = tag_key(tag_name)
    removed = 0
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            for handle in handles:
                if not handle:
                    continue
                cursor = await db.execute(
                    "DELETE FROM chat_tag_members WHERE chat_id = ? AND tag_key = ? "
                    "AND lower(username) = ?",
                    (chat_id, key, handle.lower()),
                )
                removed += cursor.rowcount
            await db.commit()
    return removed


async def get_tag_members(chat_id: int, tag_name: str):
    """Участники тега: кортежи (user_id, user_name, username)."""
    key = tag_key(tag_name)
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, user_name, username FROM chat_tag_members "
            "WHERE chat_id = ? AND tag_key = ? ORDER BY user_id",
            (chat_id, key),
        ) as cursor:
            return await cursor.fetchall()


async def tag_exists(chat_id: int, tag_name: str) -> bool:
    key = tag_key(tag_name)
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT 1 FROM chat_tag_meta WHERE chat_id = ? AND tag_key = ?", (chat_id, key)
        ) as cursor:
            return await cursor.fetchone() is not None


async def list_tags(chat_id: int):
    """Все теги чата: список (tag_name, [(user_id, user_name, username), ...])
    в порядке создания."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT tag_key, tag_name FROM chat_tag_meta WHERE chat_id = ? ORDER BY created_ts, tag_key",
            (chat_id,),
        ) as cursor:
            meta = await cursor.fetchall()
        result = []
        for key, name in meta:
            async with db.execute(
                "SELECT user_id, user_name, username FROM chat_tag_members "
                "WHERE chat_id = ? AND tag_key = ? ORDER BY user_id",
                (chat_id, key),
            ) as cursor:
                members = await cursor.fetchall()
            result.append((name, members))
    return result
