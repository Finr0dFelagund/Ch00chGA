#Инструмент событий участников чата (вход/выход) для остальных модулей бота.
#Роутеры и нормализация живут здесь; пакет group_tag (и будущие функции, например
#поздравления) подписывается на события через add_join_listener/add_left_listener.
#Источники: апдейт chat_member (супергруппы, бот — администратор) и сервисные
#сообщения new_chat_members/left_chat_member (обычные группы).
import logging
from dataclasses import dataclass

from aiogram import Router, types
from aiogram.filters.base import Filter
from aiogram.filters.chat_member_updated import (
    ChatMemberUpdatedFilter,
    JOIN_TRANSITION,
    LEAVE_TRANSITION,
)

logger = logging.getLogger(__name__)

router = Router()

_CHAT_TYPES = ("group", "supergroup")


@dataclass
class MemberEvent:
    """Нормализованное событие входа/выхода участника чата."""
    chat_id: int
    chat_type: str
    user_id: int
    user_name: str | None
    username: str | None
    is_bot: bool


_join_listeners = []
_left_listeners = []


def add_join_listener(func):
    """Регистрирует асинхронный обработчик входа участника."""
    _join_listeners.append(func)
    return func


def add_left_listener(func):
    """Регистрирует асинхронный обработчик выхода участника."""
    _left_listeners.append(func)
    return func


async def _dispatch(listeners, event: MemberEvent):
    """Передаёт событие подписчикам; каждая ошибка изолируется."""
    if event.is_bot:
        # Боты (включая самого себя) как «участники» подписчикам не интересны.
        return
    for listener in list(listeners):
        try:
            await listener(event)
        except Exception:
            logger.exception("Ошибка обработчика события участника %s", event.user_id)


def _event(user: types.User, chat: types.Chat) -> MemberEvent:
    """Собирает MemberEvent из пользователя и чата апдейта."""
    return MemberEvent(
        chat_id=chat.id,
        chat_type=chat.type,
        user_id=user.id,
        user_name=user.full_name,
        username=user.username,
        is_bot=user.is_bot,
    )


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def _member_joined(update: types.ChatMemberUpdated):
    """Обрабатывает вход участника в групповой чат."""
    if update.chat.type in _CHAT_TYPES:
        await _dispatch(_join_listeners, _event(update.new_chat_member.user, update.chat))


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def _member_left(update: types.ChatMemberUpdated):
    """Обрабатывает выход участника из группового чата."""
    if update.chat.type in _CHAT_TYPES:
        await _dispatch(_left_listeners, _event(update.new_chat_member.user, update.chat))


class _MemberServiceMessage(Filter):
    """Сервисное сообщение группы о добавлении или выходе участника."""

    async def __call__(self, message: types.Message) -> bool:
        """True для сервисного сообщения о входе или выходе участников."""
        return bool(message.new_chat_members) or bool(message.left_chat_member)


@router.message(_MemberServiceMessage())
async def _member_service_message(message: types.Message):
    """Обрабатывает сервисные сообщения о входе и выходе участников."""
    if message.chat.type not in _CHAT_TYPES:
        return
    for user in message.new_chat_members or ():
        await _dispatch(_join_listeners, _event(user, message.chat))
    if message.left_chat_member:
        await _dispatch(_left_listeners, _event(message.left_chat_member, message.chat))
