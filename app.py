from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import threading, time, pickle, os
import importlib.metadata
import flask

from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS

# ✅ Flask version: Render 환경에서 deprecated 대응
try:
    version = importlib.metadata.version("flask")
except Exception:
    version = flask.__version__
print(f"✅ Flask version: {version}")

app = Flask(__name__)
CORS(app)

MEMORY_CACHE = {}
CACHE_LOCK = threading.Lock()
CACHE_BACKUP_FILE = "memory_cache.pkl"

REFRESH_INTERVAL = 900  # 30분
MAX_DAYS = 7  # 오늘부터 11일치

def save_cache():
    with CACHE_LOCK:
        with open(CACHE_BACKUP_FILE, "wb") as f:
            pickle.dump(MEMORY_CACHE, f)

def load_cache():
    global MEMORY_CACHE
    if os.path.exists(CACHE_BACKUP_FILE):
        with open(CACHE_BACKUP_FILE, "rb") as f:
            MEMORY_CACHE = pickle.load(f)
        print(f"📥 이전 캐시 로드 완료: {sum(len(v) for v in MEMORY_CACHE.values())}건")
    else:
        print("⚠️ 캐시 백업 파일 없음")

def full_refresh_cache():
    today = datetime.now().date()
    updated_count = 0
    with CACHE_LOCK:
        for i in range(MAX_DAYS):
            date_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            try:
                items = crawl_teescan(date_str, favorite=[]) + crawl_golfpang(date_str, favorite=[])
                if items is not None:
                    MEMORY_CACHE[date_str] = items
                    updated_count += len(items)
                    print(f"✅ {date_str} 캐시 갱신 완료 ({len(items)}건)")
                else:
                    print(f"⚠️ {date_str} 크롤링 결과 없음 (None), 기존 캐시 유지")
            except Exception as e:
                print(f"❌ {date_str} 크롤링 실패, 기존 캐시 유지: {e}")
        save_cache()
    print(f"🧠 캐시 새로고침 완료: 총 {updated_count}건")

def refresher_loop():
    print("🔁 캐시 리프레시 루프 시작")
    while True:
        try:
            full_refresh_cache()
        except Exception as e:
            print("❌ 캐시 리프레시 실패:", e)
        time.sleep(REFRESH_INTERVAL)

has_started = False

@app.before_request
def trigger_background_once():
    global has_started
    if not has_started:
        has_started = True
        load_cache()
        threading.Thread(target=refresher_loop, daemon=True).start()

def get_from_cache(date_str, favorite):
    with CACHE_LOCK:
        base = MEMORY_CACHE.get(date_str, [])
        return [item for item in base if not favorite or item["golf"] in favorite]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_all_golfclubs")
def get_all_golfclubs():
    names = sorted(c["name"] for c in GOLF_CLUBS)
    print(f"📋 get_all_golfclubs 응답: {len(names)}개 골프장")
    return jsonify(names)

@app.route("/get_ttime_grouped", methods=["POST"])
def get_grouped_teetime():
    data = request.get_json()
    print(f"📥 티타임 요청 파라미터: {data}")

    start = datetime.strptime(data["start_date"], "%Y-%m-%d")
    end   = datetime.strptime(data["end_date"],   "%Y-%m-%d")
    hour_range = data.get("hour_range")
    favorite   = data.get("favorite_clubs", [])

    return jsonify(get_consolidated_teetime(start, end, hour_range, favorite))

@app.route("/get_ttime_grouped", methods=["GET"])
def get_grouped_teetime_gpt():
    start_str = request.args.get("start_date")
    end_str = request.args.get("end_date")
    print("🧠 GPT 요청 도착:", start_str, "~", end_str)

    if not start_str or not end_str:
        return jsonify({"error": "Missing start_date or end_date"}), 400

    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
    except Exception as e:
        return jsonify({"error": f"Invalid date format: {e}"}), 400

    return jsonify(get_consolidated_teetime(start, end, hour_range=None, favorite=[]))

def get_consolidated_teetime(start, end, hour_range=None, favorite=[]):
    consolidated = []
    for d in (start + timedelta(days=i) for i in range((end - start).days + 1)):
        date_str = d.strftime("%Y-%m-%d")
        consolidated += get_from_cache(date_str, favorite)

    by_key = {}
    for it in consolidated:
        if hour_range and it["hour_num"] not in hour_range:
            continue
        k = (it["golf"], it["date"], it["hour"])
        if k not in by_key or (it["price"] < by_key[k]["price"]) or \
           (it["price"] == by_key[k]["price"] and it["source"] == "teescan"):
            by_key[k] = it

    result = [ {
        "golf": v["golf"],
        "date": datetime.strptime(v["date"], "%Y-%m-%d").strftime("%m/%d"),
        "hour": v["hour"],
        "price": v["price"],
        "source": v["source"],
        "url": v["url"]
    } for v in by_key.values() ]

    print(f"📤 병합 결과: {len(result)}건")
    return result

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

@app.route("/admin/refresh", methods=["POST"])
def admin_refresh():
    threading.Thread(target=full_refresh_cache).start()
    return jsonify({"status": "refresh started"})
