from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота из переменных окружения (.env)."""

    bot_token: SecretStr
    AI_api_token: SecretStr
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


config = Settings()
