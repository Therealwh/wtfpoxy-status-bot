# wtfpoxy-status-bot

Беззвучные посты о статусе веб-прокси в Telegram-канал [wtfpoxy](https://t.me/wtfpoxy) — **2 раза в сутки: 12:00 и 21:00 МСК**.

Бот забирает данные со статус-страницы [tgchat.run/status](https://tgchat.run/status) (она рендерится панелью TGGATE на сервере — цифры лежат прямо в HTML) и публикует сообщение с кнопками. Только стандартная библиотека Python — **зависимостей 0**.

## Как выглядит пост

```
🟢 Веб-прокси работают!

📡 Статус tgchat.run · 12:00 МСК

🌐 Web Proxy — ✅ Работает · аптайм 100% · отклик 74 мс
🔌 MTProto — ✅ Работает · аптайм 100%
⚙️ Панель — ✅ Работает · аптайм 100%

🇷🇺 Доступность из РФ (24ч) — 97.2%
📈 Аптайм за 30 дней — 100%

🚀 Всё работает штатно. Пользуйтесь! 👇
```

Кнопки под постом:

| Кнопка | Ведёт на |
|---|---|
| 🎁 Получить прокси бесплатно | [@webproxy_tgrobot](https://t.me/webproxy_tgrobot) |
| 💎 Купить платный прокси | [@webproxy_panel_bot](https://t.me/webproxy_panel_bot) |
| 🛡 Купить VPN с белыми списками | [@SafeLineVPNrobot](https://t.me/SafeLineVPNrobot) |

Пост отправляется **беззвучно** (`disable_notification`). Если статус-страница недоступна или в ней проблемы — пост всё равно выйдет (упрощённый текст без цифр), если сервис в красной зоне — заголовок и концовка меняются на «проблемные».

## Настройка (один раз)

1. **Бот**: создать бота у [@BotFather](https://t.me/BotFather) → получить токен.
2. **Права**: добавить бота **администратором** канала `wtfpoxy` с правом «Публикация сообщений».
3. **Секреты GitHub** (Settings → Secrets and variables → Actions):

   ```bash
   gh secret set BOT_TOKEN --repo Therealwh/wtfpoxy-status-bot   # токен от BotFather
   gh secret set CHAT_ID  --repo Therealwh/wtfpoxy-status-bot   # -1003559855369
   ```

   Необязательно: `PANEL_API_KEY` — ключ публичного API панели (scope `read`, создаётся в админке TGGATE: Настройки → API-ключи). Добавит в пост строку «👥 Активных клиентов».

4. **Расписание**: в [cron-job.org](https://cron-job.org) создать **две** задачи, обе `POST`:

   | Задача | Расписание (UTC) | По-русски |
   |---|---|---|
   | утренняя | `0 9 * * *` | 12:00 МСК |
   | вечерняя | `0 18 * * *` | 21:00 МСК |

   URL и заголовки обеих задач:

   ```
   POST https://api.github.com/repos/Therealwh/wtfpoxy-status-bot/dispatches
   Accept: application/vnd.github+json
   Authorization: Bearer <GITHUB_PAT>
   User-Agent: cron-job.org
   Content-Type: application/json
   {"event_type":"post"}
   ```

   `<GITHUB_PAT>` — персональный токен GitHub с правом `repo` (fine-grained: Contents + Actions на этот репозиторий). Без `User-Agent` GitHub API отвечает 403 — обязательно укажите.

   Альтернатива без cron-job.org: добавить в `.github/workflows/post.yml` блок `schedule` (cron `0 9,18 * * *`), но GitHub может сдвигать запуск на несколько минут.

## Запуск вручную

```bash
# локально, без отправки
python status_post.py --dry-run

# локально, с отправкой
BOT_TOKEN=... CHAT_ID=-1003559855369 python status_post.py

# из GitHub: вкладка Actions → Post status to channel → Run workflow
```
