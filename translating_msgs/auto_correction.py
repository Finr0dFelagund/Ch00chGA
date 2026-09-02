import re

from AI_module import llm
from translating_msgs import prompts
from translating_msgs.keyboard_layout import change_kb_layout

CORRECTION_MAX_TOKENS = 20


def _is_candidate(text: str) -> bool:
    """Быстрый предфильтр: пропускает в нейронку только похожий на текст контент."""
    cleaned = text.strip()
    if len(cleaned) < 4:
        return False
    if cleaned.startswith("/"):
        return False
    if "http://" in cleaned.lower() or "https://" in cleaned.lower():
        return False
    if not re.search(r"[a-zA-Zа-яА-ЯёЁ]{2,}", cleaned):
        return False
    return True


def _parse_correction(text: str, source: str = "") -> str:
    """Разбирает ответ детектора: «нет», «to_ru» или «to_en»."""
    if not text or not text.strip():
        return "нет"
    cleaned = text.strip()
    first = cleaned.split()[0].strip(".,;:!?-_\"'").lower()
    if first not in ("да", "yes", "true", "1"):
        return "нет"
    if "to_en" in cleaned.lower():
        return "to_en"
    if "to_ru" in cleaned.lower():
        return "to_ru"
    if source:
        latin = len(re.findall(r"[a-zA-Z]", source))
        cyrillic = len(re.findall(r"[а-яА-ЯёЁ]", source))
        return "to_en" if cyrillic > latin else "to_ru"
    return "to_ru"


async def _need_correction(text: str, chat_id=None) -> str:
    system = prompts.render("layout_detector", text=text)
    try:
        raw = await llm.chat(
            [{"role": "system", "content": system}],
            temperature=0,
            max_tokens=CORRECTION_MAX_TOKENS,
            chat_id=chat_id,
            tag="layout",
        )
    except Exception as e:
        print(f"Ошибка детектора раскладки: {e}")
        return "нет"
    return _parse_correction(raw, text)


async def auto_correct(text: str, chat_id=None) -> str | None:
    """Возвращает исправленный текст, если раскладка набрана неверно, иначе None."""
    if not _is_candidate(text):
        return None
    route = await _need_correction(text, chat_id)
    if route == "нет":
        return None
    corrected = change_kb_layout(text, route)
    if corrected == text:
        return None
    return corrected
