from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import threading, time, os

from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS

app = Flask(__name__)
CORS(app)

MEMORY_CACHE = {}
CACHE_LOCK = threading.Lock()
REFRESH_INTERVAL = 1800  # 30분
MAX_DAYS = 9

def full_refresh_cache():
    today = datetime.now().date()
    updated_count = 0
    with CACHE_LOCK:
        for i in range(MAX_DAYS):
            date_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            try:
                teescan_items = crawl_teescan(date_str, favorite=[])
                golfpang_items = crawl_golfpang(date_str, favorite=[])
                items = teescan_items + golfpang_items
                if items:
                    MEMORY_CACHE[date_str] = items
                    updated_count += len(items)
                    print(f"✅ {date_str} 캐시 갱신 완료 ({len(items)}건)")
                else:
                    print(f"⚠️ {date_str} 크롤링 결과 없음")
            except Exception as e:
                print(f"❌ {date_str} 크롤링 실패: {e}")
        print(f"🧠 캐시 전체 갱신 완료: {updated_count}건")

def refresher_loop():
    print("🔁 캐시 리프레시 스레드 시작")
    while True:
        try:
            full_refresh_cache()
        except Exception as e:
            print("❌ 캐시 리프레시 스레드 오류:", e)
        time.sleep(REFRESH_INTERVAL)

# ✅ 캐시 작업을 백그라운드로 시작
def startup_background():
    def _start():
        print("🚀 캐시 수집 쓰레드 시작")
        full_refresh_cache()
        threading.Thread(target=refresher_loop, daemon=True).start()
    threading.Thread(target=_start, daemon=True).start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_all_golfclubs")
def get_all_golfclubs():
    names = sorted(c["name"] for c in GOLF_CLUBS)
    return jsonify(names)

@app.route("/get_ttime_grouped", methods=["POST"])
def get_grouped_teetime():
    try:
        data = request.get_json()
        start = datetime.strptime(data["start_date"], "%Y-%m-%d")
        end = datetime.strptime(data["end_date"], "%Y-%m-%d")
        hour_range = data.get("hour_range")
        favorite = data.get("favorite_clubs", [])
        return jsonify(get_consolidated_teetime(start, end, hour_range, favorite))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_ttime_grouped", methods=["GET"])
def get_grouped_teetime_gpt():
    start_str = request.args.get("start_date")
    end_str = request.args.get("end_date")
    if not start_str or not end_str:
        return jsonify({"error": "Missing start_date or end_date"}), 400
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
    except Exception as e:
        return jsonify({"error": f"Invalid date format: {e}"}), 400
    return jsonify(get_consolidated_teetime(start, end, None, []))

def get_from_cache(date_str, favorite):
    with CACHE_LOCK:
        base = MEMORY_CACHE.get(date_str, [])
        return [item for item in base if not favorite or item["golf"] in favorite]

def get_consolidated_teetime(start, end, hour_range=None, favorite=[]):
    consolidated = []
    for d in (start + timedelta(days=i) for i in range((end - start).days + 1)):
        consolidated += get_from_cache(d.strftime("%Y-%m-%d"), favorite)
    by_key = {}
    for it in consolidated:
        try:
            h = int(it["hour_num"])
            if hour_range and h not in hour_range:
                continue
        except:
            continue
        k = (it["golf"], it["date"], it["hour"])
        if k not in by_key or it["price"] < by_key[k]["price"]:
            by_key[k] = it
    return [dict(
        golf=v["golf"],
        date=datetime.strptime(v["date"], "%Y-%m-%d").strftime("%m/%d"),
        hour=v["hour"],
        price=v["price"],
        source=v["source"],
        url=v["url"]
    ) for v in by_key.values()]

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

@app.route("/admin/refresh", methods=["POST"])
def admin_refresh():
    threading.Thread(target=full_refresh_cache).start()
    return jsonify({"status": "refresh started"})

# ✅ Render에서 포트 감지 실패 방지를 위해 즉시 서버 실행
if __name__ == "__main__":
    startup_background()  # 캐시는 백그라운드로
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask 서버 실행 시작: 포트 {port}")
    app.run(host="0.0.0.0", port=port)
