# ChoochBotTgDemo

Telegram-бот для групповых чатов (`group`/`supergroup`): ведёт диалоги через DeepSeek AI, помнит историю разговора и скачивает видео по ссылкам прямо в чат. Скачивание работает без cookies.

## Возможности

- ИИ-общение с памятью: история в SQLite (до 100 последних сообщений), бот сам решает, когда отвечать; длинные диалоги автоматически сжимаются в саммари.
- Личность чата настраивается через `/set_personality`, просматривается через `/get_personality`.
- Скачивание видео по ссылкам (mp4):
  - YouTube — yt-dlp + ffmpeg;
  - TikTok — Playwright (персистентный headless-Chromium);
  - PornHub — yt-dlp с impersonation (curl_cffi).
- Реакция на слово «баг» в чате.
- Исправление раскладки: команда `/transliterate` (ru/en, азбука Морзе) и автоисправление текста в неправильной раскладке через LLM-гейт.
- Функции включаются/выключаются правкой `filters/handlers.txt`; индивидуально для чата — командами `/features` (статус) и `/feature <имя> on|off`. Закомментированная в файле функция запрещена глобально и не включается ни в одном чате.
- Статистика: `/stats` — обработанные сообщения, активные пользователи, команды, скачивания видео, токены и стоимость DeepSeek по функциям, с разбивкой по периодам.

## Стек

Python 3.14, aiogram 3.x (Long Polling), DeepSeek API (`openai`, модель `deepseek-chat`), SQLite (`aiosqlite`), yt-dlp, ffmpeg, Playwright, curl_cffi, pydantic-settings.

## Структура проекта

```
.
├── main.py                # точка входа: Bot + Dispatcher + Long Polling
├── config.py              # настройки из .env (pydantic-settings)
├── requirements.txt       # зависимости
├── ffmpeg.exe             # слияние/перекодирование видео
├── AI_module/
│   ├── pipeline.py        # оркестрация болталки: гейт → решение → ответ → сжатие
│   ├── decision.py        # фильтр «отвечать/нет» (temp=0, слово «да/нет»)
│   ├── responder.py       # генератор ответа (temp=0.7)
│   ├── summarizer.py      # сжатие истории в саммари (безопасная транзакция)
│   ├── memory.py          # доступ к истории/саммари/личности + per-chat lock
│   ├── llm.py             # DeepSeek-клиент
│   ├── prompts.py         # загрузчик промптов из prompts/*.txt
│   ├── database.py        # схема SQLite (chat_history, chat_meta)
│   └── prompts/           # промпты и критерии фильтра (txt)
├── handlers/
│   ├── some_logic.py      # роутер: команды, монитор сообщений, URL-обработка
│   └── features.py        # per-chat состояние функций (запреты из handlers.txt приоритетны)
├── load_video/
│   ├── sender.py          # декоратор @send_video: скачивание + отправка + удаление файла
│   ├── youtube.py         # скачивание YouTube (yt-dlp)
│   ├── pornhub.py         # скачивание PornHub (перебор форматов, лимит 48 МБ)
│   └── tiktok.py          # персистентный Playwright-браузер + скачивание TikTok
├── stats/
│   ├── __init__.py        # публичный API статистики
│   ├── db.py              # таблицы событий статистики
│   ├── collect.py         # запись событий (сообщения, команды, видео, токены)
│   ├── prices.py          # тариф DeepSeek из prices.txt (перечитывание по TTL)
│   ├── report.py          # текстовые отчёты по чатам и периодам
│   └── prices.txt         # цены USD за 1M токенов
├── translating_msgs/
│   ├── keyboard_layout.py # исправление раскладки (ru/en)
│   ├── morse_coding.py    # азбука Морзе (кодирование/декодирование)
│   ├── auto_correction.py # автоисправление раскладки через LLM-гейт
│   ├── prompts.py         # загрузчик промптов из prompts/*.txt
│   └── prompts/           # промпт детектора раскладки (txt)
└── filters/
    ├── filters.py         # декоратор @get_filter_list и проверки URL
    ├── handlers.txt       # тогглы функций
    ├── youtube.txt        # подстроки доменов YouTube
    ├── tiktok.txt         # подстроки доменов TikTok
    └── pornhub.txt        # подстроки доменов PornHub
```

## Установка

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

Браузер Playwright нужен для скачивания TikTok.

## Конфигурация

В корне создаётся файл `.env`:

```env
BOT_TOKEN=<токен бота от @BotFather>
AI_API_TOKEN=<ключ DeepSeek API>
```

## Запуск

```bash
python main.py
```

При старте создаётся схема SQLite (`AI_module/bot_talker_memory.db`) и поднимается браузер Playwright; при остановке он закрывается. Для чтения всех сообщений группы у бота в BotFather должен быть выключен Privacy Mode.

## Команды

| Команда | Описание |
|---|---|
| `/help` | Справка |
| `/set_personality <текст>` | Задать личность чата |
| `/get_personality` | Показать текущую личность |
| `/clear` | Стереть всю память чата |
| `/clear N` | Стереть последние N сообщений |
| `/transliterate [from] [to] [text]` | Исправить раскладку (ru/en) или азбука Морзе: `/transliterate en ru Ghbdtn` |
| `/features` | Показать, какие функции активны в этом чате |
| `/feature <имя> on\|off` | Включить/выключить функцию в этом чате |
| `/stats [раздел] [период]` | Статистика: `summary`/`top`/`video`/`tokens`/`global`; период `all`/`today`/`yesterday`/`week`/`month` |

## Скачивание видео

По ссылке в чате платформа определяется по подстрокам из `filters/*.txt` (регистр не важен, поддерживаются ссылки-гипертекст). Скачанный файл отправляется в чат и удаляется с диска.

- YouTube — yt-dlp (клиенты tv/visionos/web_embedded + JS-рантайм node), ffmpeg-merge в mp4 (h264+aac).
- TikTok — Playwright: CDN-ссылка извлекается из `__UNIVERSAL_DATA_FOR_REHYDRATION__`.
- PornHub — форматы перебираются от лучшего к худшему, не влезающие в лимит отсекаются через `max_filesize`.

## Тогглы функций

В `filters/handlers.txt` строка без `#` — функция разрешена (по умолчанию включена во всех чатах), с `#` — запрещена глобально (не включается ни в одном чате). Внутри конкретного чата функцию можно выключить/включить командой `/feature <имя> on|off`; запрет из файла всегда приоритетнее выбора чата.

```text
youtube
tiktok
pornhub
bug
AI_chating_responce
AI_chating_memory
transliterate_auto
stats
```

## Ограничения

- Только группы (`group`/`supergroup`); требуется выключенный Privacy Mode.
- Лимит Telegram на размер видео — 48 МБ.
- Скорость скачивания с PornHub зависит от CDN сервера.
- TikTok/WAF может отклонять запросы — иногда нужен повтор.
- `requirements.txt` сохранён в UTF-16.
- Python 3.14 (release candidate) — возможна несовместимость пакетов.

## Планы

- Замена тега `@all` (удалён Telegram).
- Поздравление участников с днём рождения.
- Инициация разговора ботом.
- Поиск картинок по описанию (SearXNG).
- Реакция на ссылки по содержимому (чтение веб-страниц).

## Лицензия

Лицензия не указана.