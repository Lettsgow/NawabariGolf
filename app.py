from flask import Flask, render_template, request, jsonify
import requests, json, os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ⚙️ 구장 정보 로딩
golf_club_path = os.path.join("json", "golf_clubs.json")
with open(golf_club_path, "r", encoding="utf-8") as f:
    GOLF_CLUBS = json.load(f)

#############################
# 티스캐너 크롤러 함수      #
#############################

def crawl_teescan_teetimes(date_str: str, favorite):
    url_tpl = (
        "https://foapi.teescanner.com/v1/booking/getTeeTimeListbyGolfclub"
        "?golfclub_seq={seq}&roundDay=" + date_str + "&orderType="
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    res = []
    for club in GOLF_CLUBS:
        if favorite and club["name"] not in favorite:
            continue
        seq = club.get("seq")
        if not seq:
            continue
        try:
            resp = requests.get(url_tpl.format(seq=seq), headers=headers, timeout=6)
            items = resp.json().get("data", {}).get("teeTimeList", [])
            print(f"[Teescan] {club['name']} {date_str} 티타임 {len(items)}개 수신")
            for it in items:
                price = int(it["price"])
                h = int(it["teetime_time"].split(":")[0])
                res.append({
                    "golf": club["name"],
                    "date": date_str,
                    "hour": f"{h:02d}시대",
                    "hour_num": h,
                    "price": price,
                    "benefit": "",
                    "url": "https://www.teescanner.com/",
                    "source": "teescan"
                })
        except Exception as e:
            print(f"[Teescan] {club['name']} 오류: {e}")
    return res

#############################
# 골팡 크롤러 함수          #
#############################

def crawl_golfpang_teetimes(date_str: str, favorite):
    url = "https://www.golfpang.com/web/round/booking_tblList.do"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "*/*",
    }
    res = []
    for club in GOLF_CLUBS:
        if favorite and club["name"] not in favorite:
            continue
        code = club.get("Golpang_code")
        if not code:
            continue
        payload = {
            "pageNum": "1",
            "bkOrder": "clubname_desc",
            "rd_date": date_str,
            "ampm": "",  # 전체 시간대
            "sector": "5",
            "idx": "",
            "cust_nick": "",
            "clubname": code,
            "sector2": "",
            "sector3": "",
            "cdOrder": "",
        }
        try:
            resp = requests.post(url, headers=headers, data=payload, verify=False, timeout=8)
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("tr[id^=tr_]")
            print(f"[Golfpang] {club['name']} {date_str} 티타임 {len(rows)}개 수신")
            for row in rows:
                cols = row.select("td")
                if len(cols) < 6:
                    continue
                hour_num = int(cols[2].text.strip().split(":")[0])
                price_tag = row.select_one(".price")
                if not price_tag:
                    continue
                price = int(price_tag.text.replace(",", ""))
                res.append({
                    "golf": club["name"],  # 이름은 golf_clubs.json 기준
                    "date": date_str,
                    "hour": f"{hour_num:02d}시대",
                    "hour_num": hour_num,
                    "price": price,
                    "benefit": "",
                    "url": "https://www.golfpang.com/",
                    "source": "golfpang"
                })
        except Exception as e:
            print(f"[Golfpang] {club['name']} 오류: {e}")
    return res

########################################
# Flask Endpoints                      #
########################################

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
    end = datetime.strptime(data["end_date"], "%Y-%m-%d")
    hour_range = data.get("hour_range")
    favorite = data.get("favorite_clubs", [])

    consolidated = []
    for d in (start + timedelta(days=i) for i in range((end-start).days+1)):
        date_str = d.strftime("%Y-%m-%d")
        print(f"\n===== {date_str} 크롤링 시작 =====")
        consolidated.extend(crawl_teescan_teetimes(date_str, favorite))
        consolidated.extend(crawl_golfpang_teetimes(date_str, favorite))

    by_key = {}
    for it in consolidated:
        if hour_range and it["hour_num"] not in hour_range:
            continue
        k = (it["golf"], it["date"], it["hour"])
        if k not in by_key or (it["price"] < by_key[k]["price"]) or (it["price"] == by_key[k]["price"] and it["source"] == "teescan"):
            by_key[k] = it
            print(f"🏌️‍♂️ 삽입: {it['golf']} {it['date']} {it['hour']} {it['price']}만원 from {it['source']}")

    final = [{
        "golf": v["golf"],
        "date": datetime.strptime(v["date"], "%Y-%m-%d").strftime("%m/%d"),
        "hour": v["hour"],
        "price": v["price"],
        "source": v["source"],
        "url": v["url"]
    } for v in by_key.values()]
    print(f"\n🎯 최종 티타임 {len(final)}건 반환")
    return jsonify(final)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
