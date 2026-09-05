from aiogram import Bot, Router, types
from aiogram.enums import MessageEntityType
from aiogram.filters import Command

from AI_module import memory, pipeline, prompts
from filters import filters
from handlers import features
from load_video import pornhub, tiktok, youtube

import birthdays
import group_tag
import stats
import translating_msgs

#Изолированный роутер для групповых обработчиков
router = Router()


def _user_id(message) -> int | None:
    """Идентификатор автора сообщения либо None."""
    return message.from_user.id if message.from_user else None


def stats_visible(message) -> bool:
    """Ворота доступа к статистике: сейчас открыты всем, позже можно ограничить."""
    return True


#Хэндлеры на команды
@router.message(Command("help"))
async def help_command(message: types.Message):
    """Справка по командам и возможностям бота."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "help")
        await message.reply(
            "Привет! Я твой кастомный помощник.\n"
            "/set_personality [str] - настроить промпт личности для чата.\n"
            "/get_personality - показать текущую личность.\n"
            "/clear - стереть всю память чата.\n"
            "/clear [N] - стереть последние N сообщений.\n"
            "/transliterate [from] [to] [text] - исправить раскладку (ru/en) или "
            "перевести в азбуку Морзе (morse).\n"
            "/features - какие функции активны в этом чате.\n"
            "/feature [имя] on|off - включить или выключить функцию в этом чате.\n"
            "/stats [раздел] [период] - статистика (summary|top|video|tokens|global, "
            "период: today|week|month).\n"
            "/all - тегнуть всех участников чата.\n"
            "/tag create <имя> [@ники] - создать группу; /tag <имя> add|remove ... - "
            "менять её; /tag <имя> - тегнуть группу.\n"
            "Дни рождения: при входе бот спросит дату и поздравит именинника в 00:00.\n"
            "Если текст набран в неправильной раскладке — предложу исправление.\n"
            "Если в сообщении есть ссылка на видео (YouTube, TikTok, PornHub) - "
            "скачаю и пришлю.\n"
            "Если функция links включена — прочитаю содержимое ссылок "
            "(новости, статьи, посты), чтобы быть в контексте беседы.\n"
        )


@router.message(Command("set_personality"))
async def set_personality_command(message: types.Message):
    """Устанавливает личность чата."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "set_personality")
        new_prompt = message.text.replace("/set_personality", "").strip()
        if new_prompt:
            await memory.set_personality(chat_id=message.chat.id, personality=new_prompt)
            await message.reply("Частичная лоботомия проведена")
        else:
            await message.reply("А кто указывать промпт будет?")


@router.message(Command("get_personality"))
async def get_personality_command(message: types.Message):
    """Показывает текущую личность чата."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "get_personality")
        personality = (
            await memory.get_personality(chat_id=message.chat.id)
            or prompts.load("personality_default")
        )
        await message.reply(personality)


@router.message(Command("clear"))
async def clear_memory_command(message: types.Message):
    """Стирает историю чата целиком или последние N сообщений."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "clear")
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
    """Исправляет раскладку (ru/en) или переводит в азбуку Морзе и обратно."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "transliterate")
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
            return await message.reply(
                translating_msgs.change_kb_layout(text_to_translit, 'to_' + to_lang)
            )

        if to_lang == 'morse':
            route = to_lang
        elif from_lang == 'morse':
            route = 'lang'
        if 'en' in [to_lang, from_lang]:
            lang = 'en'
        elif 'ru' in [to_lang, from_lang]:
            lang = 'ru'
        return await message.reply(translating_msgs.morse_coding(text_to_translit, lang, route))


@router.message(Command("features"))
async def features_status_command(message: types.Message):
    """Показывает состояние функций в чате."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "features")
        lines = ["Функции в этом чате:"]
        for name, description, state in features.status(message.chat.id):
            if state == "on":
                lines.append(f"✅ {name} — {description}")
            elif state == "off":
                lines.append(f"❌ {name} — {description} (выключена в этом чате)")
            else:
                lines.append(f"🔒 {name} — {description} (запрещена глобально)")
        await message.reply("\n".join(lines))


@router.message(Command("feature"))
async def feature_command(message: types.Message):
    """Включает или выключает функцию в этом чате."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "feature")
        args = message.text.replace("/feature", "").strip().split()
        if len(args) != 2 or args[1].lower() not in ("on", "off"):
            return await message.reply("Формат: /feature <имя> on|off (список функций — /features)")
        enabled = args[1].lower() == "on"
        ok, name = await features.set_chat_feature(message.chat.id, args[0], enabled)
        if not ok:
            return await message.reply(name)
        state = "включена" if enabled else "выключена"
        return await message.reply(f"Готово: {name} теперь {state} в этом чате.")


@router.message(Command("stats"))
async def stats_command(message: types.Message):
    """Показывает статистику по разделу и периоду."""
    if message.chat.type in ["group", "supergroup"]:
        await stats.record_command(message.chat.id, _user_id(message), "stats")
        if not stats_visible(message) or not features.is_enabled(message.chat.id, "stats"):
            await message.reply("Статистика сейчас недоступна в этом чате.")
            return
        args = message.text.replace("/stats", "").strip().split()
        section = args[0].lower() if args else "summary"
        period = args[1].lower() if len(args) > 1 else "all"
        if not stats.is_valid_section(section) or not stats.is_valid_period(period):
            await message.reply(
                "Формат: /stats [summary|top|video|tokens|global] "
                "[all|today|yesterday|week|month]"
            )
            return
        chat_id = None if section == "global" else message.chat.id
        if section == "summary":
            text = await stats.build_summary(chat_id, period)
        elif section == "top":
            text = await stats.build_top(chat_id, period)
        elif section == "video":
            text = await stats.build_video(chat_id, period)
        else:
            text = await stats.build_tokens(chat_id, period)
        await message.reply(text)


#--------------------------------------
#Функции обработки сообщений и общий хэндлер на всё
#Реакция на слово «баг»
async def check_bug_message(message: types.Message):
    """Помечает сообщение о «баге» и шлёт уведомление."""
    if features.is_enabled(message.chat.id, 'bug') and "баг" in message.text.lower():
        await message.answer(f"🔧 @{message.from_user.username} упомянул баг! Зафиксировано.")


#Реакция на любой URL
async def check_URL_message(message: types.Message):
    """Скачивает видео, если ссылка относится к платформам load_video."""
    if not message.entities:
        return
    for entity in message.entities:
        if entity.type == MessageEntityType.URL:
            url_text = message.text[entity.offset : entity.offset + entity.length]
        elif entity.type == MessageEntityType.TEXT_LINK:
            url_text = entity.url
        else:
            continue
        if features.is_enabled(message.chat.id, 'youtube') and filters.check_youtube_URL_message(url_text):
            await youtube.download_youtube_video(url_text, message=message)
        if features.is_enabled(message.chat.id, 'tiktok') and filters.check_tiktok_URL_message(url_text):
            await tiktok.download_tiktok_video(url_text, message=message)
        if features.is_enabled(message.chat.id, 'pornhub') and filters.check_pornhub_URL_message(url_text):
            await pornhub.download_pornhub_video(url_text, message=message)


#Реакция на текст в неправильной раскладке
async def check_wrong_layout(message: types.Message):
    """Предлагает исправление текста, набранного в неправильной раскладке."""
    if features.is_enabled(message.chat.id, 'transliterate_auto'):
        corrected = await translating_msgs.auto_correct(message.text, chat_id=message.chat.id)
        if corrected:
            await message.reply(f"Возможно, ты хотел написать: {corrected}")


#Хэндлер ловит все сообщения в группе (если выключен Privacy Mode в BotFather)
@router.message()
async def monitor_group_messages(message: types.Message, bot: Bot):
    """Общий обработчик: статистика, реестр, память, видео и раскладка."""
    if message.chat.type in ["group", "supergroup"]:
        from_user = message.from_user
        is_command = bool(message.text and message.text.lstrip().startswith("/"))
        await stats.record_message(
            message.chat.id,
            user_id=_user_id(message),
            user_name=from_user.full_name if from_user else None,
            is_command=is_command,
        )
        #Реестр участников для /all: любой написавший попадает в список чата.
        await group_tag.note_user(
            message.chat.id,
            user_id=_user_id(message),
            user_name=from_user.full_name if from_user else None,
            username=from_user.username if from_user else None,
            is_bot=bool(from_user and from_user.is_bot),
        )
        #Дни рождения: дата-сообщение участника запоминается и не обрабатывается дальше.
        if await birthdays.try_answer(message):
            return
        memory_on = features.is_enabled(message.chat.id, 'AI_chating_memory')
        response_on = features.is_enabled(message.chat.id, 'AI_chating_responce')
        links_on = features.is_enabled(message.chat.id, 'links')
        if memory_on or response_on:
            await pipeline.run_pipeline(
                message,
                bot,
                memory_on=memory_on,
                response_on=response_on,
                links_on=links_on,
            )
        await check_bug_message(message)
        await check_URL_message(message)
        await check_wrong_layout(message)
