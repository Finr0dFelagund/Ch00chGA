from AI_module import prompts, llm, memory

COMPRESS_THRESHOLD = 100
COMPRESS_BATCH = 50


async def maybe_compress(chat_id: int):
    if await memory.count_messages(chat_id) < COMPRESS_THRESHOLD:
        return

    old = await memory.get_oldest_messages(chat_id, limit=COMPRESS_BATCH)
    if not old:
        return
    current_summary = await memory.get_summary(chat_id)

    history_chunk = "\n".join(f"{name}: {text}" for _, name, text in old)
    prompt = prompts.render(
        "summarizer",
        summary=current_summary,
        messages=history_chunk,
    )
    try:
        new_summary = await llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            chat_id=chat_id,
            tag="summarizer",
        )
    except Exception as e:
        print(f"Ошибка сжатия истории: {e}")
        return

    if not new_summary.strip():
        print("Сжатие истории: пустой ответ, пропуск.")
        return

    await memory.commit_compression(chat_id, [msg[0] for msg in old], new_summary.strip())