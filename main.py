import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import config
from handlers import some_logic
from AI_module import database, core
from handlers.load_video import init_tiktok_browser, close_tiktok_browser

async def main():

    logging.basicConfig(level=logging.INFO)

    await database.init_talker_db()
    await init_tiktok_browser()
    
    bot = Bot(token=config.bot_token.get_secret_value())
    dp = Dispatcher()

    dp.include_router(some_logic.router)

    #print("Бот успешно запущен локально через Long Polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await close_tiktok_browser()

if __name__ == "__main__":
    asyncio.run(main())
