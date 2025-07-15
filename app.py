# app.py – Flask API (티타임 + 날씨 포함)
"""
변경점
1. 캐시·라이브 데이터 모두 weather 필드를 포함.
2. /get_ttime_grouped 응답에도 weather 전달 → 프론트에서 아이콘/텍스트 표시 가능.
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import os, json, threading

from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS
from crawler import loop as crawler_loop  # 백그라운드 크롤러

app = Flask(__name__)
DATA_DIR = "data"

# ────────────────────────────── 헬퍼 ──────────────────────────────

def crawl_from_cache_or_live(date_str: str, favorite):
    """캐시가 있으면 읽고, 없으면 즉시 크롤링"""
    cache_file = os.path.join(DATA_DIR, f"{date_str}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 선호 구장 필터
            return [it for it in data if not favorite or it["golf"] in favorite]
        except Exception as e:
            print("❌ 캐시 읽기 실패:", e)
    # 실시간 Fallback
    print("🌐 실시간 크롤링:", date_str)
    return crawl_teescan(date_str, favorite) + crawl_golfpang(date_str, favorite)

# ────────────────────────────── 라우터 ──────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_all_golfclubs")
def get_all():
    return jsonify(sorted(c["name"] for c in GOLF_CLUBS))

@app.route("/get_ttime_grouped", methods=["POST"])
def get_grouped():
    data = request.get_json()
    start = datetime.strptime(data["start_date"], "%Y-%m-%d")
    end   = datetime.strptime(data["end_date"],   "%Y-%m-%d")
    hour_range = data.get("hour_range")
    favorite   = data.get("favorite_clubs", [])

    # 날짜 범위별 데이터 모으기
    consolidated = []
    for d in (start + timedelta(days=i) for i in range((end - start).days + 1)):
        consolidated += crawl_from_cache_or_live(d.strftime("%Y-%m-%d"), favorite)

    # ── teescan 우선, 최저가 선별 ──
    by_key = {}
    for it in consolidated:
        if hour_range and it["hour_num"] not in hour_range:
            continue
        k = (it["golf"], it["date"], it["hour"])
        if k not in by_key or (it["price"] < by_key[k]["price"]) or \
           (it["price"] == by_key[k]["price"] and it["source"] == "teescan"):
            by_key[k] = it

    # 응답 포맷 (weather 포함)
    final = [{
        "golf"   : v["golf"],
        "date"   : datetime.strptime(v["date"], "%Y-%m-%d").strftime("%m/%d"),
        "hour"   : v["hour"],
        "hour_num": v["hour_num"],
        "price"  : v["price"],
        "source" : v["source"],
        "url"    : v["url"],
        "weather": v.get("weather")  # dict 또는 None
    } for v in by_key.values()]
    return jsonify(final)

# ────────────────────────────── 실행 ──────────────────────────────

if __name__ == "__main__":
    threading.Thread(target=crawler_loop, daemon=True).start()
    print("🟢 Flask 서버 + 크롤러 실행 중…")
    app.run(host="0.0.0.0", port=10000)
