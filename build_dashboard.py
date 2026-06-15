#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
АоТ — SMM Dashboard :: сборка живого HTML-дашборда.

Читает data/metrics_history.csv (снимки) + config.json (план), вычисляет
дневные метрики и факт за текущий месяц, пишет самодостаточный dashboard.html
со встроенными данными. Файл открывается двойным кликом, всегда показывает
последние собранные данные.

Запуск:  python3 build_dashboard.py
"""

import csv
import json
import os
import datetime as dt
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
HISTORY = os.path.join(DATA_DIR, "metrics_history.csv")
OUT = os.path.join(BASE, "dashboard.html")

NET_LABELS = {"vk": "VK", "telegram": "Telegram", "instagram": "Instagram",
              "youtube": "YouTube", "site": "Сайт (переходы)"}
NET_COLORS = {"vk": "#4a76a8", "telegram": "#2aabee", "instagram": "#e1306c",
              "youtube": "#ff0000", "site": "#22c55e"}

# Метрики, отображаемые на дашборде, и их тип агрегации за месяц.
METRICS = [
    ("views",           "Просмотры",      "sum"),
    ("new_subs",        "Новые подписки", "sum"),
    ("reactions",       "Реакции",        "sum"),
    ("engagement_rate", "Вовлечённость",  "avg"),
    ("content",         "Контент",        "sum"),
    ("referrals",       "Переходы",       "sum"),
]


def load_config():
    for name in ("config.json", "config.example.json"):
        p = os.path.join(BASE, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return {}


def load_history():
    """-> snap[network][date][field] = float"""
    snap = defaultdict(lambda: defaultdict(dict))
    if not os.path.exists(HISTORY):
        return snap
    with open(HISTORY, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                snap[row["network"]][row["date"]][row["field"]] = float(row["value"])
            except (ValueError, KeyError):
                continue
    return snap


def derive_daily(net_snaps):
    """Из снимков по датам -> канонические дневные метрики по датам."""
    dates = sorted(net_snaps.keys())
    daily = {}
    prev = None
    for d in dates:
        s = net_snaps[d]
        p = net_snaps[prev] if prev else {}
        rec = {}

        # просмотры: дневные напрямую, иначе дельта кумулятива
        if "views_day" in s:
            rec["views"] = s["views_day"]
        elif "views_total" in s and "views_total" in p:
            rec["views"] = max(0.0, s["views_total"] - p["views_total"])

        # новые подписки = дельта подписчиков
        if "subscribers" in s:
            rec["subscribers"] = s["subscribers"]
            if "subscribers" in p:
                rec["new_subs"] = s["subscribers"] - p["subscribers"]

        # реакции
        if "reactions_day" in s:
            rec["reactions"] = s["reactions_day"]
        elif "reactions_total" in s and "reactions_total" in p:
            rec["reactions"] = max(0.0, s["reactions_total"] - p["reactions_total"])

        # контент (новые публикации)
        if "content_day" in s:
            rec["content"] = s["content_day"]
        elif "content_total" in s and "content_total" in p:
            rec["content"] = max(0.0, s["content_total"] - p["content_total"])

        # переходы
        if "referrals_day" in s:
            rec["referrals"] = s["referrals_day"]

        # вовлечённость: готовый % (TGStat) приоритетнее, иначе реакции/просмотры*100
        if "engagement_rate_day" in s:
            rec["engagement_rate"] = s["engagement_rate_day"]
        elif rec.get("views"):
            rec["engagement_rate"] = round(rec.get("reactions", 0) / rec["views"] * 100, 2)

        daily[d] = rec
        prev = d
    return daily, dates


def month_bounds(today):
    first = today.replace(day=1)
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return first, nxt


def build():
    cfg = load_config()
    plan_cfg = cfg.get("plan", {})
    snaps = load_history()
    today = dt.date.today()
    m_first, m_next = month_bounds(today)
    days_in_month = (m_next - m_first).days
    day_of_month = today.day
    time_progress = day_of_month / days_in_month

    out_networks = {}
    totals = defaultdict(float)

    for net, net_snaps in snaps.items():
        daily, dates = derive_daily(net_snaps)

        series = {"dates": dates}
        for key, _, _ in METRICS:
            series[key] = [daily.get(d, {}).get(key) for d in dates]
        series["subscribers"] = [daily.get(d, {}).get("subscribers") for d in dates]

        # факт за текущий месяц
        fact = {}
        for key, _, agg in METRICS:
            vals = [daily[d].get(key) for d in dates
                    if m_first.isoformat() <= d < m_next.isoformat() and daily[d].get(key) is not None]
            if not vals:
                fact[key] = 0
            elif agg == "avg":
                fact[key] = round(sum(vals) / len(vals), 2)
            else:
                fact[key] = round(sum(vals), 2)

        plan = plan_cfg.get(net, {})
        progress = {}
        for key, _, _ in METRICS:
            pv = plan.get(key)
            if pv:
                progress[key] = round(fact.get(key, 0) / pv * 100, 1)

        subs_vals = [v for v in series["subscribers"] if v is not None]
        latest_subs = subs_vals[-1] if subs_vals else None

        out_networks[net] = {
            "label": NET_LABELS.get(net, net),
            "color": NET_COLORS.get(net, "#888"),
            "series": series,
            "fact": fact,
            "plan": plan,
            "progress": progress,
            "latest_subscribers": latest_subs,
        }

        for key in ("views", "new_subs", "reactions", "content", "referrals"):
            totals[key] += fact.get(key, 0)
        if latest_subs:
            totals["subscribers"] += latest_subs

    dash = {
        "project": cfg.get("project", "SMM Dashboard"),
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "current_month": today.strftime("%B %Y"),
        "time_progress": round(time_progress * 100, 1),
        "day_of_month": day_of_month,
        "days_in_month": days_in_month,
        "networks": out_networks,
        "totals": dict(totals),
        "metrics": [{"key": k, "label": l, "agg": a} for k, l, a in METRICS],
    }

    html = HTML_TEMPLATE.replace("/*__DATA__*/", json.dumps(dash, ensure_ascii=False))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[+] Дашборд собран: {OUT}")
    print(f"    Соцсетей: {len(out_networks)} | месяц пройден на {dash['time_progress']}%")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>АоТ — SMM Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#0f1117; --panel:#181b24; --panel2:#1f2330; --line:#2a2f3d;
    --txt:#e8eaf0; --muted:#9aa0ad; --good:#22c55e; --warn:#f59e0b; --bad:#ef4444;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    padding:28px 32px 64px}
  h1{font-size:22px;margin:0 0 2px}
  .sub{color:var(--muted);font-size:13px}
  header{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px;margin-bottom:22px}
  .timebar{margin-top:8px;font-size:12px;color:var(--muted)}
  .section-title{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:30px 0 12px}
  .totals{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
  .tcard{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
  .tcard .v{font-size:26px;font-weight:700;margin-top:4px}
  .tcard .l{font-size:12px;color:var(--muted)}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
  .net{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px;overflow:hidden}
  .net h3{margin:0 0 2px;font-size:16px;display:flex;align-items:center;gap:8px}
  .dot{width:11px;height:11px;border-radius:50%}
  .subs{font-size:12px;color:var(--muted);margin-bottom:12px}
  .metrics{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
  .m{background:var(--panel2);border-radius:10px;padding:10px 12px}
  .m .ml{font-size:11px;color:var(--muted)}
  .m .mv{font-size:18px;font-weight:600;margin-top:2px}
  .bar{height:6px;border-radius:4px;background:#2a2f3d;margin-top:8px;overflow:hidden}
  .bar i{display:block;height:100%;border-radius:4px}
  .pf{font-size:10px;color:var(--muted);margin-top:4px;display:flex;justify-content:space-between}
  canvas{margin-top:6px}
  .empty{color:var(--muted);padding:40px;text-align:center;border:1px dashed var(--line);border-radius:14px}
  .legend-note{font-size:11px;color:var(--muted);margin-top:6px}
  footer{margin-top:36px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
  code{background:var(--panel2);padding:2px 6px;border-radius:5px}
</style>
</head>
<body>
<header>
  <div>
    <h1 id="title">SMM Dashboard</h1>
    <div class="sub" id="subtitle"></div>
  </div>
  <div class="sub" id="genat"></div>
</header>
<div id="timebar" class="timebar"></div>

<div class="section-title">Итого за месяц — все соцсети</div>
<div class="totals" id="totals"></div>

<div class="section-title">По соцсетям — план / факт и динамика</div>
<div class="grid" id="grid"></div>

<footer>
  Слой 1 (сводный daily) активен. Слой 2 — эффективность каждой единицы контента — добавляется отдельно.<br>
  Данные обновляются ежедневно скриптом сбора. Файл всегда показывает последний собранный срез.
</footer>

<script>
const DASH = /*__DATA__*/;

const fmt = n => n==null ? "—" :
  (Math.abs(n)>=1000 ? n.toLocaleString("ru-RU",{maximumFractionDigits:0})
                     : (Number.isInteger(n)? n : n.toFixed(2)));
const fmtMetric = (key,v) => v==null ? "—" : (key==="engagement_rate" ? v.toFixed(2)+"%" : fmt(v));

document.getElementById("title").textContent = DASH.project;
document.getElementById("subtitle").textContent = "Сводный мониторинг · " + DASH.current_month;
document.getElementById("genat").textContent = "Обновлено: " + DASH.generated_at;
document.getElementById("timebar").innerHTML =
  `Прошло месяца: <b>${DASH.time_progress}%</b> (день ${DASH.day_of_month} из ${DASH.days_in_month}). ` +
  `Метрики план/факт сравнивайте с этой долей: если прогресс ≥ ${DASH.time_progress}% — идём в графике.`;

// Итоги
const TOTALS = [
  ["views","Просмотры"],["new_subs","Новые подписки"],["reactions","Реакции"],
  ["content","Контент"],["referrals","Переходы"],["subscribers","Подписчиков всего"]
];
document.getElementById("totals").innerHTML = TOTALS.map(([k,l])=>
  `<div class="tcard"><div class="l">${l}</div><div class="v">${fmt(DASH.totals[k]||0)}</div></div>`
).join("");

const nets = Object.entries(DASH.networks);
const grid = document.getElementById("grid");

if(!nets.length){
  grid.innerHTML = `<div class="empty">Пока нет данных.<br>Запустите <code>python3 seed_demo.py</code> для демо или <code>python3 collector.py</code> с реальными токенами, затем <code>python3 build_dashboard.py</code>.</div>`;
}

const barColor = (p)=> p>=DASH.time_progress ? "var(--good)" : (p>=DASH.time_progress*0.7 ? "var(--warn)":"var(--bad)");

nets.forEach(([net,d],idx)=>{
  const card = document.createElement("div");
  card.className="net";
  const subsLine = d.latest_subscribers!=null ? `Подписчиков: <b>${fmt(d.latest_subscribers)}</b>` : "";
  let mh = "";
  DASH.metrics.forEach(({key,label})=>{
    const fact = d.fact[key]; const plan = d.plan[key]; const prog = d.progress[key];
    let bar = "";
    if(plan){
      const w = Math.min(100, prog||0);
      bar = `<div class="bar"><i style="width:${w}%;background:${barColor(prog||0)}"></i></div>
             <div class="pf"><span>${prog!=null?prog+"%":"—"}</span><span>план ${fmtMetric(key,plan)}</span></div>`;
    }
    mh += `<div class="m"><div class="ml">${label}</div>
           <div class="mv">${fmtMetric(key,fact)}</div>${bar}</div>`;
  });
  card.innerHTML = `<h3><span class="dot" style="background:${d.color}"></span>${d.label}</h3>
    <div class="subs">${subsLine}</div>
    <div class="metrics">${mh}</div>
    <canvas id="c_${net}" height="120"></canvas>
    <div class="legend-note">Динамика просмотров за день</div>`;
  grid.appendChild(card);

  const s = d.series;
  new Chart(document.getElementById("c_"+net), {
    type:"line",
    data:{ labels:s.dates.map(x=>x.slice(5)),
      datasets:[{ data:s.views, borderColor:d.color, backgroundColor:d.color+"22",
        fill:true, tension:.35, pointRadius:0, borderWidth:2 }]},
    options:{ plugins:{legend:{display:false}},
      scales:{ x:{grid:{display:false},ticks:{color:"#9aa0ad",maxTicksLimit:6,font:{size:10}}},
               y:{grid:{color:"#2a2f3d"},ticks:{color:"#9aa0ad",font:{size:10},
                  callback:v=>v>=1000?(v/1000)+"k":v}}},
      maintainAspectRatio:false }
  });
});
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
