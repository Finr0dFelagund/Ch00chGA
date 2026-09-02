#Пакет статистики бота: сбор событий и формирование отчётов.
from stats.db import init_db
from stats.collect import (
    record_message,
    record_command,
    record_decision,
    record_video,
    record_llm_usage,
    VIDEO_OK,
    VIDEO_DOWNLOAD_ERROR,
    VIDEO_SEND_ERROR,
)
from stats.report import (
    build_summary,
    build_top,
    build_video,
    build_tokens,
    is_valid_section,
    is_valid_period,
)
from stats.prices import get_prices

__all__ = [
    "init_db",
    "record_message",
    "record_command",
    "record_decision",
    "record_video",
    "record_llm_usage",
    "VIDEO_OK",
    "VIDEO_DOWNLOAD_ERROR",
    "VIDEO_SEND_ERROR",
    "build_summary",
    "build_top",
    "build_video",
    "build_tokens",
    "is_valid_section",
    "is_valid_period",
    "get_prices",
]
