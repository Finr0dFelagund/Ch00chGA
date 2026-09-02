import asyncio
import inspect
import os
import time
from functools import wraps

from aiogram.types import FSInputFile, Message
import stats


def send_video(func):
    """Ставит видео на скачивание и затем отправляет асинхронно.

    Декорируемая функция определяет метод скачивания.
    """
    @wraps(func)
    async def wrapper(*args, message: Message, **kwargs):
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
                downloaded_file = await loop.run_in_executor(None, lambda: func(url=url, output_path=filename))
        except Exception as e:
            await stats.record_video(message.chat.id, platform, stats.VIDEO_DOWNLOAD_ERROR, user_id, user_name)
            print(f"Ошибка при скачивании видео ({platform}): {e}")
            raise

        if downloaded_file and os.path.exists(downloaded_file):
            video_file = FSInputFile(downloaded_file)
            try:
                await message.reply_video(video=video_file)
                status = stats.VIDEO_OK
            except Exception as e:
                await message.answer(f"❌ Не удалось отправить видео. Ошибка: {e}")
                status = stats.VIDEO_SEND_ERROR
            await stats.record_video(message.chat.id, platform, status, user_id, user_name)
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)
        else:
            await message.reply("❌ Не удалось скачать видео. Проверьте ссылку или попробуйте позже.")
            await stats.record_video(message.chat.id, platform, stats.VIDEO_DOWNLOAD_ERROR, user_id, user_name)
    return wrapper

