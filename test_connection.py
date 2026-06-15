#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка подключений. Запускайте на своём Mac:

    python3 test_connection.py

Для каждой включённой соцсети показывает ✅/❌ и что удалось получить.
Токены НЕ выводятся. Ничего не пишет в историю — только проверяет.
"""
import datetime as dt
import collector as C  # переиспользуем коллекторы и загрузку конфигов

def main():
    cfg = C.load_json(C.os.path.join(C.BASE, "config.json"),
                      C.os.path.join(C.BASE, "config.example.json"))
    sec = C.load_json(C.os.path.join(C.BASE, "secrets.json"),
                      C.os.path.join(C.BASE, "secrets.example.json"))
    if not cfg:
        print("Нет config.json"); return

    print(f"Проверка подключений — {dt.datetime.now():%Y-%m-%d %H:%M}\n")
    ok = 0
    for name, ncfg in cfg.get("networks", {}).items():
        if not ncfg.get("enabled", True):
            print(f"⏭️  {name:10} выключен (enabled:false)")
            continue
        fn = C.COLLECTORS.get(name)
        if not fn:
            continue
        try:
            vals = fn(ncfg, sec)
            vals = {k: v for k, v in vals.items() if v is not None}
            if vals:
                pretty = ", ".join(f"{k}={v}" for k, v in vals.items())
                print(f"✅  {name:10} OK — {pretty}")
                ok += 1
            else:
                print(f"⚠️   {name:10} ответ пустой — проверьте права токена/ID")
        except Exception as e:
            print(f"❌  {name:10} {e}")

    print(f"\nИтог: подключено {ok} соцсетей.")
    if ok:
        print("Дальше:  python3 collector.py  &&  python3 build_dashboard.py")
    else:
        print("Заполните secrets.json и config.json. Подсказки — в README.md и внутри файлов.")


if __name__ == "__main__":
    main()
