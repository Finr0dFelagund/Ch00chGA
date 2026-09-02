#Тариф DeepSeek из stats/prices.txt: кэш с периодической перезагрузкой.
import os
import time

PRICES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.txt")
RELOAD_INTERVAL = 60.0

_cache = {}
_cache_time = 0.0


def _read_prices() -> dict:
    """Читает файл цен: строки вида ключ=значение, # — комментарий."""
    prices = {}
    try:
        with open(PRICES_PATH, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    prices[key.strip().lower()] = float(value.strip())
    except Exception as e:
        print(f"Ошибка чтения тарифа {PRICES_PATH}: {e}")
    return prices


def get_prices() -> dict:
    """Цены (USD за 1M токенов). Перечитывает файл не чаще RELOAD_INTERVAL секунд."""
    global _cache, _cache_time
    now = time.time()
    if not _cache or now - _cache_time > RELOAD_INTERVAL:
        _cache = _read_prices()
        _cache_time = now
    return _cache


def tokens_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Стоимость в долларах по текущему тарифу."""
    prices = get_prices()
    input_price = prices.get("input", 0.0)
    output_price = prices.get("output", 0.0)
    return prompt_tokens / 1_000_000 * input_price + completion_tokens / 1_000_000 * output_price
