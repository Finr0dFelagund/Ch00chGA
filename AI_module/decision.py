import logging
import re

from AI_module import llm, memory, prompts

logger = logging.getLogger(__name__)

DECISION_LIMIT = 10
DECISION_MAX_TOKENS = 20
MAX_DECISION_TRIES = 3


async def should_respond(chat_id: int, bot_name: str, bot_username: str):
    """Решение «отвечать или нет»: пара (флаг, причина)."""
    rows = await memory.get_recent_messages(chat_id, limit=DECISION_LIMIT)
    if not rows:
        return False, "no_history"

    system = prompts.render("decision", bot_name=bot_name, bot_username=bot_username)
    messages = [{"role": "system", "content": system}]
    for role, name, text in rows:
        content = f"{name}: {text}" if role == "user" else text
        messages.append({"role": role, "content": content})

    tries = MAX_DECISION_TRIES
    should, reason = False, "parse_failed"
    while tries > 0:
        try:
            raw = await llm.chat(
                messages,
                temperature=0,
                max_tokens=DECISION_MAX_TOKENS,
                chat_id=chat_id,
                tag="decision",
            )
        except Exception:
            logger.exception("Ошибка фильтра решения")
            return False, "error"

        should, reason = parse_decision(raw)
        logger.info(
            "[decision] chat=%s |%s| should_respond=%s reason=%s",
            chat_id,
            MAX_DECISION_TRIES - tries + 1,
            should,
            reason,
        )

        tries -= 1
        if reason != "parse_failed":
            break
    return should, reason

def parse_decision(text: str):
    """Разбирает ответ модели: слово «да/нет» либо набор таких слов в тексте."""
    if not text:
        return False, "empty"

    cleaned = text.strip()
    if not cleaned:
        return False, "empty"

    first = cleaned.split()[0].strip(".,;:!?-_\"'").lower()
    if first in ("да", "yes", "true", "1"):
        return True, cleaned
    if first in ("нет", "no", "false", "0"):
        return False, cleaned

    tokens = set(re.findall(r"[а-яa-z0-9]+", cleaned.lower()))
    has_yes = {"да", "yes", "true"}.intersection(tokens)
    has_no = {"нет", "no", "false"}.intersection(tokens)
    if has_yes and not has_no:
        return True, cleaned
    if has_no:
        return False, cleaned

    return False, "parse_failed"
