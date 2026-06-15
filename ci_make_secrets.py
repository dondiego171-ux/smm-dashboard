#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собирает secrets.json из переменных окружения (GitHub Secrets) — для запуска
в GitHub Actions. Токены НИКОГДА не лежат в репозитории, только в Secrets.
Локально этот файл не нужен: там есть свой secrets.json.
"""
import json, os

secrets = {
    "vk": {"access_token": os.environ.get("VK_TOKEN", "")},
    "telegram": {
        "tgstat_token": os.environ.get("TGSTAT_TOKEN", ""),
        "api_id": os.environ.get("TELEGRAM_API_ID", ""),
        "api_hash": os.environ.get("TELEGRAM_API_HASH", ""),
        "session": os.environ.get("TELEGRAM_SESSION", ""),
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    },
    "youtube": {"api_key": os.environ.get("YOUTUBE_API_KEY", "")},
    "instagram": {"access_token": os.environ.get("INSTAGRAM_TOKEN", "")},
    "metrika": {"oauth_token": os.environ.get("METRIKA_TOKEN", "")},
    "roistat": {
        "api_key": os.environ.get("ROISTAT_API_KEY", ""),
        "project_id": os.environ.get("ROISTAT_PROJECT_ID", ""),
    },
}

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "secrets.json"), "w", encoding="utf-8") as f:
    json.dump(secrets, f, ensure_ascii=False, indent=2)

print("secrets.json собран из переменных окружения.")
