from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

GOLF_CLUBS = [
    {"name": "태광", "seq": "51", "xgolf_code": "136", "golfpang_code": None},
    {"name": "세현", "seq": "114055", "xgolf_code": "1300", "golfpang_code": None},
    {"name": "윈체스트", "seq": "102", "xgolf_code": None, "golfpang_code": None},
    {"name": "이글몬트", "seq": "114312", "xgolf_code": "1562", "golfpang_code": None},
    {"name": "수원", "seq": "455", "xgolf_code": "137", "golfpang_code": None},
    {"name": "자유", "seq": "86", "xgolf_code": "318", "golfpang_code": None},
    {"name": "블루헤런", "seq": "207", "xgolf_code": "101", "golfpang_code": None},
    {"name": "H1", "seq": "261", "xgolf_code": "803", "golfpang_code": None},
    {"name": "신라", "seq": "167", "xgolf_code": "108", "golfpang_code": None},
    {"name": "골프존H", "seq": "386", "xgolf_code": None, "golfpang_code": None},
    {"name": "레이크사이드", "seq": "244", "xgolf_code": "990", "golfpang_code": None},
    {"name": "중부", "seq": "74", "xgolf_code": "126", "golfpang_code": None},
    {"name": "파인크리크", "seq": "39", "xgolf_code": "998", "golfpang_code": None}
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
                "benefit": item.get("benefit_tag_name", ""),
                "source": "(T)"
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
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for row in soup.select("table.new_list_tbl tbody tr"):
            tds = row.find_all("td")
            if len(tds) >= 4:
                time_str = tds[2].text.strip().split(":"[0])
                price_tag = tds[3].select_one("strong")
                if price_tag:
                    price_str = price_tag.text.replace(",", "").replace("원", "").strip()
                    if price_str.isdigit():
                        results.append({
                            "golf": club_name,
                            "date": date,
                            "hour": f"{int(time_str):02d}시대",
                            "price": int(price_str),
                            "benefit": tds[4].text.strip(),
                            "source": "(X)"
                        })
        return results
    except Exception as e:
        print(f"❌ XGOLF 오류 ({club_name}): {e}")
        return []

def get_golfpang_prices(club_code, club_name, date):
    try:
        url = "https://www.golfpang.com/web/round/booking_list.do"
        headers = {"User-Agent": "Mozilla/5.0"}
        data = {
            "round_date": date,
            "round_time": "",
            "area": "",
            "golf_course": ""
        }
        resp = requests.post(url, headers=headers, data=data, verify=False)
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for row in soup.select("table.tbl_booking_list tbody tr"):
            tds = row.find_all("td")
            if len(tds) >= 3:
                time = tds[2].text.strip().split(":"[0])
                price_tag = row.select_one("span.price")
                if price_tag:
                    price_str = price_tag.text.replace(",", "").replace("원", "").strip()
                    if price_str.isdigit():
                        results.append({
                            "golf": club_name,
                            "date": date,
                            "hour": f"{int(time):02d}시대",
                            "price": int(price_str),
                            "benefit": "",
                            "source": "(G)"
                        })
        return results
    except Exception as e:
        print(f"❌ 골팡 오류 ({club_name}): {e}")
        return []

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
            golfpang_prices = get_golfpang_prices(club.get("golfpang_code"), club['name'], date)

            all_prices = tee_prices + xgolf_prices + golfpang_prices

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
            "benefit": item.get("benefit", ""),
            "source": item.get("source", "")
        })

    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
