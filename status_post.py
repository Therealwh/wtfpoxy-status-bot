#!/usr/bin/env python3
"""Беззвучный постинг статуса веб-прокси в Telegram-канал.

По расписанию (12:00 и 21:00 МСК; запускает cron-job.org -> workflow_dispatch)
скрипт забирает данные со статус-страницы https://tgchat.run/status
и публикует в канал сообщение со статистикой и кнопками.

Только стандартная библиотека Python, зависимостей нет.

Запуск:
    BOT_TOKEN=... CHAT_ID=... python status_post.py            # отправить
    BOT_TOKEN=... CHAT_ID=... python status_post.py --dry-run  # только показать
"""

import html as html_mod
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

STATUS_URL = "https://tgchat.run/status"
PANEL_API_URL = "https://tgchat.run/api/v1/stats"
TG_API = "https://api.telegram.org/bot{token}/{method}"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
# Необязательный ключ публичного API панели (scope read) — добавит строку
# «Активных клиентов». Если не задан, бот работает без него.
PANEL_API_KEY = os.environ.get("PANEL_API_KEY", "")

# Кнопки под постом
BUTTONS = {
    "inline_keyboard": [
        [{"text": "🎁 Получить прокси бесплатно", "url": "https://t.me/webproxy_tgrobot"}],
        [{"text": "💎 Купить платный прокси", "url": "https://t.me/webproxy_panel_bot"}],
        [{"text": "🛡 Купить VPN с белыми списками", "url": "https://t.me/SafeLineVPNrobot"}],
        [{"text": "🛰 MTProto — если веб не работает", "url": "https://t.me/mtprxtgg"}],
    ]
}

MSK = timezone(timedelta(hours=3))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; wtfpoxy-status-bot/1.0)"}


def http_get(url, headers=None, timeout=20):
    """GET по https, возвращает текст или None при любой ошибке."""
    try:
        req = urllib.request.Request(url, headers=dict(HEADERS, **(headers or {})))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # сеть/таймаут/HTTP-код — не валим запуск
        print(f"[warn] GET {url} failed: {exc}")
        return None


def strip_tags(fragment):
    """Убирает теги и схлопывает пробелы — текстовый поток страницы."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Парсинг статус-страницы (она рендерится на сервере: значения в разметке)
# ---------------------------------------------------------------------------

def _metric(page, label):
    """Значение перед подписью метрики: >97.2%</div><div ...>Доступность из РФ (24ч)</div>"""
    m = re.search(
        r">([^<>]+)</\w+>\s*<[^>]*>\s*" + re.escape(label) + r"\s*<",
        page,
    )
    return m.group(1).strip() if m else None


def _service(text, name):
    """Строка сервиса из текстового потока: 'Web Proxy Работает · 100% за 30 дней · 74 мс'."""
    info = {}
    m = re.search(
        re.escape(name)
        + r"\s+([^\s·]+)\s*·\s*(\d+(?:\.\d+)?)%"
        r"(?:\s*за\s*30\s*дней\s*·\s*(\d+)\s*мс)?",
        text,
    )
    if not m:
        return info
    info["status"] = m.group(1)
    info["uptime"] = m.group(2) + "%"
    if m.group(3):
        info["ms"] = m.group(3) + " мс"
    return info


def parse_status(page):
    """Разбирает HTML статус-страницы в словарь с данными для поста."""
    stats = {}

    m = re.search(r"<h1>\s*<span[^>]*>(.*?)</span>\s*</h1>", page, re.S)
    if m:
        banner = strip_tags(m.group(1))
        stats["banner"] = banner
        stats["ok"] = "🟢" in banner or "работают" in banner.lower()

    stats["uptime30"] = _metric(page, "Аптайм 30 дней")
    stats["rf24"] = _metric(page, "Доступность из РФ (24ч)")

    text = strip_tags(page)
    stats["web"] = _service(text, "Web Proxy")
    stats["mtproto"] = _service(text, "MTProto")
    stats["panel"] = _service(text, "Панель и управление")
    return stats


def api_active_clients():
    """Число активных клиентов через публичный API панели (если задан ключ)."""
    if not PANEL_API_KEY:
        return None
    raw = http_get(
        PANEL_API_URL,
        headers={"Authorization": f"Bearer {PANEL_API_KEY}"},
        timeout=15,
    )
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return int(data["clients"]["active"])
    except Exception as exc:
        print(f"[warn] panel API parse failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Сборка и отправка
# ---------------------------------------------------------------------------

def _service_line(emoji, short, info):
    if not info:
        return None
    mark = "✅" if info.get("status") == "Работает" else "❌"
    parts = [f"{emoji} {short} — {mark} {info.get('status', '?')}"]
    if info.get("uptime"):
        parts.append(f"аптайм {info['uptime']}")
    if info.get("ms"):
        parts.append(f"отклик {info['ms']}")
    return " · ".join(parts)


def build_message(stats, clients=None):
    """HTML-текст поста. При полном отсутствии данных — упрощённый вариант."""
    now = datetime.now(MSK).strftime("%H:%M")
    head_time = f"📡 Статус tgchat.run · {now} МСК"

    if not stats:
        # Страница недоступна — пост всё равно выходит, но без цифр
        text = (
            "🟢 <b>Веб-прокси работают!</b>\n\n"
            f"{head_time}\n\n"
            "🌐 Web Proxy · 🔌 MTProto · ⚙️ Панель — в штатном режиме\n\n"
            "🚀 Пользуйтесь! 👇"
        )
        return text

    ok = stats.get("ok", True)
    if ok:
        title = "🟢 <b>Веб-прокси работают!</b>"
        outro = "🚀 Всё работает штатно. Пользуйтесь! 👇"
    else:
        title = f"⚠️ <b>{html_mod.escape(stats.get('banner') or 'Наблюдаются проблемы')}</b>"
        outro = "🛠 Уже разбираемся, скоро всё заработает!"

    lines = [title, "", head_time, ""]
    for emoji, short, key in (
        ("🌐", "Web Proxy", "web"),
        ("🔌", "MTProto", "mtproto"),
        ("⚙️", "Панель", "panel"),
    ):
        line = _service_line(emoji, short, stats.get(key) or {})
        if line:
            lines.append(line)

    tail = []
    if stats.get("rf24"):
        tail.append(f"🇷🇺 Доступность из РФ (24ч) — {stats['rf24']}")
    if stats.get("uptime30"):
        tail.append(f"📈 Аптайм за 30 дней — {stats['uptime30']}")
    if clients is not None:
        tail.append(f"👥 Активных клиентов — {clients}")
    if tail:
        lines += ["", *tail]

    lines += ["", outro]
    return "\n".join(lines)


def send_message(text):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_notification": True,  # беззвучно
        "disable_web_page_preview": True,
        "reply_markup": BUTTONS,
    }
    url = TG_API.format(token=BOT_TOKEN, method="sendMessage")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        answer = json.loads(resp.read().decode("utf-8"))
    if not answer.get("ok"):
        raise RuntimeError(f"Telegram API error: {answer}")
    return answer["result"]["message_id"]


def main():
    # консоль Windows может быть не UTF-8 — эмодзи не должны ронять вывод
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    dry = "--dry-run" in sys.argv
    page = http_get(STATUS_URL)
    stats = parse_status(page) if page else {}
    clients = api_active_clients()

    text = build_message(stats, clients)
    print(text)
    print("-" * 40)
    print(f"buttons: {len(BUTTONS['inline_keyboard'])}")

    if dry:
        print("[dry-run] сообщение не отправлено")
        return 0

    if not BOT_TOKEN or not CHAT_ID:
        print("[error] BOT_TOKEN / CHAT_ID не заданы")
        return 1

    message_id = send_message(text)
    print(f"[ok] отправлено, message_id={message_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
