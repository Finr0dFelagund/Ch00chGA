#Пакет групповых тегов участников: команды /all и /tag.
#События входа/выхода участников берутся из инструмента handlers.member_events
#(подписка — attach_events), реестр /all пополняется сообщениями через note_user.
from group_tag.db import init_db
from group_tag.commands import router
from group_tag.reconcile import reconcile
from group_tag.registry import note_user
from handlers.member_events import add_join_listener, add_left_listener

_events_attached = False


async def _on_member_join(event):
    """Добавляет вошедшего участника в реестр чата."""
    # Реестр пополняется только людьми: ботов исключает handlers.member_events.
    from group_tag import registry

    await registry.add_from_event(event.chat_id, event.user_id, event.user_name, event.username)


async def _on_member_left(event):
    """Убирает вышедшего участника из реестра и всех его тегов."""
    from group_tag import registry

    await registry.remove_user(event.chat_id, event.user_id)


def attach_events():
    """Подписывает пакет на события входа/выхода участников чата."""
    global _events_attached
    if _events_attached:
        return
    add_join_listener(_on_member_join)
    add_left_listener(_on_member_left)
    _events_attached = True


__all__ = [
    "init_db",
    "router",
    "reconcile",
    "note_user",
    "attach_events",
]
