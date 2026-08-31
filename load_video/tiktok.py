import asyncio
import json
import re

from load_video.sender import send_video

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
