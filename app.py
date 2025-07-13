from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import os, json
from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS

app = Flask(__name__)
DATA_DIR = "data"

def crawl_from_cache_or_live(date_str, favorite):
    cache_file = os.path.join(DATA_DIR, f"{date_str}.json")
    if os.path.exists(cache_file):
        print(f"📁 캐시 사용: {cache_file}")
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [item for item in data if not favorite or item["golf"] in favorite]
        except Exception as e:
            print(f"❌ 캐시 읽기 실패: {e}")
    print(f"🌐 실시간 크롤링: {date_str}")
    return crawl_teescan(date_str, favorite) + crawl_golfpang(date_str, favorite)

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

    consolidated = []
    for d in (start + timedelta(days=i) for i in range((end - start).days + 1)):
        date_str = d.strftime("%Y-%m-%d")
        consolidated += crawl_from_cache_or_live(date_str, favorite)

    by_key = {}
    for it in consolidated:
        if hour_range and it["hour_num"] not in hour_range:
            continue
        k = (it["golf"], it["date"], it["hour"])
        if k not in by_key or (it["price"] < by_key[k]["price"]) or \
           (it["price"] == by_key[k]["price"] and it["source"] == "teescan"):
            by_key[k] = it

    final = [{
        "golf": v["golf"],
        "date": datetime.strptime(v["date"], "%Y-%m-%d").strftime("%m/%d"),
        "hour": v["hour"],
        "price": v["price"],
        "source": v["source"],
        "url": v["url"]
    } for v in by_key.values()]
    return jsonify(final)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
