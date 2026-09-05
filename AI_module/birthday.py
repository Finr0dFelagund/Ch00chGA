#Генерация текста поздравления с днём рождения.
#Контекст: личность чата (chat_meta) и краткое содержание прошлых бесед —
#чтобы поздравление учитывало известные об участнике факты. Расход токенов
#записывается в статистику внутри llm.chat с тегом "birthday".
import logging

from AI_module import llm, memory, prompts

logger = logging.getLogger(__name__)

BIRTHDAY_MAX_TOKENS = 500

_FALLBACK = "{name}, с днём рождения! 🎂 Желаю здоровья, радости и всего самого лучшего!"


async def birthday_text(chat_id: int, *, user_name: str, age: int | None = None) -> str:
    """Возвращает текст поздравления для участника чата."""
    personality = (
        await memory.get_personality(chat_id) or prompts.load("personality_default")
    )
    summary = await memory.get_summary(chat_id)
    if age is not None:
        age_hint = f"Сегодня имениннику исполняется {age}."
    else:
        age_hint = "Возраст неизвестен — не упоминай его."
    user_prompt = prompts.render("birthday", user_name=user_name, age_hint=age_hint)
    messages = [
        {
            "role": "system",
            "content": f"Ты — участник группового чата.\n\nЛичность чата:\n{personality}",
        },
        {"role": "system", "content": f"Краткое содержание прошлых бесед:\n{summary}"},
        {"role": "user", "content": user_prompt},
    ]
    try:
        raw = await llm.chat(
            messages,
            temperature=0.7,
            max_tokens=BIRTHDAY_MAX_TOKENS,
            chat_id=chat_id,
            tag="birthday",
        )
    except Exception:
        logger.exception("Ошибка генерации поздравления")
        return _FALLBACK.format(name=user_name)
    text = raw.strip() if raw else ""
    return text or _FALLBACK.format(name=user_name)
