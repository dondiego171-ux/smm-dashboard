#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Одноразовый вход в Telegram (MTProto) — создаёт «ключ-сессию» для автоматического сбора.

Запускать НЕ нужно вручную: проще двойным кликом по tg_login.command.
Либо:  python3 tg_login.py

Что делает:
  1. Берёт api_id/api_hash из secrets.json (спросит, если их там нет).
  2. Просит номер телефона и код из Telegram (и пароль, если включена 2FA).
  3. Сохраняет строку-сессию в secrets.json → telegram.session.
После этого сбор Telegram работает сам, повторный вход не нужен.
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SECRETS = os.path.join(BASE, "secrets.json")

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    raise SystemExit("Нужен пакет telethon. Установите:  pip3 install telethon --break-system-packages")


def main():
    sec = {}
    if os.path.exists(SECRETS):
        with open(SECRETS, encoding="utf-8") as f:
            sec = json.load(f)
    tg = sec.setdefault("telegram", {})

    api_id = str(tg.get("api_id", "")).strip()
    api_hash = str(tg.get("api_hash", "")).strip()
    if not api_id:
        api_id = input("Введите api_id (с my.telegram.org): ").strip()
    if not api_hash:
        api_hash = input("Введите api_hash (с my.telegram.org): ").strip()

    print("\nСейчас попросит номер телефона и код из Telegram. Поехали...\n")
    with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        session_str = client.session.save()
        me = client.get_me()
        print(f"\n✅ Вошли как: {me.first_name} (@{me.username})")

    tg["api_id"] = api_id
    tg["api_hash"] = api_hash
    tg["session"] = session_str
    with open(SECRETS, "w", encoding="utf-8") as f:
        json.dump(sec, f, ensure_ascii=False, indent=2)

    print("\n✅ Сессия сохранена в secrets.json (поле telegram.session).")
    print("Готово — Telegram теперь собирается автоматически.")
    print("\nДля GitHub позже понадобится значение этой сессии — покажу, как достать.")


if __name__ == "__main__":
    main()
