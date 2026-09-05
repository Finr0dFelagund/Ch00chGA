import asyncio
import logging

from aiogram import Bot, Dispatcher

from AI_module import database
from config import config
from handlers import features, member_events, some_logic
from load_video import close_tiktok_browser, init_tiktok_browser

import birthdays
import group_tag
import stats


async def main():
    """Запуск бота: инициализация БД и браузера, подключение роутеров, Long Polling."""
    logging.basicConfig(level=logging.INFO)

    await database.init_talker_db()
    await stats.init_db()
    await group_tag.init_db()
    await birthdays.init_db()
    await features.load_state()
    await init_tiktok_browser()

    bot = Bot(token=config.bot_token.get_secret_value())
    dp = Dispatcher()

    group_tag.attach_events()
    birthdays.attach(bot)
    await group_tag.reconcile(bot)

    #Команды и членские события подключаются до some_logic: его catch-all
    #обрабатывает любое сообщение и не даёт более поздним роутерам его увидеть.
    dp.include_router(group_tag.router)
    dp.include_router(birthdays.router)
    dp.include_router(member_events.router)
    dp.include_router(some_logic.router)

    #Полуночный воркер поздравлений работает параллельно с polling.
    birthdays_task = asyncio.create_task(birthdays.run_worker(bot))

    try:
        await dp.start_polling(bot)
    finally:
        birthdays_task.cancel()
        await close_tiktok_browser()


if __name__ == "__main__":
    asyncio.run(main())
