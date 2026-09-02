from AI_module import prompts, llm, memory
import re

DECISION_LIMIT = 10
DECISION_MAX_TOKENS = 20
MAX_DECISION_TRIES = 3

async def should_respond(chat_id: int, bot_name: str, bot_username: str):
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
            raw = await llm.chat(messages, temperature=0, max_tokens=DECISION_MAX_TOKENS, chat_id=chat_id, tag="decision")
        except Exception as e:
            print(f"Ошибка фильтра решения: {e}")
            return False, "error"

        should, reason = parse_decision(raw)
        print(f"[decision] chat={chat_id} |{MAX_DECISION_TRIES - tries + 1}| should_respond={should} reason={reason}")

        tries -= 1
        if reason != "parse_failed":
            break
    return should, reason

def parse_decision(text: str):
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
    if {"да", "yes", "true"}.intersection(tokens) and not {"нет", "no", "false"}.intersection(tokens):
        return True, cleaned
    if {"нет", "no", "false"}.intersection(tokens):
        return False, cleaned

    return False, "parse_failed"