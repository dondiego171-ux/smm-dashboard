#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерирует ДЕМО-историю в data/metrics_history.csv (~35 дней), чтобы увидеть,
как выглядит дашборд до подключения реальных токенов.

Запуск:  python3 seed_demo.py  &&  python3 build_dashboard.py

После подключения реальных токенов просто удалите data/metrics_history.csv
и запускайте collector.py — он начнёт писать настоящие данные.
"""
import csv, os, random, datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)
HIST = os.path.join(DATA, "metrics_history.csv")
random.seed(7)

DAYS = 35
start = dt.date.today() - dt.timedelta(days=DAYS - 1)

# стартовые кумулятивы и дневные диапазоны
NETS = {
    "vk":        {"subs": 84000, "subs_g": (40, 160),  "views_day": (12000, 24000), "react_t": 320000, "react_d": (300, 700), "cont_t": 410, "cont_d": (0, 3)},
    "telegram":  {"subs": 52000, "subs_g": (30, 120),  "views_day": (8000, 16000),  "react_t": 180000, "react_d": (150, 400), "cont_t": 600, "cont_d": (1, 4)},
    "instagram": {"subs": 96000, "subs_g": (50, 200),  "views_day": (14000, 26000), "react_t": 450000, "react_d": (500, 1100),"cont_t": 300, "cont_d": (0, 2)},
    "youtube":   {"subs": 41000, "subs_g": (10, 70),   "views_total": 3200000, "views_dg": (6000, 13000), "react_t": 95000, "react_d": (120, 350), "cont_t": 140, "cont_d": (0, 1)},
}

rows = []
for net, p in NETS.items():
    subs = p["subs"]; react = p["react_t"]; cont = p["cont_t"]
    vtot = p.get("views_total")
    for i in range(DAYS):
        d = (start + dt.timedelta(days=i)).isoformat()
        subs += random.randint(*p["subs_g"])
        react += random.randint(*p["react_d"])
        cont += random.randint(*p["cont_d"])
        rows.append([d, net, "subscribers", subs])
        rows.append([d, net, "reactions_total", react])
        rows.append([d, net, "content_total", cont])
        if "views_day" in p:
            rows.append([d, net, "views_day", random.randint(*p["views_day"])])
        if vtot is not None:
            vtot += random.randint(*p["views_dg"])
            rows.append([d, net, "views_total", vtot])

# сайт: переходы из соцсетей за день
for i in range(DAYS):
    d = (start + dt.timedelta(days=i)).isoformat()
    rows.append([d, "site", "referrals_day", random.randint(180, 420)])

with open(HIST, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["date", "network", "field", "value"]); w.writerows(rows)

print(f"[+] Демо-история записана: {HIST}  ({len(rows)} строк, {DAYS} дней)")
