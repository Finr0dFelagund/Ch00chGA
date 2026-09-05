import asyncio
import inspect
import logging
import os
import time
from functools import wraps

from aiogram.types import FSInputFile, Message

import stats

logger = logging.getLogger(__name__)


def send_video(func):
    """Ставит видео на скачивание и затем отправляет асинхронно.

    Декорируемая функция определяет метод скачивания.
    """
    @wraps(func)
    async def wrapper(*args, message: Message, **kwargs):
        """Скачивает видео функцией func и отправляет результат в чат."""
        url = args[0] if args else kwargs.get("url")
        if not url:
            await message.reply("❌ Ошибка: не удалось найти ссылку на видео.")
            return
        platform = func.__module__.rsplit(".", 1)[-1]
        user_id = message.from_user.id if message.from_user else None
        user_name = message.from_user.full_name if message.from_user else None
        filename = f"video_{time.time()}_{message.chat.id}_{user_id}.mp4"

        try:
            if inspect.iscoroutinefunction(func):
                downloaded_file = await func(url=url, output_path=filename)
            else:
                loop = asyncio.get_event_loop()
                task = lambda: func(url=url, output_path=filename)
                downloaded_file = await loop.run_in_executor(None, task)
        except Exception:
            await stats.record_video(
                message.chat.id, platform, stats.VIDEO_DOWNLOAD_ERROR, user_id, user_name
            )
            logger.exception("Ошибка при скачивании видео (%s)", platform)
            raise

        if downloaded_file and os.path.exists(downloaded_file):
            video_file = FSInputFile(downloaded_file)
            try:
                await message.reply_video(video=video_file)
                status = stats.VIDEO_OK
            except Exception as e:
                await message.answer(f"❌ Не удалось отправить видео. Ошибка: {e}")
                status = stats.VIDEO_SEND_ERROR
            await stats.record_video(
                message.chat.id, platform, status, user_id, user_name
            )
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)
        else:
            await message.reply(
                "❌ Не удалось скачать видео. Проверьте ссылку или попробуйте позже."
            )
            await stats.record_video(
                message.chat.id, platform, stats.VIDEO_DOWNLOAD_ERROR, user_id, user_name
            )
    return wrapper
