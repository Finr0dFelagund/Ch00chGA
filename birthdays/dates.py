#Парсинг даты рождения из ответа участника.
#Форматы: ДД.ММ[.ГГГГ] (разделители «.», «/», «-») и русские названия
#месяцев («12 мая 1990»). Возвращается (день, месяц, год_или_None) либо None.
import datetime
import re

_MONTHS = {
    "январь": 1, "января": 1,
    "февраль": 2, "февраля": 2,
    "март": 3, "марта": 3,
    "апрель": 4, "апреля": 4,
    "май": 5, "мая": 5,
    "июнь": 6, "июня": 6,
    "июль": 7, "июля": 7,
    "август": 8, "августа": 8,
    "сентябрь": 9, "сентября": 9,
    "октябрь": 10, "октября": 10,
    "ноябрь": 11, "ноября": 11,
    "декабрь": 12, "декабря": 12,
}

_NUMERIC = re.compile(r"^\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})(?:\s*[./\-]\s*(\d{2,4}))?\s*$")
_TEXT = re.compile(r"^\s*(\d{1,2})\s+([а-яё]+)(?:[,\s]+(\d{4}))?\s*$", re.IGNORECASE)
_TRAIL_YEAR_WORD = re.compile(r"(?i)\s*(?:года?|г)\s*$")


def _normalize_year(year):
    """Двузначный год относит к XXI веку, если он не старше текущего года."""
    if year is None:
        return None
    if year >= 100:
        return year
    current = datetime.date.today().year
    return 2000 + year if year <= current % 100 else 1900 + year


def _days_in_month(month: int, year) -> int:
    if month == 2:
        if year is None:
            return 29
        if year % 4 != 0 or (year % 100 == 0 and year % 400 != 0):
            return 28
        return 29
    if month in (4, 6, 9, 11):
        return 30
    return 31


def _valid(day: int, month: int, year) -> bool:
    if not 1 <= month <= 12 or day < 1:
        return False
    return day <= _days_in_month(month, year)


def parse(text: str):
    """Разбирает дату рождения; возвращает (день, месяц, год) либо None."""
    if not text:
        return None
    cleaned = str(text).strip(" .,;")
    cleaned = _TRAIL_YEAR_WORD.sub(" ", cleaned).strip()
    if not cleaned:
        return None

    match = _NUMERIC.match(cleaned)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else None
        year = _normalize_year(year)
        if _valid(day, month, year):
            return day, month, year
        return None

    match = _TEXT.match(cleaned)
    if match:
        day = int(match.group(1))
        month = _MONTHS.get(match.group(2).lower())
        year = int(match.group(3)) if match.group(3) else None
        if month is not None and _valid(day, month, year):
            return day, month, year
    return None
