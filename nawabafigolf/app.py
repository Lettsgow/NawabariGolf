from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os  # ✅ 빠졌던 import 추가

app = Flask(__name__)

GOLF_CLUBS = [
    {"name": "태광", "seq": "51", "xgolf_code": None},
    {"name": "세현", "seq": "114055", "xgolf_code": "1300"},
    {"name": "윈체스트", "seq": "102", "xgolf_code": None},
    {"name": "이글몬트", "seq": "114312", "xgolf_code": None},
    {"name": "수원", "seq": "176", "xgolf_code": None},
    {"name": "자유", "seq": "86", "xgolf_code": None},
    {"name": "블루헤런", "seq": "207", "xgolf_code": None},
    {"name": "H1", "seq": "261", "xgolf_code": None},
    {"name": "신라", "seq": "167", "xgolf_code": None},
    {"name": "골프존H", "seq": "386", "xgolf_code": None},
    {"name": "레싸", "seq": "244", "xgolf_code": None},
    {"name": "중부", "seq": "74", "xgolf_code": None},
    {"name": "파인크리", "seq": "39", "xgolf_code": None},
    {"name": "코리아", "seq": "58", "xgolf_code": None},
    {"name": "리베라", "seq": "235", "xgolf_code": None},
    {"name": "골드", "seq": "307", "xgolf_code": None}
]

def get_teescanner_prices(club_seq, club_name, date):
    url = f"https://foapi.teescanner.com/v1/booking/getTeeTimeListbyGolfclub?golfclub_seq={club_seq}&roundDay={date}&orderType="
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers)
        tee_list = resp.json().get("data", {}).get("teeTimeList", [])
        return [
            {
                "golf": club_name,
                "date": date,
                "hour": f"{int(item['teetime_time'].split(':')[0]):02d}시대",
                "price": int(item["price"]),
                "benefit": item.get("benefit_tag_name", "")
            }
            for item in tee_list
        ]
    except Exception as e:
        print(f"❌ 티스캐너 오류 ({club_name}): {e}")
        return []

def get_xgolf_prices(club_code, club_name, date):
    if not club_code:
        return []
    url = f"https://www.xgolf.com/booking/booking_normal_list.asp?club_code={club_code}&book_date={date.replace('-', '')}"
    try:
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for row in soup.select(".tblTime tbody tr"):
            time_tag = row.select_one("td.time")
            price_tag = row.select_one("td.price")
            if time_tag and price_tag:
                hour = time_tag.text.strip().split(":")[0]
                price_str = price_tag.text.replace(",", "").replace("원", "").strip()
                if price_str.isdigit():
                    results.append({
                        "golf": club_name,
                        "date": date,
                        "hour": f"{int(hour):02d}시대",
                        "price": int(price_str),
                        "benefit": ""
                    })
        return results
    except Exception as e:
        print(f"❌ XGOLF 오류 ({club_name}): {e}")
        return []
    
@app.route('/get_all_golfclubs')
def get_all_golfclubs():
    return jsonify(sorted([club["name"] for club in GOLF_CLUBS]))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_ttime_grouped', methods=['POST'])
def get_ttime_grouped():
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    hour_range = data.get('hour_range')

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception as e:
        return jsonify({"error": f"날짜 형식 오류: {str(e)}"}), 400

    merged = []

    for club in GOLF_CLUBS:
        for n in range((end - start).days + 1):
            date = (start + timedelta(days=n)).strftime("%Y-%m-%d")
            tee_prices = get_teescanner_prices(club['seq'], club['name'], date)
            xgolf_prices = get_xgolf_prices(club.get("xgolf_code"), club['name'], date)

            all_prices = tee_prices + xgolf_prices

            by_slot = {}
            for item in all_prices:
                if hour_range and isinstance(hour_range, list) and len(hour_range) > 0:
                    if int(item['hour'][:2]) not in hour_range:
                        continue
                key = (item['date'], item['hour'], item['golf'])
                if key not in by_slot or item['price'] < by_slot[key]['price']:
                    by_slot[key] = item

            merged.extend(by_slot.values())

    result = []
    for item in merged:
        try:
            date_obj = datetime.strptime(item['date'], "%Y-%m-%d")
            short_date = date_obj.strftime("%m/%d")
        except Exception as e:
            print(f"❌ 날짜 파싱 오류: {e}")
            continue
        result.append({
            "golf": item["golf"],
            "date": short_date,
            "hour": item["hour"],
            "price": item["price"],
            "benefit": item.get("benefit", "")
        })

    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render가 할당한 포트를 자동으로 사용
    app.run(host="0.0.0.0", port=port)