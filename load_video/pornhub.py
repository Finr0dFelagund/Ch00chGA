import os
import time

import yt_dlp

from load_video.sender import send_video


@send_video
def download_pornhub_video(url: str, output_path: str = "video.mp4") -> str | None:
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
        print(f"Ошибка получения метаданных PH: {e}")
        return None

    # PornHub отдаёт без указания размера
    # Большие форматы отсекаются через max_filesize
    # Узнаем размер из Content-Length и прерываем скачивание, не передавая тело файла
    formats = [f for f in info.get('formats', []) if f.get('url') and f.get('format_id') and f.get('protocol') in (None, 'http', 'https')]
    if not formats:
        print("PH: подходящие форматы не найдены.")
        return None

    # Лучшее качество первым
    formats.sort(key=lambda f: f.get('height') or 0, reverse=True)

    temp_path = output_path.removesuffix('.mp4') + '_temp.mp4'
    for fmt in formats:
        height = fmt.get('height', 'unknown')
        print(f"PH: пробуем {height}p...")
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
            print(f"PH: {height}p не скачался: {e}")

        # Убираем частичный
        part_path = temp_path + '.part'
        if os.path.exists(part_path):
            os.remove(part_path)
        if not os.path.exists(temp_path):
            continue

        real_size = os.path.getsize(temp_path)
        print(f"PH: {height}p скачан, размер {real_size / 1024 / 1024:.2f} МБ")
        if real_size <= max_bytes:
            os.replace(temp_path, output_path)
            return output_path
        os.remove(temp_path)
        print(f"PH: {height}p превысил лимит, пробуем формат ниже.")

    print("PH: ни один формат не уложился в 48 МБ.")
    return None
