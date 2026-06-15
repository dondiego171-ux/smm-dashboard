#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
АоТ — SMM Dashboard :: сборщик данных (только стандартная библиотека Python).

Запускается на вашем Mac (полный доступ к сети). Дописывает за СЕГОДНЯ снимок
по каждой соцсети в data/metrics_history.csv. Дневные приросты вычисляются на
этапе сборки дашборда из разницы снимков.

Запуск:  python3 collector.py
Конфиг:  config.json   (аккаунты + план)
Токены:  secrets.json  (в чат не передавать)

Зависимостей нет — работает на любом Mac «из коробки».
"""

import csv
import json
import os
import sys
import datetime as dt
import urllib.request
import urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
HISTORY = os.path.join(DATA_DIR, "metrics_history.csv")
LOG = os.path.join(DATA_DIR, "collector.log")

FIELDS = [
    "subscribers", "views_total", "views_day",
    "reactions_total", "reactions_day", "comments_total",
    "content_total", "content_day", "referrals_day",
    "engagement_rate_day",  # готовый % вовлечённости за день (есть у TGStat)
]


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_json(path, fallback=None):
    if not os.path.exists(path) and fallback and os.path.exists(fallback):
        log(f"[i] {os.path.basename(path)} не найден — использую {os.path.basename(fallback)}")
        path = fallback
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def http_get(url, params=None, headers=None, timeout=25):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url, params=None, body=None, headers=None, timeout=25):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    data = json.dumps(body or {}).encode("utf-8")
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ──────────────────────────────────────────────────────────────────────────
#  Коллекторы. Каждый возвращает dict {field: value}.
#  Нет токена / ошибка API → исключение, которое ловится снаружи (соцсеть пропускается).
# ──────────────────────────────────────────────────────────────────────────

def collect_vk(cfg, sec):
    token = sec.get("vk", {}).get("access_token", "").strip()
    if not token:
        raise RuntimeError("нет vk.access_token")
    v = "5.199"
    base = "https://api.vk.com/method/"

    gid = str(cfg.get("group_id", "")).strip()
    params = {"fields": "members_count,screen_name", "access_token": token, "v": v}
    # placeholder или пусто → автоопределение сообщества по групповому токену
    if gid and gid not in ("", "12345678"):
        params["group_id"] = gid.lstrip("-")
    r = http_get(base + "groups.getById", params)
    if "error" in r:
        raise RuntimeError(f"vk: {r['error'].get('error_msg')}")
    resp = r.get("response", {})
    groups = resp.get("groups") if isinstance(resp, dict) else resp
    grp = (groups or [{}])[0]
    gid_num = str(grp.get("id", gid.lstrip("-")))
    out = {"subscribers": grp.get("members_count")}

    # охват за вчера
    today = dt.date.today()
    try:
        r = http_get(base + "stats.get", {
            "group_id": gid_num, "interval": "day",
            "date_from": str(today - dt.timedelta(days=1)),
            "date_to": str(today - dt.timedelta(days=1)),
            "access_token": token, "v": v,
        })
        rows = r.get("response", [])
        if rows and isinstance(rows[0], dict):
            reach = rows[0].get("reach", {})
            if isinstance(reach, dict) and reach.get("reach") is not None:
                out["views_day"] = reach.get("reach")
    except Exception as e:
        log(f"[i] vk: подписчики получены, но охват недоступен ({e}). Нужен токен с правом stats.")
    return out


def collect_youtube(cfg, sec):
    key = sec.get("youtube", {}).get("api_key", "").strip()
    if not key:
        raise RuntimeError("нет youtube.api_key")
    cid = cfg.get("channel_id", "").strip()
    if not cid or cid.startswith("UCxxx"):
        raise RuntimeError("укажите реальный youtube.channel_id в config.json")
    r = http_get("https://www.googleapis.com/youtube/v3/channels",
                 {"part": "statistics", "id": cid, "key": key})
    items = r.get("items", [])
    if not items:
        raise RuntimeError("канал не найден / неверный channel_id или API key")
    s = items[0]["statistics"]
    return {
        "subscribers": int(s.get("subscriberCount", 0)),
        "views_total": int(s.get("viewCount", 0)),
        "content_total": int(s.get("videoCount", 0)),
    }


def collect_telegram(cfg, sec):
    """MTProto (Telethon), если есть сессия + api_id/api_hash — даёт подписчиков,
    просмотры, реакции и число публикаций за вчера. Иначе откат на Bot API (только подписчики)."""
    tg = sec.get("telegram", {})
    chat = cfg.get("channel", "").strip()
    if not chat:
        raise RuntimeError("укажите telegram.channel в config.json")

    # 1) TGStat API — приоритетно: подписчики, охват, вовлечённость, посты
    tgstat = str(tg.get("tgstat_token", "")).strip()
    if tgstat:
        return _telegram_tgstat(chat, tgstat)

    # 2) MTProto (Telethon) — если есть сессия
    session = str(tg.get("session", "")).strip()
    api_id = str(tg.get("api_id", "")).strip()
    api_hash = str(tg.get("api_hash", "")).strip()
    if session and api_id and api_hash:
        return _telegram_mtproto(chat, int(api_id), api_hash, session)

    # 3) Bot API — только число подписчиков
    bot = tg.get("bot_token", "").strip()
    if bot:
        r = http_get(f"https://api.telegram.org/bot{bot}/getChatMemberCount", {"chat_id": chat})
        if not r.get("ok"):
            raise RuntimeError(f"telegram (bot): {r.get('description')}")
        return {"subscribers": r["result"]}

    raise RuntimeError("нет telegram.tgstat_token, session (+api_id/api_hash) или bot_token")


def _telegram_tgstat(chat, token):
    r = http_get("https://api.tgstat.ru/channels/stat", {"token": token, "channelId": chat})
    if r.get("status") != "ok":
        raise RuntimeError(f"tgstat: {r.get('error') or r.get('error_code') or r}")
    d = r.get("response", {})
    out = {}
    if d.get("participants_count") is not None:
        out["subscribers"] = d["participants_count"]
    if d.get("daily_reach") is not None:
        out["views_day"] = d["daily_reach"]          # суммарный дневной охват
    if d.get("posts_count") is not None:
        out["content_total"] = d["posts_count"]      # всего публикаций (кумулятив)
    if d.get("er_percent") is not None:
        out["engagement_rate_day"] = d["er_percent"]  # ER % (реакции/пересылки/комментарии)
    return out


def _telegram_mtproto(chat, api_id, api_hash, session):
    try:
        from telethon.sync import TelegramClient
        from telethon.sessions import StringSession
        from telethon.tl.functions.channels import GetFullChannelRequest
    except ImportError:
        raise RuntimeError("нужен пакет telethon: pip install telethon --break-system-packages")

    import datetime as _dt
    yesterday = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=1)).date()

    with TelegramClient(StringSession(session), api_id, api_hash) as client:
        entity = client.get_entity(chat)
        full = client(GetFullChannelRequest(entity))
        subs = full.full_chat.participants_count

        views = reactions = posts = 0
        for msg in client.iter_messages(entity, limit=300):
            d = msg.date.date()
            if d > yesterday:
                continue
            if d < yesterday:
                break
            posts += 1
            views += (msg.views or 0)
            if getattr(msg, "reactions", None) and msg.reactions.results:
                reactions += sum(rr.count for rr in msg.reactions.results)

    return {
        "subscribers": subs,
        "views_day": views,
        "reactions_day": reactions,
        "content_day": posts,
    }


def collect_instagram(cfg, sec):
    token = sec.get("instagram", {}).get("access_token", "").strip()
    if not token:
        raise RuntimeError("нет instagram.access_token")
    uid = cfg.get("ig_user_id", "").strip()
    if not uid or uid.startswith("1784xxx"):
        raise RuntimeError("укажите реальный instagram.ig_user_id в config.json")
    r = http_get(f"https://graph.facebook.com/v19.0/{uid}",
                 {"fields": "followers_count,media_count", "access_token": token})
    if "error" in r:
        raise RuntimeError(f"instagram: {r['error'].get('message')}")
    return {"subscribers": r.get("followers_count"), "content_total": r.get("media_count")}


def collect_site(cfg, sec):
    src = cfg.get("source", "metrika")
    y = dt.date.today() - dt.timedelta(days=1)

    if src == "metrika":
        token = sec.get("metrika", {}).get("oauth_token", "").strip()
        if not token:
            raise RuntimeError("нет metrika.oauth_token")
        r = http_get("https://api-metrika.yandex.net/stat/v1/data", {
            "ids": cfg["counter_id"], "metrics": "ym:s:visits",
            "dimensions": "ym:s:lastTrafficSource",
            "date1": str(y), "date2": str(y),
            "filters": "ym:s:lastTrafficSource=='social'",
        }, headers={"Authorization": f"OAuth {token}"})
        total = sum(int(row["metrics"][0]) for row in r.get("data", []))
        return {"referrals_day": total}

    if src == "roistat":
        key = sec.get("roistat", {}).get("api_key", "").strip()
        project = sec.get("roistat", {}).get("project_id", "").strip()
        if not key or not project:
            raise RuntimeError("нужны roistat.api_key и roistat.project_id")
        # Аналитика Roistat: визиты по верхнему уровню источника (marker_level_1) за вчера.
        # Документация: https://help-en.roistat.com/API/methods/analytics/
        tz = "+0300"  # Europe/Moscow
        body = {
            "dimensions": ["marker_level_1"],
            "metrics": ["visits"],
            "period": {"from": f"{y}T00:00:00{tz}", "to": f"{y}T23:59:59{tz}"},
        }
        r = http_post_json("https://cloud.roistat.com/api/v1/project/analytics/data",
                           params={"project": project}, body=body,
                           headers={"Api-key": key})
        data = r.get("data")
        items = data[0].get("items", []) if isinstance(data, list) and data else []
        SOCIAL = ("social", "соц", "vk", "вконтакте", "telegram", "телеграм",
                  "instagram", "facebook", "youtube", "ok.ru", "одноклассник",
                  "tiktok", "дзен", "zen")
        total = 0
        breakdown = []
        for it in items:
            dim = it.get("dimensions", {}).get("marker_level_1", {})
            name = str(dim.get("value", "")).lower()
            title = str(dim.get("title", "")).lower()
            try:
                visits = int(float(it.get("metrics", {}).get("visits", {}).get("value", 0)))
            except (TypeError, ValueError):
                visits = 0
            breakdown.append((title or name, visits))
            if any(s in name or s in title for s in SOCIAL):
                total += visits
        if breakdown:
            log("[i] roistat каналы за " + str(y) + ": " +
                ", ".join(f"{n}={v}" for n, v in breakdown[:15]))
        if total == 0 and breakdown:
            log("[i] roistat: соцканалы не распознаны по названиям — посмотрите список каналов выше "
                "и при необходимости расширьте список SOCIAL в collect_site().")
        return {"referrals_day": total}

    raise RuntimeError(f"источник '{src}' не поддерживается")


COLLECTORS = {
    "vk": collect_vk, "youtube": collect_youtube, "telegram": collect_telegram,
    "instagram": collect_instagram, "site": collect_site,
}


def append_rows(date_str, network, values):
    os.makedirs(DATA_DIR, exist_ok=True)
    new = not os.path.exists(HISTORY)
    with open(HISTORY, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "network", "field", "value"])
        for field, val in values.items():
            if val is not None:
                w.writerow([date_str, network, field, val])


def main():
    cfg = load_json(os.path.join(BASE, "config.json"), os.path.join(BASE, "config.example.json"))
    sec = load_json(os.path.join(BASE, "secrets.json"), os.path.join(BASE, "secrets.example.json"))
    if not cfg:
        log("[!] Нет config.json — нечего собирать."); sys.exit(1)

    today = dt.date.today().isoformat()
    collected = 0
    for name, ncfg in cfg.get("networks", {}).items():
        if not ncfg.get("enabled", True):
            continue
        fn = COLLECTORS.get(name)
        if not fn:
            continue
        try:
            values = {k: v for k, v in fn(ncfg, sec).items() if k in FIELDS and v is not None}
            if values:
                append_rows(today, name, values)
                collected += 1
                log(f"[+] {name}: {values}")
            else:
                log(f"[i] {name}: данные не получены (пусто)")
        except Exception as e:
            log(f"[-] {name}: пропущено — {e}")

    log(f"[=] Готово. Соцсетей собрано: {collected}. История: {HISTORY}")


if __name__ == "__main__":
    main()
