import logging
import time

import yt_dlp

from load_video.sender import send_video

logger = logging.getLogger(__name__)


@send_video
def download_youtube_video(url: str, output_path: str = "video.mp4") -> str | None:
    """Скачивает видео YouTube в mp4 через yt-dlp и ffmpeg."""
    time.sleep(3)
    ydl_opts = {
        'noplaylist': True,
        'js_runtimes': {'node': {}},
        'format': (
            'bestvideo[filesize_approx<=48M]+bestaudio[filesize_approx<=48M]'
            '/best[filesize_approx<=48M]'
        ),
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
    except Exception:
        logger.exception("Ошибка при скачивании")
        return None
