#Чтение содержимого ссылок (новости, статьи, посты) для контекста беседы.
#Ссылки берутся из entities сообщения (URL/TEXT_LINK), страница скачивается
#через aiohttp и превращается в текст stdlib-парсером (без новых зависимостей).
#Все ошибки тихо возвращают отсутствие контента: конвейер болталки не должен
#зависеть от внешних сайтов.
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import aiohttp
from aiogram.enums import MessageEntityType

from filters.filters import is_video_url

logger = logging.getLogger(__name__)

#Ограничения загрузки: суммарное время запроса и объём тела.
MAX_BODY_BYTES = 2_000_000
FETCH_TIMEOUT_SEC = 8.0
#Сколько ссылок из сообщения читаем (берётся первая удачная).
MAX_LINKS = 1
MAX_TEXT_CHARS = 4000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

#Ссылки, которые забирает load_video (проверка filters.is_video_url по общим
#спискам filters/*.txt), link_reader не читает: их страницы текста не дают.
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _is_http(url: str) -> bool:
    """True для схем http/https."""
    try:
        return urlparse(url).scheme in ("http", "https")
    except ValueError:
        return False


def extract_urls(message) -> list:
    """Ссылки из entities сообщения (URL/TEXT_LINK), без видео-доменов."""
    text = getattr(message, "text", None) or ""
    urls = []
    seen = set()
    entities = getattr(message, "entities", None) or []
    for entity in entities:
        if entity.type == MessageEntityType.URL:
            url = text[entity.offset:entity.offset + entity.length].strip()
        elif entity.type == MessageEntityType.TEXT_LINK:
            url = (getattr(entity, "url", "") or "").strip()
        else:
            continue
        if url and url not in seen and _is_http(url) and not is_video_url(url):
            urls.append(url)
            seen.add(url)
    if urls:
        return urls
    #Запасной вариант: голый текст без entities (например, ссылка в подписи).
    for match in _URL_RE.findall(text):
        url = match.strip().rstrip(".,!?:;")
        if url and url not in seen and _is_http(url) and not is_video_url(url):
            urls.append(url)
            seen.add(url)
    return urls


def _detect_encoding(raw: bytes, header_charset) -> str:
    """Кодировка страницы: из заголовка, meta-тега либо utf-8 по умолчанию."""
    if header_charset:
        return header_charset
    match = re.search(rb'<meta[^>]+charset\s*=\s*["\']?([\w\-]+)', raw[:4000], re.IGNORECASE)
    if match:
        return match.group(1).decode("ascii", "replace")
    return "utf-8"


def _meta_content(html: str, *keys) -> str | None:
    """Значение content для og:title/og:description/description из <head>."""
    for tag in re.findall(r"<meta\b[^>]*>", html, re.IGNORECASE):
        props = dict(re.findall(r'([a-zA-Z:_-]+)\s*=\s*"([^"]*)"', tag))
        if (props.get("property") or props.get("name")) in keys and props.get("content"):
            return props["content"].strip()
    return None


class _ArticleParser(HTMLParser):
    """Сбор текста статьи: заголовки, абзацы, списки; без мусора script/nav и т.п."""

    _IGNORED = {
        "script", "style", "noscript", "svg", "template", "iframe", "form",
        "nav", "footer", "aside", "select", "button", "canvas",
    }
    _CAPTURE = {
        "article", "main", "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "li", "td", "th", "pre", "figcaption", "dt", "dd", "caption",
    }
    _BLOCK = _CAPTURE | {"div", "section", "tr", "ul", "ol", "table",
                         "thead", "tbody", "figure", "header", "hr", "br"}

    def __init__(self):
        """Готовит парсер: счётчики вложенности, буферы текста и заголовка."""
        super().__init__(convert_charrefs=True)
        self.title = None
        self._in_title = False
        self._skip = 0
        self._capture = 0
        self._buf = []
        self._paras = []
        self._started = False

    def handle_starttag(self, tag, attrs):
        """Отмечает вход в заголовочный, игнорируемый или захватываемый тег."""
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
            return
        if tag in self._IGNORED:
            self._skip += 1
            return
        if tag in self._CAPTURE:
            self._capture += 1
        if tag == "br":
            self._finish()

    def handle_endtag(self, tag):
        """Завершает захват/пропуск при выходе из тега и закрывает блоки."""
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            return
        if tag in self._IGNORED:
            if self._skip:
                self._skip -= 1
            return
        if tag in self._CAPTURE and self._capture:
            self._capture -= 1
        if tag in self._BLOCK:
            self._finish()

    def handle_data(self, data):
        """Собирает текст: заголовок отдельно, остальное — в буфер абзацев."""
        if self._skip:
            return
        if self._in_title:
            self.title = (self.title or "") + data
            return
        if self._capture <= 0:
            return
        if not data.strip():
            if self._started:
                self._buf.append(data)
            return
        if not self._started:
            self._started = True
        self._buf.append(data)

    def _finish(self):
        """Закрывает текущий абзац: сбрасывает буфер в список абзацев."""
        if self._started:
            self._paras.append("".join(self._buf))
            self._buf = []
            self._started = False


def _clean(value: str | None) -> str:
    """Убирает пустые значения и схлопывает пробелы в тексте."""
    if not value:
        return ""
    return " ".join(value.split())


def _truncate(text: str, limit: int) -> str:
    """Обрезает текст до limit, по границе слова, с многоточием на конце."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip() + "…"


def extract_article_text(html: str) -> str:
    """Текст страницы: заголовок + абзацы; без статьи — описание страницы."""
    parser = _ArticleParser()
    try:
        parser.feed(html)
    except Exception:
        logger.debug("Не удалось разобрать HTML страницы", exc_info=True)
        return ""

    paragraphs = [_clean(p) for p in parser._paras]
    paragraphs = [p for p in paragraphs if len(p) >= 3]
    body = "\n\n".join(paragraphs)

    title = _clean(parser.title or _meta_content(html, "og:title", "title"))
    description = _clean(_meta_content(html, "og:description", "description"))

    parts = [title] if title else []
    if body:
        parts.append(body)
    elif description:
        parts.append(description)
    return _truncate("\n\n".join(parts).strip(), MAX_TEXT_CHARS)


async def read_url_text(url: str) -> str | None:
    """Возвращает текст статьи/поста по ссылке либо None (не прочиталось)."""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"}
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_SEC)
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    return None
                if "html" not in response.headers.get("Content-Type", "").lower():
                    return None
                header_charset = response.charset
                raw = await response.content.read(MAX_BODY_BYTES + 1)
    except Exception:
        logger.debug("Не удалось прочитать ссылку %s", url, exc_info=True)
        return None
    if not raw:
        return None
    raw = raw[:MAX_BODY_BYTES]
    encoding = _detect_encoding(raw, header_charset)
    html = raw.decode(encoding, errors="replace")
    text = extract_article_text(html)
    return text or None


async def enrich_message_text(message) -> str:
    """Текст сообщения, дополненный содержанием ссылки; без изменений при неудаче."""
    base = getattr(message, "text", None) or ""
    try:
        for url in extract_urls(message)[:MAX_LINKS]:
            content = await read_url_text(url)
            if content:
                return f"{base}\n\n[Содержимое ссылки:\n{content}]"
    except Exception:
        logger.debug("Не удалось обогатить сообщение содержанием ссылки", exc_info=True)
    return base
