from config import config
from openai import AsyncOpenAI
import stats

ai_client = AsyncOpenAI(
    api_key=config.AI_api_token.get_secret_value(),
    base_url="https://api.deepseek.com",
)


async def chat(messages, *, temperature: float = 0.7, max_tokens: int = 400,
               chat_id=None, tag: str = None) -> str:
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    await _record_usage(response, chat_id, tag)
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


async def _record_usage(response, chat_id, tag: str):
    """Записывает расход токенов ответа DeepSeek в статистику."""
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if not usage:
        return
    if isinstance(usage, dict):
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
    else:
        prompt = getattr(usage, "prompt_tokens", None)
        completion = getattr(usage, "completion_tokens", None)
    if prompt is None or completion is None:
        return
    await stats.record_llm_usage(chat_id, tag, prompt, completion)
