from datetime import datetime, timedelta
from pathlib import Path
import json, os, sys, time, traceback

from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS

# ────────────────────────────── 설정 ──────────────────────────────
DATA_DIR   = Path("data"); DATA_DIR.mkdir(exist_ok=True)
MAX_DAYS   = 10            # 오늘부터 10일치
INTERVAL   = 660          # 11분(초)
FAVORITES  = []           # 추후 환경변수 등으로 주입 가능

# ────────────────────────────── 함수 ──────────────────────────────
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{level}] {ts}  {msg}", flush=True)

def crawl_date(date_str: str):
    try:
        items = crawl_teescan(date_str, FAVORITES) + crawl_golfpang(date_str, FAVORITES)
        (DATA_DIR / f"{date_str}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        log(f"{date_str}.json 저장 완료  ({len(items)}건)")
    except Exception as e:
        log(f"{date_str} 수집 실패 → {e}", level="ERROR")
        traceback.print_exc()

def loop():
    log("크롤러 루프 시작!")
    try:
        while True:
            start_ts = time.time()

            today = datetime.now().date()
            for i in range(MAX_DAYS):
                crawl_date((today + timedelta(days=i)).strftime("%Y-%m-%d"))

            # ── 다음 루프까지 남은 시간 계산 (드리프트 방지) ──
            elapsed = time.time() - start_ts
            sleep_sec = max(0, INTERVAL - elapsed)
            log(f"🕑 {sleep_sec:0.1f}초 뒤 다음 라운드")
            time.sleep(sleep_sec)
    except KeyboardInterrupt:
        log("KeyboardInterrupt → 크롤러 종료")
    except Exception as e:
        log(f"치명적 오류: {e}", level="ERROR")
        traceback.print_exc()

# ────────────────────────────── CLI 진입점 ──────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) == 2:
        crawl_date(sys.argv[1])          # 예: python crawler.py 2025-07-15
    else:
        loop()
