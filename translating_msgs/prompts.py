import os

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

_cache = {}


def load(name: str) -> str:
    if name not in _cache:
        with open(os.path.join(PROMPTS_DIR, name + ".txt"), "r", encoding="utf-8") as f:
            _cache[name] = f.read()
    return _cache[name]


def render(name: str, **values) -> str:
    text = load(name)
    for key, value in values.items():
        text = text.replace("{{%s}}" % key.upper(), str(value))
    return text
