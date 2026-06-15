# АоТ — SMM Dashboard

Живой HTML-дашборд контент-маркетинга по VK, Telegram, YouTube и переходам на сайт (Roistat).
Instagram можно подключить позже. Слой 1 (сводный daily-мониторинг) — готов. Слой 2
(эффективность каждой единицы контента) — добавляется отдельно.

## Как это работает

```
collector.py        тянет данные по API → пишет историю в data/metrics_history.csv
build_dashboard.py  считает дневные метрики + план/факт → пересобирает dashboard.html
dashboard.html      открывается двойным кликом, всегда показывает последний срез
```

Скрипты используют только стандартную библиотеку Python — никакого `pip install` не нужно.

**Важно про автообновление.** Сбор данных запускается НА вашем Mac (через launchd), а не внутри
Claude: песочница Claude не имеет доступа к API соцсетей (VK/Telegram/YouTube/Google заблокированы
белым списком сети). На Mac доступ полный, токены остаются у вас, сбор идёт даже когда Claude закрыт.

## Подключение (по шагам)

1. **Конфиги уже созданы:** `config.json` и `secrets.json`.
2. **Впишите токены** в `secrets.json` (подсказки `_how` внутри файла). VK-токен уже добавлен.
   **`secrets.json` никому не передавайте и не вставляйте в чат.**
3. **Впишите аккаунты** в `config.json`:
   - `vk.group_id` — можно оставить пустым (определится по токену);
   - `telegram.channel` — `@username` вашего канала (бот из secrets.json должен быть его админом);
   - `youtube.channel_id` — реальный ID (начинается с `UC...`);
   - Roistat — `api_key` и `project_id` в `secrets.json`.
4. **Проверьте подключения:**
   ```bash
   python3 test_connection.py
   ```
   Для каждой соцсети покажет ✅/❌ и что удалось получить. Токены не выводятся.
5. **Уберите демо-историю** перед первым реальным сбором:
   ```bash
   rm data/metrics_history.csv
   ```
6. **Первый сбор и сборка:**
   ```bash
   python3 collector.py && python3 build_dashboard.py
   ```
   Откройте `dashboard.html` двойным кликом.

Любую соцсеть можно отключить (`enabled: false`) — она будет пропущена.

## Автообновление (ежедневно, на Mac)

Двойной клик по **`setup_autorefresh.command`** (или `bash setup_autorefresh.command`).
Установит задачу launchd на ежедневный запуск в 07:30. Время меняется в начале файла (HOUR/MINUTE).

```bash
# проверить разовый запуск прямо сейчас:
launchctl kickstart -k gui/$(id -u)/com.aot.smmdashboard
# снять автозапуск:
bash uninstall_autorefresh.command
```

Логи запусков: `data/cron.log`. launchd выполняет задачу, когда вы залогинены; если Mac спал —
при ближайшем пробуждении.

В приложении Claude дополнительно настроена утренняя проверка (09:00): она читает `data/cron.log`
и предупреждает, если вчерашний сбор не отработал или данные устарели.

## Где брать токены

| Соцсеть | Что нужно | Где взять |
|---|---|---|
| VK | групповой токен с правами `stats,groups` | Настройки сообщества → Работа с API |
| Telegram | `bot_token` (бот — админ канала) | @BotFather |
| Telegram (просмотры постов) | `api_id` + `api_hash` (MTProto) | my.telegram.org |
| YouTube | API key (YouTube Data API v3) + `channel_id` | Google Cloud Console |
| Roistat | `api_key` + `project_id` | Roistat → Интеграции/API |
| Instagram (позже) | long-lived токен Graph API | Meta for Developers |

## Ограничения по источникам

- **Telegram:** Bot API отдаёт только число подписчиков. Просмотры постов требуют MTProto
  (Telethon) — допишется в `collector.py` отдельно.
- **Roistat:** отчёт соцтрафика строится по уровням маркера; если за вчера выходит 0 — поля
  `dimensions/filters` в `collect_site()` нужно подстроить под ваш проект (в логе будет подсказка).
- **Instagram:** только бизнес-аккаунт через Graph API; иначе метрики вносятся вручную в
  `data/metrics_history.csv` или из LiveDune.

## Метрики

Просмотры · Новые подписки · Реакции · Вовлечённость (реакции/просмотры) · Контент (новые
публикации) · Переходы на сайт. Кумулятивные счётчики хранятся снимками по дням; дневные приросты
считаются как разница соседних снимков.

## План / факт

План на месяц — в `config.json → plan`. У каждой метрики прогресс-бар: 🟢 в графике
(прогресс ≥ доли прошедшего месяца), 🟡 отставание, 🔴 сильное отставание.

## Структура

```
config.json / config.example.json     аккаунты + план
secrets.json / secrets.example.json   токены (в чат не передавать)
test_connection.py                    проверка токенов (✅/❌)
collector.py                          сбор по API (только stdlib)
build_dashboard.py                    сборка HTML
seed_demo.py                          демо-данные
setup_autorefresh.command             установка ежедневного автозапуска (launchd)
uninstall_autorefresh.command         снятие автозапуска
dashboard.html                        результат (открывать в браузере)
data/metrics_history.csv              история снимков
data/cron.log, collector.log          логи
```
