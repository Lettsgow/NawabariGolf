# crawler.py – 티타임 + 단기예보 날씨 캐시 통합
"""
💡 동작 개요
1. Teescan / Golfpang 크롤링으로 티타임을 수집
2. golf_clubs.json 의 위·경도 → 기상청 단기예보(getVilageFcst) 호출
3. 같은 날짜·구장별 시간대별 날씨를 dict 로 정리
4. 티타임 item 에 weather 필드 추가

weather 필드 예시
{
  "weather": {
     "desc": "비",   # 맑음 | 흐림 | 비 | 눈 | 구름 ...
     "temp": 25.3,    # °C
     "rain": 3.2      # mm (없으면 0)
  }
}

캐시에 weather 가 포함되면 프론트엔드에서 손쉽게 렌더링 가능
"""

from datetime import datetime, timedelta
from pathlib import Path
import json, os, sys, time, traceback, concurrent.futures

from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS
from weather import fetch_weather  # ▶️ 새로 만든 weather.py 의 메인 함수 (lat,lng 기반)

# ────────────────────────────── 설정 ──────────────────────────────
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
MAX_DAYS = 10          # 오늘부터 10일치
INTERVAL = 660         # 11분(초)
FAVORITES = []         # 추후 환경변수 등으로 주입 가능
THREADS = 8            # 날씨 병렬 요청용 스레드 수

# ────────────────────────────── 공통 ──────────────────────────────

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{level}] {ts}  {msg}", flush=True)

# ────────────────────────────── 날씨 보조 ──────────────────────────────

def build_weather_index(date_str: str):
    """구장별 시간대별 날씨 dict 반환 {golf_name: {hour:int → {...}}}"""
    idx = {}

    def task(club):
        lat, lng = club.get("lat"), club.get("lng")
        if lat is None or lng is None:
            return club["name"], {}
        return club["name"], fetch_weather(club["name"], lat, lng, base_date=date_str)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        futures = [ex.submit(task, c) for c in GOLF_CLUBS]
        for fut in concurrent.futures.as_completed(futures):
            name, data = fut.result()
            idx[name] = data or {}

    return idx

# ────────────────────────────── 주요 기능 ──────────────────────────────

def crawl_date(date_str: str):
    try:
        # 1️⃣ 티타임 수집
        items = crawl_teescan(date_str, FAVORITES) + crawl_golfpang(date_str, FAVORITES)

        # 2️⃣ 날씨 인덱스 구축
        weather_idx = build_weather_index(date_str)

        # 3️⃣ 티타임 each 에 weather 붙이기
        for it in items:
            # 시간대(정수) 추출
            h = it.get("hour_num")
            w = weather_idx.get(it["golf"], {}).get(h, {})
            it["weather"] = w  # 없으면 빈 dict

        # 4️⃣ 캐시 저장
        out_path = DATA_DIR / f"{date_str}.json"
        out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"{date_str}.json 저장 완료  ({len(items)}건, weather ✅)")

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
