from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os  # ✅ 빠졌던 import 추가

app = Flask(__name__)

GOLF_CLUBS = [
    {"name": "태광", "seq": "51", "xgolf_code": None},#경기
    {"name": "세현", "seq": "114055", "xgolf_code": "1300"},#경기
    {"name": "윈체스트", "seq": "102", "xgolf_code": None},#경기
    {"name": "이글몬트", "seq": "114312", "xgolf_code": None},#경기
    {"name": "수원", "seq": "176", "xgolf_code": None},#경기
    {"name": "자유", "seq": "86", "xgolf_code": None},#경기
    {"name": "블루헤런", "seq": "207", "xgolf_code": None},#경기
    {"name": "H1", "seq": "261", "xgolf_code": None},#경기
    {"name": "신라", "seq": "167", "xgolf_code": None},#경기
    {"name": "골프존H", "seq": "386", "xgolf_code": None},#경기
    {"name": "레싸", "seq": "244", "xgolf_code": None},#경기
    {"name": "중부", "seq": "74", "xgolf_code": None},#경기
    {"name": "파인크리", "seq": "39", "xgolf_code": None},#경기
    {"name": "코리아", "seq": "58", "xgolf_code": None},#경기
    {"name": "리베라", "seq": "235", "xgolf_code": None},#경기
    {"name": "골드", "seq": "307", "xgolf_code": None},#경기
    {"name": "태광9", "seq": "52", "xgolf_code": None},#경기
    {"name": "아세코9", "seq": "617", "xgolf_code": None},#경기
    {"name": "코리아9", "seq": "474", "xgolf_code": None},#경기
    {"name": "화성상록", "seq": "8", "xgolf_code": None},#경기
    {"name": "은화삼", "seq": "99", "xgolf_code": None},#경기
    {"name": "해솔리아", "seq": "442", "xgolf_code": None},#경기
    {"name": "화성9", "seq": "360", "xgolf_code": None},#경기
    {"name": "양지파인", "seq": "141", "xgolf_code": None},#경기
    {"name": "한원", "seq": "19", "xgolf_code": None},#경기
    {"name": "플라자용인", "seq": "30", "xgolf_code": None},#경기
    {"name": "한림용인", "seq": "240", "xgolf_code": None},#경기
    {"name": "화성상록", "seq": "8", "xgolf_code": None},#경기
    {"name": "링크나인9", "seq": "233", "xgolf_code": None},#경기
    {"name": "포웰", "seq": "113869", "xgolf_code": None},#경기
    {"name": "발리오스", "seq": "224", "xgolf_code": None},#경기
    {"name": "더크로스비", "seq": "114051", "xgolf_code": None},#경기
    {"name": "써닝포인트", "seq": "441", "xgolf_code": None},#경기
    {"name": "금강", "seq": "292", "xgolf_code": None},#경기
    {"name": "남서울", "seq": "282", "xgolf_code": None},#경기
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
    favorite_clubs = data.get('favorite_clubs')  # ✅ 추가

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception as e:
        return jsonify({"error": f"날짜 형식 오류: {str(e)}"}), 400

    merged = []

    for club in GOLF_CLUBS:
        if favorite_clubs and club['name'] not in favorite_clubs:  # ✅ 필터링 조건 추가
            continue
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
