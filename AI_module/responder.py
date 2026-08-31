from AI_module import prompts, llm, memory

HISTORY_LIMIT = 100


async def respond(chat_id: int, bot_name: str, bot_username: str) -> str:
    summary = await memory.get_summary(chat_id)
    personality = await memory.get_personality(chat_id) or prompts.load("personality_default")
    rows = await memory.get_recent_messages(chat_id, limit=HISTORY_LIMIT)

    messages = [
        {"role": "system", "content": prompts.render("system", bot_name=bot_name, bot_username=bot_username, personality=personality)},
        {"role": "system", "content": f"Краткое содержание прошлых бесед:\n{summary}"},
    ]
    for role, name, text in rows:
        content = f"{name}: {text}" if role == "user" else text
        messages.append({"role": role, "content": content})
    messages.append({"role": "system", "content": prompts.load("responder")})

    try:
        return await llm.chat(messages, temperature=0.7, max_tokens=400)
    except Exception as e:
        print(f"Ошибка генерации ответа: {e}")
        return "Ой, что-то мои нейроны заклинило... Повтори еще раз?"