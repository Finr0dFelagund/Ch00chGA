from AI_module import prompts, llm, memory

DECISION_LIMIT = 10


async def should_respond(chat_id: int):
    rows = await memory.get_recent_messages(chat_id, limit=DECISION_LIMIT)
    if not rows:
        return False, "no_history"

    messages = [{"role": "system", "content": prompts.load("decision")}]
    for role, name, text in rows:
        content = f"{name}: {text}" if role == "user" else text
        messages.append({"role": role, "content": content})

    try:
        raw = await llm.chat(messages, temperature=0, max_tokens=50)
    except Exception as e:
        print(f"Ошибка фильтра решения: {e}")
        return False, "error"

    should, reason = llm.parse_decision(raw)
    print(f"[decision] chat={chat_id} should_respond={should} reason={reason}")
    return should, reason