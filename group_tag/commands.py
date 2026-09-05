#Команды тегания участников: /all и /tag.
#Тогглы разделены: group_tag_all управляет /all (и голым /tag как его эквивалентом),
#group_tag — созданием, изменением и теганием именованных групп.
from aiogram import Router, types
from aiogram.filters import Command

from handlers import features
from stats import record_command
from group_tag import registry, tags, mentions

router = Router()

GROUP_TYPES = ("group", "supergroup")
FORMAT_HINT = (
    "/tag create <имя> [@ник1, @ник2 ...] — создать тег.\n"
    "/tag <имя> — тегнуть участников тега.\n"
    "/tag <имя> add [@ник ...] — добавить участников (без списка — всех из чата).\n"
    "/tag <имя> remove [@ник ...] — убрать участников (без списка — удалить тег).\n"
    "/tag list — показать все теги.\n"
    "/tag clear — удалить все теги чата."
)


def _is_group(message) -> bool:
    """True для групповых чатов (group/supergroup)."""
    return message.chat.type in GROUP_TYPES


def _user_id(message):
    """Идентификатор автора сообщения либо None."""
    return message.from_user.id if message.from_user else None


def _tail(message) -> str:
    """Хвост команды: всё после первого слова команды."""
    _, _, tail = (message.text or "").partition(" ")
    return tail.strip()


async def _need_feature(message, feature: str) -> bool:
    """Проверяет включённость функции в чате и сообщает об отказе."""
    if features.is_enabled(message.chat.id, feature):
        return True
    if features.is_allowed(feature):
        await message.reply("Эта функция выключена в этом чате (/features).")
    else:
        await message.reply("Эта функция запрещена глобально в filters/handlers.txt.")
    return False


async def _reply_long(message, text: str):
    """Отправляет длинный текст сообщениями в пределах лимита Telegram."""
    if not text:
        return
    for part in mentions.chunk_text_lines(text.split("\n")):
        await message.answer(part)


async def _send_mentions(message, members):
    """Отправляет сообщение с упоминаниями участников."""
    chunks = mentions.build_chunks(members)
    for text, entities in chunks:
        await message.answer(text, entities=entities or None)


async def _member_handles(tokens):
    """Разбирает список участников: возвращает (ник_без_@, был_ли_указан_@).

    Разделители — пробелы и запятые.
    """
    entries = []
    for token in tokens:
        for part in token.split(","):
            part = part.strip()
            if not part:
                continue
            mentioned = part.startswith("@")
            clean = part.lstrip("@").strip()
            if clean:
                entries.append((clean, mentioned))
    return entries


async def _resolve_members(chat_id, entries):
    """Ищет участников реестра по нику или имени.

    Возвращает (найденные, неразрешённые) — неразрешённые это кортежи
    (ник_без_@, был_ли_указан_@).
    """
    members = await registry.list_members(chat_id)
    by_username = {}
    by_name = {}
    for user_id, user_name, username in members:
        if username:
            by_username[username.lower()] = (user_id, user_name, username)
        if user_name:
            by_name.setdefault(user_name.lower(), (user_id, user_name, username))
    found = []
    unresolved = []
    seen_ids = set()
    seen_handles = set()
    for handle, mentioned in entries:
        key = handle.lower()
        if key in seen_handles:
            continue
        seen_handles.add(key)
        match = by_username.get(key) or by_name.get(key)
        if match is None:
            unresolved.append((handle, mentioned))
            continue
        if match[0] in seen_ids:
            continue
        seen_ids.add(match[0])
        found.append(match)
    return found, unresolved


def _split_unresolved(unresolved):
    """Делит неразрешённых на @ники (можно хранить и тегать по нику) и прочее."""
    handles = [handle for handle, mentioned in unresolved if mentioned]
    missing = [handle for handle, mentioned in unresolved if not mentioned]
    return handles, missing


async def _tag_all(message):
    """Эквивалент /all: тегает всех известных участников чата."""
    if not await _need_feature(message, "group_tag_all"):
        return
    members = await registry.list_members(message.chat.id)
    if not members:
        await message.reply("Пока некого тегать — пусть кто-нибудь напишет в чат.")
        return
    await _send_mentions(message, members)


@router.message(Command("all"))
async def all_command(message: types.Message):
    """Тегает всех известных боту участников чата (/all)."""
    if not _is_group(message):
        return
    await record_command(message.chat.id, _user_id(message), "all")
    await _tag_all(message)


async def _do_create(message, tokens):
    """Создаёт именованный тег с переданными участниками."""
    if not tokens:
        await message.reply("Имя тега не указано.\n" + FORMAT_HINT)
        return
    name = tokens[0]
    if tags.tag_key(name) in tags.RESERVED_NAMES:
        await message.reply(f"«{name}» — зарезервированное слово, так тег не назвать.")
        return
    if not await tags.create_tag(message.chat.id, name):
        await message.reply(f"Тег «{name}» уже есть.")
        return
    entries = await _member_handles(tokens[1:])
    if not entries:
        await message.reply(f"Создал пустой тег «{name}». Участников добавишь через /tag {name} add.")
        return
    found, unresolved = await _resolve_members(message.chat.id, entries)
    added = await tags.add_members(message.chat.id, name, found)
    handles, missing = _split_unresolved(unresolved)
    if handles:
        added += await tags.add_external_handles(message.chat.id, name, handles)
    reply = f"Создал тег «{name}»: добавлено {added}."
    if missing:
        reply += "\nНе нашёл в чате: " + ", ".join(missing)
    await message.reply(reply)


async def _do_list(message):
    """Показывает все теги чата."""
    rows = await tags.list_tags(message.chat.id)
    if not rows:
        await message.reply("Тегов пока нет.\n" + FORMAT_HINT)
        return
    lines = ["Теги чата:"]
    for name, members in rows:
        lines.append(f"• {name} ({len(members)}): {mentions.describe_members(members)}")
    await _reply_long(message, "\n".join(lines))


async def _do_tag_members(message, name):
    """Тегает участников именованного тега."""
    if not await tags.tag_exists(message.chat.id, name):
        await message.reply(f"Нет тега «{name}».")
        return
    members = await tags.get_tag_members(message.chat.id, name)
    if not members:
        await message.reply(f"В теге «{name}» никого нет.")
        return
    await _send_mentions(message, members)


async def _do_add(message, name, entries):
    """Добавляет участников в тег."""
    if not await tags.tag_exists(message.chat.id, name):
        await message.reply(f"Нет тега «{name}» — сначала /tag create {name}.")
        return
    if not entries:
        members = await registry.list_members(message.chat.id)
        if not members:
            await message.reply("Некого добавлять — в чате пока никого не знаю.")
            return
        added = await tags.add_members(message.chat.id, name, members)
        await message.reply(f"Добавил в «{name}» всех известных участников чата ({added}).")
        return
    found, unresolved = await _resolve_members(message.chat.id, entries)
    added = await tags.add_members(message.chat.id, name, found)
    handles, missing = _split_unresolved(unresolved)
    if handles:
        added += await tags.add_external_handles(message.chat.id, name, handles)
    if not added:
        await message.reply("Никого из перечисленных в чате не нашёл.")
        return
    reply = f"Добавил в «{name}»: {added}."
    if missing:
        reply += "\nНе нашёл в чате: " + ", ".join(missing)
    await message.reply(reply)


async def _do_remove(message, name, entries):
    """Удаляет участников из тега."""
    if not await tags.tag_exists(message.chat.id, name):
        await message.reply(f"Нет тега «{name}».")
        return
    if not entries:
        # Без списка участников — удаление всего тега.
        await tags.delete_tag(message.chat.id, name)
        await message.reply(f"Тег «{name}» удалён.")
        return
    found, unresolved = await _resolve_members(message.chat.id, entries)
    removed = await tags.remove_members(message.chat.id, name, [row[0] for row in found])
    handles, missing = _split_unresolved(unresolved)
    if handles:
        removed += await tags.remove_external_handles(message.chat.id, name, handles)
    if removed:
        reply = f"Убрал из «{name}»: {removed}."
    else:
        reply = "Никого из перечисленных в теге не нашёл."
    if missing:
        reply += "\nНе нашёл в чате: " + ", ".join(missing)
    await message.reply(reply)


async def _do_clear(message):
    """Удаляет все теги чата."""
    await tags.clear_tags(message.chat.id)
    await message.reply("Все теги чата удалены. Реестр /all не тронут.")


@router.message(Command("tag"))
async def tag_command(message: types.Message):
    """Роутер подкоманд /tag."""
    if not _is_group(message):
        return
    await record_command(message.chat.id, _user_id(message), "tag")
    tokens = _tail(message).split()
    if not tokens:
        # Без аргументов /tag эквивалентен /all.
        await _tag_all(message)
        return

    head = tokens[0].lower()
    if head == "create":
        if not await _need_feature(message, "group_tag"):
            return
        await _do_create(message, tokens[1:])
        return
    if head == "list":
        if not await _need_feature(message, "group_tag"):
            return
        await _do_list(message)
        return
    if head == "clear":
        if not await _need_feature(message, "group_tag"):
            return
        await _do_clear(message)
        return

    name = tokens[0]
    if len(tokens) == 1:
        if not await _need_feature(message, "group_tag"):
            return
        await _do_tag_members(message, name)
        return

    operation = tokens[1].lower()
    if operation not in ("add", "remove"):
        await message.reply(FORMAT_HINT)
        return
    if not await _need_feature(message, "group_tag"):
        return
    entries = await _member_handles(tokens[2:])
    if operation == "add":
        await _do_add(message, name, entries)
    else:
        await _do_remove(message, name, entries)
