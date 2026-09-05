import logging
import os
import time

import yt_dlp

from load_video.sender import send_video

logger = logging.getLogger(__name__)


@send_video
def download_pornhub_video(url: str, output_path: str = "video.mp4") -> str | None:
    """Скачивает видео PornHub в mp4, перебирая форматы до лимита 48 МБ."""
    time.sleep(3)
    max_bytes = 48 * 1024 * 1024  # Лимит Telegram на размер видео

    # Метаданные: список доступных форматов
    meta_opts = {
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        logger.warning("PH: ошибка получения метаданных: %s", e)
        return None

    #PornHub отдаёт размер без указания в формате.
    #Большие форматы отсекаются через max_filesize.
    #Узнаём размер из Content-Length и прерываем скачивание, не передавая тело файла.
    formats = [
        f for f in info.get('formats', [])
        if f.get('url') and f.get('format_id')
        and f.get('protocol') in (None, 'http', 'https')
    ]
    if not formats:
        logger.warning("PH: подходящие форматы не найдены.")
        return None

    #Лучшее качество первым
    formats.sort(key=lambda f: f.get('height') or 0, reverse=True)

    temp_path = output_path.removesuffix('.mp4') + '_temp.mp4'
    for fmt in formats:
        height = fmt.get('height', 'unknown')
        logger.info("PH: пробуем %sp...", height)
        ydl_opts = {
            'noplaylist': True,
            'format': fmt['format_id'],
            'outtmpl': temp_path,
            'quiet': True,
            'no_warnings': True,
            'max_filesize': max_bytes,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            logger.debug("PH: %sp не скачался: %s", height, e)

        #Убираем частичный
        part_path = temp_path + '.part'
        if os.path.exists(part_path):
            os.remove(part_path)
        if not os.path.exists(temp_path):
            continue

        real_size = os.path.getsize(temp_path)
        logger.info("PH: %sp скачан, размер %.2f МБ", height, real_size / 1024 / 1024)
        if real_size <= max_bytes:
            os.replace(temp_path, output_path)
            return output_path
        os.remove(temp_path)
        logger.info("PH: %sp превысил лимит, пробуем формат ниже.", height)

    logger.warning("PH: ни один формат не уложился в 48 МБ.")
    return None
