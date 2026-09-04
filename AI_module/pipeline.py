from aiogram.enums import MessageEntityType
from AI_module import memory, decision, responder, summarizer, link_reader
import stats


def _bot_mentioned(message, bot_username: str) -> bool:
    if not bot_username:
        return False
    text = message.text or ""
    if f"@{bot_username}".lower() in text.lower():
        return True
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.MENTION:
                mention = text[entity.offset : entity.offset + entity.length]
                if mention.lower() == f"@{bot_username}".lower():
                    return True
    return False


async def run_pipeline(message, bot, *, memory_on: bool, response_on: bool, links_on: bool = False):
    if not memory.should_store_message(message):
        return

    chat_id = message.chat.id
    async with memory.chat_lock(chat_id):
        bot_user = await bot.get_me()
        bot_name = bot_user.first_name
        bot_username = bot_user.username
        user_name = message.from_user.full_name if message.from_user else "unknown"

        if memory_on:
            #Ссылки читаются только при включённой функции links (и при включённой
            #памяти — иначе нечего сохранять); обогащённый текст остаётся в истории
            #и попадает в контекст decision и responder.
            text = message.text
            if links_on:
                text = await link_reader.enrich_message_text(message)
            await memory.append_message(chat_id, "user", user_name, text)

        if response_on:
            if _bot_mentioned(message, bot_username):
                should, reason = True, "mention"
            else:
                should, reason = await decision.should_respond(chat_id, bot_name, bot_username)
            await stats.record_decision(chat_id, should, reason)

            if should:
                text = await responder.respond(chat_id, bot_name, bot_username)
                if text and text.strip():
                    text = text.strip()
                    await message.reply(text)
                    if memory_on:
                        await memory.append_message(chat_id, "assistant", bot_name, text)
                else:
                    print(f"[pipeline] chat={chat_id} пустой ответ (reason={reason})")

        if memory_on:
            await summarizer.maybe_compress(chat_id)