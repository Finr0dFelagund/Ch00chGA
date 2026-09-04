#Схема и операции с днями рождения участников (общая SQLite-база проекта).
#notified_year — год, в котором участник уже был поздравлен (не поздравляем дважды).
import aiosqlite

from AI_module import database, memory

_DDL = [
    '''
    CREATE TABLE IF NOT EXISTS chat_birthdays (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        day INTEGER NOT NULL,
        month INTEGER NOT NULL,
        year INTEGER,
        user_name TEXT,
        username TEXT,
        source TEXT NOT NULL DEFAULT 'manual',
        notified_year INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )
    ''',
    'CREATE INDEX IF NOT EXISTS idx_birthdays_day_month ON chat_birthdays(month, day)',
]


def _clean_username(username):
    """Ник без ведущего '@'; None для пустого значения."""
    if not username:
        return None
    value = str(username).strip().lstrip("@")
    return value or None


async def init_db():
    """Создаёт таблицу дней рождения, если её ещё нет."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        for statement in _DDL:
            await db.execute(statement)
        await db.commit()


async def save(chat_id: int, user_id: int, *, day: int, month: int, year=None,
               user_name=None, username=None, source: str = "manual"):
    """Сохраняет или обновляет дату рождения участника чата.

    Отметка notified_year сбрасывается только при изменении самой даты.
    """
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute(
                """
                INSERT INTO chat_birthdays
                    (chat_id, user_id, day, month, year, user_name, username, source, notified_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    day = excluded.day,
                    month = excluded.month,
                    year = excluded.year,
                    user_name = excluded.user_name,
                    username = COALESCE(excluded.username, chat_birthdays.username),
                    source = excluded.source,
                    notified_year = CASE
                        WHEN chat_birthdays.day = excluded.day AND chat_birthdays.month = excluded.month
                        THEN chat_birthdays.notified_year
                        ELSE NULL
                    END
                """,
                (chat_id, user_id, day, month, year, user_name, _clean_username(username), source),
            )
            await db.commit()


async def delete_user(chat_id: int, user_id: int):
    """Удаляет день рождения участника при его выходе из чата."""
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute(
                "DELETE FROM chat_birthdays WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            await db.commit()


async def get(chat_id: int, user_id: int):
    """Запись о дне рождения участника либо None."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT day, month, year, user_name, username, source, notified_year "
            "FROM chat_birthdays WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ) as cursor:
            return await cursor.fetchone()


async def get_today(month: int, day: int):
    """Все записи с указанными месяцем и днём: кортежи
    (chat_id, user_id, user_name, username, year, notified_year)."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT chat_id, user_id, user_name, username, year, notified_year "
            "FROM chat_birthdays WHERE month = ? AND day = ?",
            (month, day),
        ) as cursor:
            return await cursor.fetchall()


async def mark_notified(chat_id: int, user_id: int, year: int):
    """Отмечает участника поздравленным в указанном году."""
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute(
                "UPDATE chat_birthdays SET notified_year = ? WHERE chat_id = ? AND user_id = ?",
                (year, chat_id, user_id),
            )
            await db.commit()
