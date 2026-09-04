#Сборка упоминания участника в начале сообщений пакета дней рождения.
#Участник с ником упоминается как «@ник» (сущность mention), без ника — по
#user_id сущностью text_mention (видимый текст — имя).
from aiogram.types import MessageEntity, User


def build(user_id: int, user_name=None, username=None):
    """Возвращает (текст-упоминание, сущность) для начала сообщения."""
    if username:
        text = "@" + username
        return text, MessageEntity(type="mention", offset=0, length=len(text))
    name = user_name or "участник"
    user = User(id=user_id, is_bot=False, first_name=name)
    return name, MessageEntity(type="text_mention", offset=0, length=len(name), user=user)
