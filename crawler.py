from datetime import datetime, timedelta
import json, time, sys, os
from pathlib import Path
from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS

DATA_DIR  = Path("data"); DATA_DIR.mkdir(exist_ok=True)
MAX_DAYS  = 7
INTERVAL  = 600  # 10분
FAVORITES = []

def crawl_date(date_str):
    items = crawl_teescan(date_str, FAVORITES) + crawl_golfpang(date_str, FAVORITES)
    (DATA_DIR / f"{date_str}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 {date_str}.json 저장 ({len(items)}건)")

def loop():
    while True:
        today = datetime.now().date()
        for i in range(MAX_DAYS):
            crawl_date((today + timedelta(days=i)).strftime("%Y-%m-%d"))
        print("🕑 10분 대기"); time.sleep(INTERVAL)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        crawl_date(sys.argv[1])   # python crawler.py 2025-07-12
    else:
        loop()
