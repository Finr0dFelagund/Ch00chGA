#Декоратор, добавляющий функции список строк из txt (строки с # игнорируются).

def read_filter_lines(path: str) -> list:
    """Читает строки txt-файла; пустые строки и комментарии пропускаются."""
    with open(path, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

def get_filter_list(path: str):
    """Возвращает декоратор, который при декорировании читает txt-файл path
    и сохраняет строки-подстроки в атрибут filter функции. reload() перечитывает
    файл — для применения правок без перезапуска бота."""
    def decorator(func):
        def reload():
            func.filter = read_filter_lines(path)

        func.filter = read_filter_lines(path)
        func.reload = reload
        return func

    return decorator


@get_filter_list("filters/youtube.txt")
def check_youtube_URL_message(url_text: str):
    """True, если в URL есть подстрока из списка youtube.txt."""
    url_text = url_text.lower()
    if any(i in url_text for i in check_youtube_URL_message.filter):
        return True


@get_filter_list("filters/tiktok.txt")
def check_tiktok_URL_message(url_text: str):
    """True, если в URL есть подстрока из списка tiktok.txt."""
    url_text = url_text.lower()
    if any(i in url_text for i in check_tiktok_URL_message.filter):
        return True


@get_filter_list("filters/pornhub.txt")
def check_pornhub_URL_message(url_text: str):
    """True, если в URL есть подстрока из списка pornhub.txt."""
    url_text = url_text.lower()
    if any(i in url_text for i in check_pornhub_URL_message.filter):
        return True

#Сводная проверка: ссылку забирает load_video (единый источник для link_reader,
#чтобы списки платформ не дублировались в двух местах).
VIDEO_URL_CHECKERS = (
    check_youtube_URL_message,
    check_tiktok_URL_message,
    check_pornhub_URL_message,
)


def is_video_url(url_text: str) -> bool:
    """True, если URL обрабатывает load_video (YouTube/TikTok/PornHub)."""
    return any(check(url_text) for check in VIDEO_URL_CHECKERS)
