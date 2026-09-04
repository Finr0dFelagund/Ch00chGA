#Запрос даты рождения у участников и приём ответа.
#Обработчики входа/выхода — обычные функции модуля: бот фиксируется один раз
#при attach (смена бота в процессе работы не предполагается). Добавление бота
#в новый чат ловится роутером my_chat_member. Приём даты не требует отдельного
#фильтра-роутера: сообщение распознаёт try_answer, вызываемая из монитора
#some_logic (последнего обработчика сообщений).
import logging

from aiogram import Bot, Router, types
from aiogram.filters.chat_member_updated import (
    ChatMemberUpdatedFilter,
    JOIN_TRANSITION,
)

from handlers import features
from handlers.member_events import MemberEvent
from birthdays import db, dates, mention

logger = logging.getLogger(__name__)

router = Router()

GROUP_TYPES = ("group", "supergroup")

_bot = None
#Незакрытые вопросы о дате: (chat_id, user_id). В памяти процесса: после рестарта
#бот не переспрашивает, но продолжает принимать дату через try_answer.
_pending = set()


async def _api_birthday(user_id: int):
    """Дата рождения из приватного чата с пользователем либо None."""
    try:
        chat = await _bot.get_chat(user_id)
    except Exception:
        return None
    return getattr(chat, "birthdate", None)


async def _ask_date(chat_id: int, user_id: int, user_name, username):
    fragment, entity = mention.build(user_id, user_name, username)
    text = (
        f"{fragment}, привет! Я записываю дни рождения участников.\n"
        "Напиши свою дату рождения в формате ДД.ММ или ДД.ММ.ГГГГ — "
        "поздравлю с днём рождения в 00:00. 🎂"
    )
    try:
        await _bot.send_message(chat_id, text, entities=[entity])
    except Exception:
        logger.exception("Не удалось спросить дату рождения у %s в чате %s", user_id, chat_id)


async def on_member_join(event: MemberEvent):
    """Обработчик входа участника: попытка API либо запрос даты."""
    if not features.is_enabled(event.chat_id, "birthdays"):
        return
    if await db.get(event.chat_id, event.user_id) is not None:
        return
    birth = await _api_birthday(event.user_id)
    if birth is not None and getattr(birth, "day", None) and getattr(birth, "month", None):
        await db.save(
            event.chat_id,
            event.user_id,
            day=birth.day,
            month=birth.month,
            year=getattr(birth, "year", None),
            user_name=event.user_name,
            username=event.username,
            source="api",
        )
        return
    if (event.chat_id, event.user_id) in _pending:
        return
    _pending.add((event.chat_id, event.user_id))
    await _ask_date(event.chat_id, event.user_id, event.user_name, event.username)


async def on_member_left(event: MemberEvent):
    """Обработчик выхода участника: очистка данных и незакрытого вопроса."""
    _pending.discard((event.chat_id, event.user_id))
    await db.delete_user(event.chat_id, event.user_id)


async def try_answer(message: types.Message) -> bool:
    """Запоминает дату рождения, если сообщение участника — дата.

    Вызывается из монитора some_logic; возвращает True, если сообщение обработано
    как дата (дальше в обработку не идёт).
    """
    if message.chat.type not in GROUP_TYPES:
        return False
    user = message.from_user
    if not user or user.is_bot or not message.text:
        return False
    if not features.is_enabled(message.chat.id, "birthdays"):
        return False
    parsed = dates.parse(message.text)
    if parsed is None:
        return False
    day, month, year = parsed
    await db.save(
        message.chat.id,
        user.id,
        day=day,
        month=month,
        year=year,
        user_name=user.full_name,
        username=user.username,
        source="manual",
    )
    _pending.discard((message.chat.id, user.id))
    suffix = f".{year}" if year else ""
    await message.reply(f"Записал: {day:02d}.{month:02d}{suffix}. Приду поздравлять! 🎂")
    return True


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def _bot_added(event: types.ChatMemberUpdated, bot: Bot):
    """Бот добавлен в чат: знакомит участников с возможностью записать дату."""
    if event.chat.type not in GROUP_TYPES:
        return
    if not features.is_enabled(event.chat.id, "birthdays"):
        return
    text = (
        "🎂 Я умею поздравлять с днём рождения!\n"
        "Если хочешь поздравлений — напиши мне свою дату в формате ДД.ММ или ДД.ММ.ГГГГ."
    )
    try:
        await bot.send_message(event.chat.id, text)
    except Exception:
        logger.exception("Не удалось опубликовать приветствие в чате %s", event.chat.id)


