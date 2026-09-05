#Полуночный воркер поздравлений и отправка сообщений.
#При старте бота (в день рождения, если ещё не поздравлял) и далее каждую
#локальную полночь выбирает именинников дня без отметки notified_year и публикует
#поздравление: упоминание участника + текст, сгенерированный AI_module.
import asyncio
import datetime
import logging

from aiogram import Bot

from AI_module import birthday_text
from birthdays import db, mention
from group_tag import registry
from handlers import features

logger = logging.getLogger(__name__)

MAX_MESSAGE_TEXT = 4000


def _seconds_until_next_midnight() -> float:
    """Секунды до ближайшей полуночи по локальному времени."""
    now = datetime.datetime.now()
    next_midnight = (now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()


async def _fresh_profile(chat_id, user_id, snap_name, snap_username):
    """Актуальные (имя, ник) из реестра участников либо снапшот записи."""
    for row in await registry.list_members(chat_id):
        if row[0] == user_id:
            return row[1] or snap_name, row[2] or snap_username
    return snap_name, snap_username


async def _send_greeting(bot: Bot, row):
    """Отправляет поздравление участнику и отмечает год поздравления."""
    chat_id, user_id, snap_name, snap_username, year, _ = row
    user_name, username = await _fresh_profile(chat_id, user_id, snap_name, snap_username)
    age = None
    if year:
        age = datetime.date.today().year - year
        if not 1 <= age <= 120:
            age = None
    text = await birthday_text(chat_id, user_name=user_name or "друг", age=age)
    fragment, entity = mention.build(user_id, user_name, username)
    body = f"{fragment} 🎂\n{text}"
    if len(body) > MAX_MESSAGE_TEXT:
        limit = MAX_MESSAGE_TEXT - len(fragment) - 3
        body = f"{fragment} 🎂\n{text[:limit].rsplit(' ', 1)[0]}"
    await bot.send_message(chat_id, body, entities=[entity])


async def _greet_due(bot: Bot):
    """Поздравляет именинников текущего дня, которых ещё не поздравлял."""
    today = datetime.date.today()
    for row in await db.get_today(today.month, today.day):
        chat_id, user_id, _, _, _, notified_year = row
        if notified_year == today.year:
            continue
        if not features.is_enabled(chat_id, "birthdays"):
            continue
        try:
            await _send_greeting(bot, row)
        except Exception:
            logger.exception("Ошибка поздравления участника %s в чате %s", user_id, chat_id)
            continue
        await db.mark_notified(chat_id, user_id, today.year)


async def run_worker(bot: Bot):
    """Цикл воркера: поздравление при старте, затем каждую локальную полночь."""
    while True:
        await _greet_due(bot)
        await asyncio.sleep(_seconds_until_next_midnight())
