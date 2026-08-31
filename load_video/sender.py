import asyncio
import inspect
import os
import time
from functools import wraps

from aiogram.types import FSInputFile, Message


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
        filename = f"video_{time.time()}_{message.chat.id}_{message.from_user.id}.mp4"

        if inspect.iscoroutinefunction(func):
            downloaded_file = await func(url=url, output_path=filename)
        else:
            loop = asyncio.get_event_loop()
            downloaded_file = await loop.run_in_executor(None, lambda: func(url=url, output_path=filename))

        if downloaded_file and os.path.exists(downloaded_file):
            video_file = FSInputFile(downloaded_file)
            try:
                await message.reply_video(video=video_file)
            except Exception as e:
                await message.answer(f"❌ Не удалось отправить видео. Ошибка: {e}")
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)
        else:
            await message.reply("❌ Не удалось скачать видео. Проверьте ссылку или попробуйте позже.")
    return wrapper
