#Формирование текстовых отчётов статистики по чатам и периодам.
import time
import aiosqlite
from AI_module import database
from stats import prices
from stats import categories
from stats.collect import (
    TAG_DECISION,
    TAG_RESPONDER,
    TAG_SUMMARIZER,
    TAG_LAYOUT,
)

TAG_LABELS = {
    TAG_DECISION: "фильтр «отвечать»",
    TAG_RESPONDER: "генерация ответа",
    TAG_SUMMARIZER: "сжатие истории",
    TAG_LAYOUT: "детектор раскладки",
}

PERIODS = ("all", "today", "yesterday", "week", "month")
TOP_LIMIT = 5

PERIOD_LABELS = {
    "all": "всё время",
    "today": "сегодня",
    "yesterday": "вчера",
    "week": "7 дней",
    "month": "30 дней",
}


def _period_range(period: str):
    """Возвращает (start, end) метки времени для периода; для all — (None, None)."""
    now = time.time()
    lt = time.localtime(now)
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    if period == "today":
        return midnight, None
    if period == "yesterday":
        return midnight - 86400, midnight
    if period == "week":
        return now - 7 * 86400, None
    if period == "month":
        return now - 30 * 86400, None
    return None, None


def _period_days(period: str, first_ts=None) -> int:
    """Число дней в периоде для расчёта среднего."""
    if period in ("today", "yesterday"):
        return 1
    if period == "week":
        return 7
    if period == "month":
        return 30
    if first_ts:
        return max(1, int((time.time() - first_ts) / 86400))
    return 1


def _ts_conds(start, end):
    """Возвращает (sql_фрагмент, params) для фильтра по времени."""
    conds, params = [], []
    if start is not None:
        conds.append("ts >= ?")
        params.append(start)
    if end is not None:
        conds.append("ts < ?")
        params.append(end)
    return " AND ".join(conds), params


async def _fetch_all(db, sql: str, params: tuple):
    async with db.execute(sql, params) as cur:
        return await cur.fetchall()


async def _fetch_one(db, sql: str, params: tuple):
    rows = await _fetch_all(db, sql, params)
    return rows[0] if rows else None


def _fmt_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(int(value))


def _fmt_cost(value: float) -> str:
    return f"${value:.2f}"


def _scope_label(chat_id, period: str) -> str:
    chat = "все чаты" if chat_id is None else f"чат {chat_id}"
    label = PERIOD_LABELS.get(period, period)
    return f"{chat}, {label}"


def _scope_where(chat_id, start, end):
    """Общие условия WHERE для выборок отчёта."""
    conds, params = [], []
    if chat_id is not None:
        conds.append("chat_id = ?")
        params.append(chat_id)
    ts_sql, ts_params = _ts_conds(start, end)
    if ts_sql:
        conds.append(ts_sql)
        params.extend(ts_params)
    where = " AND ".join(conds)
    if where:
        where = " WHERE " + where
    return where, params


async def _messages_info(db, chat_id, start, end):
    """(всего сообщений, уникальных пользователей, команд, первый ts)."""
    where, params = _scope_where(chat_id, start, end)
    return await _fetch_one(
        db,
        f"SELECT COUNT(*), COUNT(DISTINCT user_id), SUM(is_command), MIN(ts) "
        f"FROM stats_messages{where}",
        tuple(params),
    ) or (0, 0, 0, None)


async def _top_users(db, chat_id, start, end, limit=TOP_LIMIT):
    where, params = _scope_where(chat_id, start, end)
    return await _fetch_all(
        db,
        f"SELECT MAX(user_name), COUNT(*) FROM stats_messages{where} "
        "GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT ?",
        (*params, limit),
    )


async def _top_commands(db, chat_id, start, end, limit=TOP_LIMIT):
    where, params = _scope_where(chat_id, start, end)
    return await _fetch_all(
        db,
        f"SELECT command, COUNT(*) FROM stats_commands{where} "
        "GROUP BY command ORDER BY COUNT(*) DESC LIMIT ?",
        (*params, limit),
    )


async def _decisions_info(db, chat_id, start, end):
    """Распределение исходов и полный список причин (для категоризации)."""
    where, params = _scope_where(chat_id, start, end)
    should = await _fetch_all(
        db, f"SELECT should, COUNT(*) FROM stats_decisions{where} GROUP BY should", tuple(params)
    )
    reasons = await _fetch_all(
        db,
        f"SELECT should, reason, COUNT(*) FROM stats_decisions{where} "
        "GROUP BY should, reason",
        tuple(params),
    )
    return should, reasons


async def _videos_info(db, chat_id, start, end):
    where, params = _scope_where(chat_id, start, end)
    return await _fetch_all(
        db,
        f"SELECT platform, status, COUNT(*) FROM stats_videos{where} GROUP BY platform, status",
        tuple(params),
    )


async def _top_video_users(db, chat_id, start, end, limit=TOP_LIMIT):
    where, params = _scope_where(chat_id, start, end)
    return await _fetch_all(
        db,
        f"SELECT MAX(user_name), COUNT(*) FROM stats_videos{where} "
        "GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT ?",
        (*params, limit),
    )


async def _usage_by_tag(db, chat_id, start, end):
    where, params = _scope_where(chat_id, start, end)
    return await _fetch_all(
        db,
        f"SELECT tag, SUM(prompt_tokens), SUM(completion_tokens) "
        f"FROM stats_llm_usage{where} GROUP BY tag",
        tuple(params),
    )


async def _top_chats(db, start, end, limit=TOP_LIMIT):
    ts_sql, params = _ts_conds(start, end)
    where = ""
    if ts_sql:
        where = " WHERE " + ts_sql
    return await _fetch_all(
        db,
        f"SELECT chat_id, COUNT(*) FROM stats_messages{where} "
        "GROUP BY chat_id ORDER BY COUNT(*) DESC LIMIT ?",
        (*params, limit),
    )

def _format_messages_section(total, unique, period, first_ts=None):
    days = _period_days(period, first_ts) if period == "all" else _period_days(period)
    avg = total / max(1, days)
    return [f"Сообщений обработано: {total} · уникальных пользователей: {unique} · среднее в день: {avg:.1f}"]


def _format_users(lines, rows):
    if rows:
        items = ", ".join(f"{name or 'без имени'} ({cnt})" for name, cnt in rows)
        lines.append(f"Активные пользователи: {items}")


def _format_decisions(lines, should_rows, reason_rows):
    total = sum(cnt for _, cnt in should_rows)
    if total == 0:
        lines.append("Фильтр «отвечать»: событий нет")
        return
    yes = sum(cnt for s, cnt in should_rows if s)
    lines.append(f"Фильтр «отвечать»: да {yes} ({yes / total * 100:.0f}%) · нет {total - yes}")

    buckets = {}
    for should, reason, cnt in reason_rows:
        key = categories.categorize_reason(bool(should), reason)
        buckets[key] = buckets.get(key, 0) + cnt
    if not buckets:
        return

    order = {key: i for i, (key, _) in enumerate(categories.CATEGORY_LABELS)}
    ordered = sorted(buckets.items(), key=lambda item: (-item[1], order.get(item[0], 99)))

    lines.append("Причины:")
    for key, cnt in ordered:
        label = categories.category_label(key)
        percent = cnt / total * 100
        lines.append(f"  • {label} — {cnt} ({percent:.0f}%)")


def _format_videos(lines, rows):
    if not rows:
        lines.append("Видео: скачиваний нет")
        return
    total = sum(cnt for _, _, cnt in rows)
    ok = sum(cnt for _, status, cnt in rows if status == "ok")
    by_platform = {}
    for platform, status, cnt in rows:
        by_platform[platform or "?"] = by_platform.get(platform or "?", 0) + cnt
    platform_part = " · ".join(f"{p} {c}" for p, c in by_platform.items())
    lines.append(f"Видео: попыток {total}, отправлено {ok} ({platform_part}); остальное — ошибки")


def _format_tokens_cost(lines, usage_rows):
    if not usage_rows:
        lines.append("Токены: записей нет")
        return
    total_prompt = sum(p or 0 for _, p, _ in usage_rows)
    total_completion = sum(c or 0 for _, _, c in usage_rows)
    total_cost = prices.tokens_cost(total_prompt, total_completion)
    lines.append(
        f"Токены: вход {_fmt_tokens(total_prompt)} · выход {_fmt_tokens(total_completion)} · "
        f"стоимость {_fmt_cost(total_cost)}"
    )
    parts = []
    for tag, prompt, completion in usage_rows:
        label = TAG_LABELS.get(tag or "", tag or "?")
        cost = prices.tokens_cost(prompt or 0, completion or 0)
        parts.append(f"{label} {_fmt_cost(cost)}")
    if parts:
        lines.append("По функциям: " + ", ".join(parts))


async def build_summary(chat_id, period="all") -> str:
    """Сводка по чату (или по всем чатам, если chat_id is None) за период."""
    start, end = _period_range(period)
    async with aiosqlite.connect(database.DB_NAME) as db:
        total, unique, commands, first_ts = await _messages_info(db, chat_id, start, end)
        users = await _top_users(db, chat_id, start, end)
        cmd_rows = await _top_commands(db, chat_id, start, end)
        should_rows, reason_rows = await _decisions_info(db, chat_id, start, end)
        video_rows = await _videos_info(db, chat_id, start, end)
        usage_rows = await _usage_by_tag(db, chat_id, start, end)
        chats = await _top_chats(db, start, end) if chat_id is None else []

    lines = [f"📊 Статистика: {_scope_label(chat_id, period)}"]
    lines += _format_messages_section(total, unique, period, first_ts)
    _format_users(lines, users)
    _format_decisions(lines, should_rows, reason_rows)
    _format_videos(lines, video_rows)
    _format_tokens_cost(lines, usage_rows)
    if cmd_rows:
        cmds = ", ".join(f"{cmd} — {cnt}" for cmd, cnt in cmd_rows)
        lines.append(f"Топ команд: {cmds}")
    if chats:
        top_chats = ", ".join(f"чат {cid} — {cnt}" for cid, cnt in chats)
        lines.append(f"Топ чатов: {top_chats}")
    return "\n".join(lines)


async def build_top(chat_id, period="all") -> str:
    """Топ активных пользователей, команд и заказчиков видео."""
    start, end = _period_range(period)
    async with aiosqlite.connect(database.DB_NAME) as db:
        users = await _top_users(db, chat_id, start, end)
        cmd_rows = await _top_commands(db, chat_id, start, end)
        video_users = await _top_video_users(db, chat_id, start, end)

    lines = [f"🏆 Топ: {_scope_label(chat_id, period)}"]
    if users:
        lines.append("По сообщениям: " + ", ".join(f"{n or '?'} — {c}" for n, c in users))
    else:
        lines.append("По сообщениям: данных нет")
    if cmd_rows:
        lines.append("По командам: " + ", ".join(f"{cmd} — {cnt}" for cmd, cnt in cmd_rows))
    if video_users:
        lines.append("Заказчики видео: " + ", ".join(f"{n or '?'} — {c}" for n, c in video_users))
    return "\n".join(lines)


async def build_video(chat_id, period="all") -> str:
    """Детализация скачиваний видео по платформам и статусам."""
    start, end = _period_range(period)
    async with aiosqlite.connect(database.DB_NAME) as db:
        rows = await _videos_info(db, chat_id, start, end)

    lines = [f"🎬 Видео: {_scope_label(chat_id, period)}"]
    if not rows:
        lines.append("Скачиваний нет")
        return "\n".join(lines)
    status_text = {
        "ok": "отправлено",
        "download_error": "ошибка скачивания",
        "send_error": "ошибка отправки",
    }
    for platform, status, cnt in rows:
        lines.append(f"{platform or '?'} · {status_text.get(status, status)}: {cnt}")
    return "\n".join(lines)


async def build_tokens(chat_id, period="all") -> str:
    """Токены и стоимость по функциям за период."""
    start, end = _period_range(period)
    async with aiosqlite.connect(database.DB_NAME) as db:
        rows = await _usage_by_tag(db, chat_id, start, end)

    lines = [f"🔢 Токены: {_scope_label(chat_id, period)}"]
    _format_tokens_cost(lines, rows)
    return "\n".join(lines)


def is_valid_section(section: str) -> bool:
    return section in ("summary", "top", "video", "tokens", "global")


def is_valid_period(period: str) -> bool:
    return period in PERIODS

