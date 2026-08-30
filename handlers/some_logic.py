from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.enums import MessageEntityType
from handlers import load_video
from filters import filters
from filters.filters import get_filter_list
from AI_module import memory, pipeline, prompts

# Изолированный роутер для групповых обработчиков
router = Router()

# Хэндлеры на команды
@router.message(Command("help"))
async def chat_help_command(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        await message.reply(
            "Привет! Я твой кастомный помощник.\n"
            "/set_personality [str] - настроить промпт личности для чата.\n"
            "/get_personality - узнать промпт личности для чата.\n"
            "Если в сообщении есть ссылка на youtube видео, я его скачаю и пришлю в лучшем разрешении.\n"
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
            await load_video.download_youtube_video(url_text, message = message)
        if 'tiktok' in monitor_group_messages.filter and filters.check_tiktok_URL_message(url_text):
            await load_video.download_tiktok_video(url_text, message = message)
        if 'pornhub' in monitor_group_messages.filter and filters.check_pornhub_URL_message(url_text):
            await load_video.download_pornhub_video(url_text, message = message)

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