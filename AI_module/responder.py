import logging

from AI_module import llm, memory, prompts

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 100


async def respond(chat_id: int, bot_name: str, bot_username: str) -> str:
    """Генерирует ответ бота в контексте истории, саммари и личности чата."""
    summary = await memory.get_summary(chat_id)
    personality = (
        await memory.get_personality(chat_id) or prompts.load("personality_default")
    )
    rows = await memory.get_recent_messages(chat_id, limit=HISTORY_LIMIT)

    system_prompt = prompts.render(
        "system",
        bot_name=bot_name,
        bot_username=bot_username,
        personality=personality,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"Краткое содержание прошлых бесед:\n{summary}"},
    ]
    for role, name, text in rows:
        content = f"{name}: {text}" if role == "user" else text
        messages.append({"role": role, "content": content})
    messages.append({"role": "system", "content": prompts.load("responder")})

    try:
        return await llm.chat(
            messages,
            temperature=0.7,
            max_tokens=400,
            chat_id=chat_id,
            tag="responder",
        )
    except Exception:
        logger.exception("Ошибка генерации ответа")
        return "Ой, что-то мои нейроны заклинило... Повтори еще раз?"
