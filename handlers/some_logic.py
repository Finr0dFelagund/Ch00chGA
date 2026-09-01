from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.enums import MessageEntityType
from load_video import youtube, tiktok, pornhub
from filters import filters
from filters.filters import get_filter_list
from AI_module import memory, pipeline, prompts
import translating_msgs

# Изолированный роутер для групповых обработчиков
router = Router()

# Хэндлеры на команды
@router.message(Command("help"))
async def chat_help_command(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        await message.reply(
            "Привет! Я твой кастомный помощник.\n"
            "/set_personality [str] - настроить промпт личности для чата.\n"
            "/get_personality - показать текущую личность.\n"
            "/clear - стереть всю память чата.\n"
            "/clear [N] - стереть последние N сообщений.\n"
            "/transliterate [from] [to] [text] - исправить раскладку (ru/en) или перевести в азбуку Морзе (morse).\n"
            "Если текст набран в неправильной раскладке — предложу исправление.\n"
            "Если в сообщении есть ссылка на видео (YouTube, TikTok, PornHub) - скачаю и пришлю.\n"
        )

@router.message(Command("set_personality"))
async def chat_help_command(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        new_prompt = message.text.replace("/set_personality", "").strip()
        if new_prompt:
            await memory.set_personality(chat_id=message.chat.id, personality=new_prompt)
            await message.reply("Частичная лоботомия проведена")
        else:
            await message.reply("А кто указывать промпт будет?")

@router.message(Command("get_personality"))
async def chat_help_command(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        personality = await memory.get_personality(chat_id=message.chat.id) or prompts.load("personality_default")
        await message.reply(personality)

@router.message(Command("clear"))
async def clear_memory_command(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        async with memory.chat_lock(message.chat.id):
            arg = message.text.replace("/clear", "").strip()
            if arg:
                try:
                    count = int(arg)
                except ValueError:
                    await message.reply("А сколько сообщений стереть? Числом.")
                    return
                if count <= 0:
                    await message.reply("Тебе типо новых надо добавить? Так пиши....")
                    return
                await memory.delete_last_messages(message.chat.id, count)
                await message.reply(f"Последние {count} сообщений отлоботомированы.")
            else:
                await memory.clear_history(message.chat.id)
                await message.reply("Ультралоботомия окончена.")

@router.message(Command("transliterate"))
async def transliterate_command(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        in_str = message.text.replace('/transliterate', '').strip()
        if not in_str:
            return await message.reply('А что конкретно сделать??')

        parts = in_str.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply('Аргументов маловато...')
        from_lang, to_lang, text_to_translit = parts
        from_lang = from_lang.lower().strip()
        to_lang = to_lang.lower().strip()
        if from_lang not in ['ru', 'en', 'morse'] or to_lang not in ['ru', 'en', 'morse']:
            return await message.reply('Укажи языки откуда-куда: "en", "ru", "morse"')
        if not text_to_translit or to_lang == from_lang:
            return await message.reply('И что тут переводить??')
        
        if from_lang in ['ru', 'en'] and to_lang in ['ru', 'en']:
            return await message.reply(translating_msgs.change_kb_layout(text_to_translit, 'to_' + to_lang))
        
        if to_lang == 'morse':
            route = to_lang
        elif from_lang == 'morse':
            route = 'lang'
        if 'en' in [to_lang, from_lang]:
            lang = 'en'
        elif 'ru' in [to_lang, from_lang]:
            lang = 'ru'
        return await message.reply(translating_msgs.morse_coding(text_to_translit, lang, route))


#------------------------------
#Функции обработки и общий хэндлер на всё
#Реакция на "баг"
async def check_bug_message(message: types.Message):
    if 'bug' in monitor_group_messages.filter and "баг" in message.text.lower():
        await message.answer(f"🔧 @{message.from_user.username} упомянул баг! Зафиксировано.")
    
#Реакция на любой URL
async def check_URL_message(message: types.Message):
    if not message.entities:
        return
    for entity in message.entities:
        if entity.type == MessageEntityType.URL:
            url_text = message.text[entity.offset : entity.offset + entity.length]
        elif entity.type == MessageEntityType.TEXT_LINK:
            url_text = entity.url
        else:
            continue
        if 'youtube' in monitor_group_messages.filter and filters.check_youtube_URL_message(url_text):
            await youtube.download_youtube_video(url_text, message = message)
        if 'tiktok' in monitor_group_messages.filter and filters.check_tiktok_URL_message(url_text):
            await tiktok.download_tiktok_video(url_text, message = message)
        if 'pornhub' in monitor_group_messages.filter and filters.check_pornhub_URL_message(url_text):
            await pornhub.download_pornhub_video(url_text, message = message)

#Реакция на текст в неправильной раскладке
async def check_wrong_layout(message: types.Message):
    if 'transliterate_auto' in monitor_group_messages.filter:
        corrected = await translating_msgs.auto_correct(message.text)
        if corrected:
            await message.reply(f"Возможно, ты хотел написать: {corrected}")

# Хендлер ловит все сообщения в группе (если выключен Privacy Mode в BotFather)
@router.message()
@get_filter_list("filters/handlers.txt")
async def monitor_group_messages(message: types.Message,  bot: Bot):
    if message.chat.type in ["group", "supergroup"]:
        if 'AI_chating_memory' in monitor_group_messages.filter or 'AI_chating_responce' in monitor_group_messages.filter:
            await pipeline.run_pipeline(
                message,
                bot,
                memory_on='AI_chating_memory' in monitor_group_messages.filter,
                response_on='AI_chating_responce' in monitor_group_messages.filter,
            )
        await check_bug_message(message)
        await check_URL_message(message)
        await check_wrong_layout(message)