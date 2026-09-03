#Сборка сообщений-упоминаний для команд /all и /tag.
#Участник с ником упоминается как «@ник» (сущность mention), участник без ника —
#по user_id через сущность text_mention. Сообщения длиннее лимита Telegram
#разбиваются на несколько, offsets сущностей считаются заново в каждом.
from aiogram.types import MessageEntity, User

MAX_TEXT_LENGTH = 4000


def _member_text(user_id: int, user_name: str | None, username: str | None):
    """Возвращает (текст фрагмента, тип сущности, user для text_mention)."""
    if username:
        return "@" + username, "mention", None
    name = user_name or "участник"
    user = User(id=user_id, is_bot=False, first_name=name)
    return name, "text_mention", user


def _group_fragments(fragments, weight, gap):
    """Группирует фрагменты так, чтобы склейка каждой группы не превышала лимит.

    weight(fragment) — длина фрагмента, gap — длина разделителя между фрагментами.
    """
    groups = []
    current = []
    length = 0
    for fragment in fragments:
        addition = weight(fragment) + (gap if current else 0)
        if current and length + addition > MAX_TEXT_LENGTH:
            groups.append(current)
            current = []
            length = 0
            addition = weight(fragment)
        current.append(fragment)
        length += addition
    if current:
        groups.append(current)
    return groups


def chunk_text_lines(lines) -> list:
    """Список сообщений из строк: каждая склейка строк по '\n' в пределах лимита."""
    return ["\n".join(group) for group in _group_fragments(lines, len, 1)]


def build_chunks(members):
    """Список сообщений-упоминаний: кортежи (text, entities).

    members — кортежи (user_id, user_name, username).
    """
    segments = [_member_text(user_id, user_name, username) for user_id, user_name, username in members]
    chunks = []
    for group in _group_fragments(segments, lambda segment: len(segment[0]), 1):
        text = " ".join(segment[0] for segment in group)
        entities = []
        offset = 0
        for segment in group:
            if entities:
                offset += 1
            fragment, kind, user = segment
            entities.append(MessageEntity(type=kind, offset=offset, length=len(fragment), user=user))
            offset += len(fragment)
        chunks.append((text, entities))
    return chunks


def describe_members(members) -> str:
    """Имена участников для списков тегов.

    @-упоминания допустимы только в тегающих сообщениях; в списках участники
    показываются обычными именами, чтобы никого не отвлекать.
    """
    descriptions = []
    for _, user_name, username in members:
        if user_name:
            descriptions.append(user_name)
        elif username:
            # Внешний участник, известный только по нику: ник без «@» — не упоминание.
            descriptions.append(username)
        else:
            descriptions.append("участник")
    return ", ".join(descriptions)
