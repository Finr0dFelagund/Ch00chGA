#Стартовая сверка реестра участников и тегов с реальным членством в чатах.
#Проверка через getChatMember гарантированно работает, если бот — админ
#супергруппы (в обычных группах работает и без админки). При отсутствии прав
#сверка чата пропускается: участники добавляются по следу в истории, а чистка
#уехавших происходит по событиям выхода, когда бот их получает.
import logging

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from AI_module import database
from group_tag import registry

logger = logging.getLogger(__name__)

_NOT_MEMBER = ("left", "kicked")


async def _known_chats():
    """Чаты, для которых у бота есть данные об участниках или истории сообщений."""
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT DISTINCT chat_id FROM chat_members "
            "UNION SELECT DISTINCT chat_id FROM chat_tag_members "
            "UNION SELECT DISTINCT chat_id FROM chat_tag_meta "
            "UNION SELECT DISTINCT chat_id FROM stats_messages"
        ) as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def _verify_members(bot: Bot, chat_id: int) -> bool:
    """Проверяет участников реестра чата, чистит уехавших и ботов.

    Возвращает False, если проверка невозможна (не хватает прав бота).
    """
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, user_name, username, is_bot FROM chat_members WHERE chat_id = ?",
            (chat_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    for user_id, user_name, username, _ in rows:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
        except TelegramBadRequest:
            logger.info("Нет прав для сверки участников чата %s — проверка пропущена", chat_id)
            return False
        user = member.user
        if user.is_bot:
            await registry.remove_user(chat_id, user_id)
            continue
        if member.status in _NOT_MEMBER or (
            member.status == "restricted" and not getattr(member, "is_member", True)
        ):
            await registry.remove_user(chat_id, user_id)
            continue
        if user.username and user.username != username:
            await registry.set_username(chat_id, user_id, user.username)
    return True


async def reconcile(bot: Bot):
    """Стартовая сверка: чистка уехавших, добавление новых по истории сообщений."""
    for chat_id in await _known_chats():
        await _verify_members(bot, chat_id)
        await registry.backfill_from_stats(chat_id)
    logger.info("Стартовая сверка участников завершена")
