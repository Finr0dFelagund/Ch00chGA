#Запись событий статистики. Сбор никогда не должен ломать основную логику бота,
#поэтому все ошибки записи глушатся и логируются в консоль.
import time
import aiosqlite
from AI_module import database

#Теги LLM-функций для учёта токенов
TAG_DECISION = "decision"
TAG_RESPONDER = "responder"
TAG_SUMMARIZER = "summarizer"
TAG_LAYOUT = "layout"

#Статусы скачивания видео
VIDEO_OK = "ok"
VIDEO_DOWNLOAD_ERROR = "download_error"
VIDEO_SEND_ERROR = "send_error"


async def _insert(sql: str, params: tuple):
    try:
        async with aiosqlite.connect(database.DB_NAME) as db:
            await db.execute(sql, params)
            await db.commit()
    except Exception as e:
        print(f"Ошибка записи статистики: {e}")


async def record_message(chat_id: int, user_id=None, user_name=None, is_command=False):
    """Событие «сообщение обработано монитором группы»."""
    await _insert(
        "INSERT INTO stats_messages (ts, chat_id, user_id, user_name, is_command) VALUES (?, ?, ?, ?, ?)",
        (time.time(), chat_id, user_id, user_name, int(bool(is_command))),
    )


async def record_command(chat_id: int, user_id=None, command: str = ""):
    """Событие «вызвана команда»."""
    await _insert(
        "INSERT INTO stats_commands (ts, chat_id, user_id, command) VALUES (?, ?, ?, ?)",
        (time.time(), chat_id, user_id, command),
    )


async def record_decision(chat_id: int, should: bool, reason: str):
    """Итоговое решение фильтра «отвечать/молчать» по сообщению."""
    await _insert(
        "INSERT INTO stats_decisions (ts, chat_id, should, reason) VALUES (?, ?, ?, ?)",
        (time.time(), chat_id, int(bool(should)), reason or ""),
    )


async def record_video(chat_id: int, platform: str, status: str, user_id=None, user_name=None):
    """Исход попытки скачивания/отправки видео."""
    await _insert(
        "INSERT INTO stats_videos (ts, chat_id, user_id, user_name, platform, status) VALUES (?, ?, ?, ?, ?, ?)",
        (time.time(), chat_id, user_id, user_name, platform, status),
    )


async def record_llm_usage(chat_id, tag: str, prompt_tokens: int, completion_tokens: int):
    """Расход токенов одним LLM-запросом (chat_id может отсутствовать)."""
    await _insert(
        "INSERT INTO stats_llm_usage (ts, chat_id, tag, prompt_tokens, completion_tokens) VALUES (?, ?, ?, ?, ?)",
        (time.time(), chat_id, tag, prompt_tokens, completion_tokens),
    )
