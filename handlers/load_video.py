import asyncio
import yt_dlp
from collections import deque
import time
import os
from aiogram import types
from aiogram.types import Message, FSInputFile
from functools import wraps
import inspect
import json
import re

#Декоратор отправщик видео. 
#Ставит видос на скачку и потом отправляет асинхронно.
# Декорируемая ф-я определяет метод скачивания
def send_video(func):
    @wraps(func)
    async def wrapper(*args, message: types.Message, **kwargs):
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

@send_video
def download_youtube_video(url: str, output_path: str = "video.mp4") -> str | None:
    time.sleep(3)
    ydl_opts = {
        'noplaylist': True,
        'js_runtimes': {'node': {}},
        'format': 'bestvideo[filesize_approx<=48M]+bestaudio[filesize_approx<=48M]/best[filesize_approx<=48M]',
        'format_sort': ['vcodec:h264', 'acodec:aac'],
        'merge_output_format': 'mp4',
        'extractor_args': {
            'youtube': {
                'player_client': ['tv', 'visionos', 'web_embedded'],
            }
        },
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return output_path
    except Exception as e:
        print(f"Ошибка при скачивании: {e}")
        return


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

# --- Персистентный браузер для TikTok (Playwright) ---
_playwright = None
_tiktok_browser = None
_tiktok_context = None
_tiktok_semaphore = None
_init_lock = asyncio.Lock()

async def init_tiktok_browser():
    global _playwright, _tiktok_browser, _tiktok_context, _tiktok_semaphore
    async with _init_lock:
        if _tiktok_browser:
            return
        try:
            from playwright.async_api import async_playwright
            _playwright = await async_playwright().start()
            _tiktok_browser = await _playwright.chromium.launch(headless=True)
            _tiktok_context = await _tiktok_browser.new_context(viewport={'width': 1280, 'height': 720})
            _tiktok_semaphore = asyncio.Semaphore(1)
            print("TikTok-браузер запущен.")
        except Exception as e:
            print(f"Не удалось запустить TikTok-браузер: {e}")
            if _tiktok_browser:
                try:
                    await _tiktok_browser.close()
                except Exception:
                    pass
            _playwright = _tiktok_browser = _tiktok_context = _tiktok_semaphore = None


async def close_tiktok_browser():
    global _playwright, _tiktok_browser, _tiktok_context, _tiktok_semaphore
    async with _init_lock:
        if _tiktok_browser is None:
            return
        if _tiktok_semaphore is not None:
            async with _tiktok_semaphore:
                pass
        try:
            await _tiktok_browser.close()
        except Exception:
            pass
        if _playwright:
            try:
                await _playwright.stop()
            except Exception:
                pass
        _playwright = _tiktok_browser = _tiktok_context = _tiktok_semaphore = None
        print("TikTok-браузер остановлен.")


def _find_video_urls(obj):
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_find_video_urls(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_find_video_urls(v))
    elif isinstance(obj, str) and 'v16-webapp' in obj and '/video/tos/' in obj and 'audio' not in obj:
        out.append(obj)
    return out


async def _download_tiktok_video(url, output_path):
    page = await _tiktok_context.new_page()
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        await page.wait_for_timeout(6000)

        html = await page.content()
        m = re.search(r'id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            print("TikTok: universal_data не найден")
            return None

        data = json.loads(m.group(1))
        urls = _find_video_urls(data)

        seen = set()
        for video_url in urls:
            if video_url in seen:
                continue
            seen.add(video_url)
            resp = await page.request.get(video_url, headers={'Referer': url})
            if resp.status != 200:
                continue
            ct = (resp.headers.get('content-type') or '').lower()
            if 'video' not in ct and 'octet-stream' not in ct:
                continue
            body = await resp.body()
            if 0 < len(body) <= 48_000_000:
                with open(output_path, 'wb') as f:
                    f.write(body)
                return output_path
        print("TikTok: видео не скачалось или превышает 48 МБ")
        return None
    finally:
        await page.close()


@send_video
async def download_tiktok_video(url: str, output_path: str = "video.mp4") -> str | None:
    await asyncio.sleep(3)
    if _tiktok_browser is None:
        print("TikTok: браузер не инициализирован (вызовите init_tiktok_browser)")
        return None
    async with _tiktok_semaphore:
        try:
            return await _download_tiktok_video(url, output_path)
        except Exception as e:
            print(f"Ошибка при скачивании TikTok: {e}")
            return None