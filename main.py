import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import config
from handlers import some_logic, features, member_events
from AI_module import database
from load_video import init_tiktok_browser, close_tiktok_browser
import stats
import group_tag

async def main():

    logging.basicConfig(level=logging.INFO)

    await database.init_talker_db()
    await stats.init_db()
    await group_tag.init_db()
    await features.load_state()
    await init_tiktok_browser()
    
    bot = Bot(token=config.bot_token.get_secret_value())
    dp = Dispatcher()

    group_tag.attach_events()
    await group_tag.reconcile(bot)

    # Команды и членские события подключаются до some_logic: его catch-all
    # обрабатывает любое сообщение и не даёт более поздним роутерам его увидеть.
    dp.include_router(group_tag.router)
    dp.include_router(member_events.router)
    dp.include_router(some_logic.router)

    #print("Бот успешно запущен локально через Long Polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await close_tiktok_browser()

if __name__ == "__main__":
    asyncio.run(main())
