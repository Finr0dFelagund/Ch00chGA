import json
import re
from config import config
from openai import AsyncOpenAI

ai_client = AsyncOpenAI(
    api_key=config.AI_api_token.get_secret_value(),
    base_url="https://api.deepseek.com",
)


async def chat(messages, *, temperature: float = 0.7, max_tokens: int = 400) -> str:
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if response and response.choices:
        first = response.choices[0]
        if hasattr(first, "message"):
            content = first.message.content
            if content:
                return content
        elif isinstance(first, dict):
            content = first.get("message", {}).get("content", "")
            if content:
                return content
    return ""

def parse_decision(text: str):
    if not text:
        return False, "empty"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return False, "parse_failed"
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return False, "parse_failed"

    raw = data.get("should_respond")
    if isinstance(raw, str):
        should = raw.strip().lower() in ("true", "1", "yes")
    elif isinstance(raw, bool):
        should = raw
    else:
        should = bool(raw)
    reason = str(data.get("reason", ""))
    return should, reason