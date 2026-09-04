#Пакет поздравлений с днём рождения: запрос даты при входе участника (или из API
#приватного чата, когда она доступна) и поздравление в 00:00 текстом AI_module.
from birthdays.db import init_db
from birthdays.ask import router, try_answer
from birthdays.sender import run_worker
from birthdays import ask
from handlers import member_events

_attached = False


def attach(bot):
    """Подписывает пакет на события входа/выхода участников чата.

    Бот фиксируется один раз при старте; смена бота в процессе работы не
    предполагается, поэтому отдельный setter не нужен.
    """
    global _attached
    if _attached:
        return
    ask._bot = bot
    member_events.add_join_listener(ask.on_member_join)
    member_events.add_left_listener(ask.on_member_left)
    _attached = True


__all__ = [
    "init_db",
    "router",
    "try_answer",
    "run_worker",
    "attach",
]
