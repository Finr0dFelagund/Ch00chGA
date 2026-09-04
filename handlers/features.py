#Глобальные разрешения функций (filters/handlers.txt) и их состояние по чатам.
#Строка без # в файле — функция разрешена; закомментированная — запрещена везде
#и не может быть включена командой ни в одном чате.
import aiosqlite
from AI_module import database, memory
from filters.filters import read_filter_lines

HANDLERS_PATH = "filters/handlers.txt"

#Реестр известных функций: внутреннее имя (как в handlers.txt) и описание для статуса.
FEATURES = {
    "youtube": "скачивание видео с YouTube",
    "tiktok": "скачивание видео с TikTok",
    "pornhub": "скачивание видео с PornHub",
    "bug": "реакция на слово «баг»",
    "AI_chating_responce": "генерация ответов в беседе",
    "AI_chating_memory": "запоминание истории беседы",
    "transliterate_auto": "автоисправление раскладки",
    "stats": "статистика бота",
    "group_tag_all": "тег /all — всех участников чата",
    "group_tag": "группы участников /tag",
    "birthdays": "поздравления с днём рождения",
}

_LOWER_TO_NAME = {name.lower(): name for name in FEATURES}

_allowed = frozenset()
_disabled = {}


def _canonical(feature: str):
    """Каноническое имя функции либо None для неизвестного имени."""
    return _LOWER_TO_NAME.get(feature.strip().lower())


def allowed_features() -> tuple:
    """Функции, разрешённые файлом handlers.txt глобально."""
    return tuple(_allowed)


def is_allowed(feature: str) -> bool:
    """Разрешена ли функция файлом handlers.txt (не зависит от чата)."""
    name = _canonical(feature)
    return name is not None and name in _allowed


def is_enabled(chat_id: int, feature: str) -> bool:
    """Активна ли функция в чате: запрет из файла приоритетнее выбора чата."""
    name = _canonical(feature)
    if name is None or name not in _allowed:
        return False
    return name not in _disabled.get(chat_id, ())


def status(chat_id: int):
    """Состояние всех функций для чата: список (имя, описание, 'on'|'off'|'forbidden')."""
    disabled = _disabled.get(chat_id, ())
    result = []
    for name, description in FEATURES.items():
        if name not in _allowed:
            state = "forbidden"
        elif name in disabled:
            state = "off"
        else:
            state = "on"
        result.append((name, description, state))
    return result


async def load_state():
    """Перечитывает handlers.txt и чат-настройки из БД в память (вызов при старте)."""
    global _allowed, _disabled
    names = []
    for line in read_filter_lines(HANDLERS_PATH):
        name = _canonical(line)
        if name is not None:
            names.append(name)
    _allowed = frozenset(names)
    _disabled = {}
    async with aiosqlite.connect(database.DB_NAME) as db:
        async with db.execute(
            "SELECT chat_id, feature FROM chat_disabled_features"
        ) as cursor:
            rows = await cursor.fetchall()
    for chat_id, feature in rows:
        _disabled.setdefault(chat_id, set()).add(feature)


async def set_chat_feature(chat_id: int, feature: str, enabled: bool):
    """Включает или выключает функцию в чате. Возвращает (ok, имя_или_причина)."""
    name = _canonical(feature)
    if name is None:
        return False, f"Нет такой функции: {feature}."
    if name not in _allowed:
        return False, f"{name} запрещена глобально в {HANDLERS_PATH} — включить нельзя."
    #Сериализация в рамках чата: БД и кэш обновляются атомарно (per-chat лок из AI_module.memory)
    async with memory.chat_lock(chat_id):
        async with aiosqlite.connect(database.DB_NAME) as db:
            if enabled:
                await db.execute(
                    "DELETE FROM chat_disabled_features WHERE chat_id = ? AND feature = ?",
                    (chat_id, name),
                )
            else:
                await db.execute(
                    "INSERT OR IGNORE INTO chat_disabled_features (chat_id, feature) VALUES (?, ?)",
                    (chat_id, name),
                )
            await db.commit()
        chat_disabled = _disabled.setdefault(chat_id, set())
        if enabled:
            chat_disabled.discard(name)
        else:
            chat_disabled.add(name)
    return True, name
