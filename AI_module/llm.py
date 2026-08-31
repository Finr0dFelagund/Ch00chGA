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