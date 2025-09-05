import requests, json, os
from datetime import datetime
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 구장 정보 로딩
base_dir = os.path.dirname(__file__)
golf_club_path = os.path.join(base_dir, "static", "golf_clubs.json")
with open(golf_club_path, "r", encoding="utf-8") as f:
    GOLF_CLUBS = json.load(f)

def crawl_teescan(date_str: str, favorite):
    url_tpl = (
        "https://foapi.teescanner.com/v1/booking/getTeeTimeListbyGolfclub"
        "?golfclub_seq={seq}&roundDay=" + date_str + "&orderType="
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    res = []
    visited = set()

    for club in GOLF_CLUBS:
        name = club.get("name")
        if not name or name in visited:
            continue
        visited.add(name)

        seq = club.get("seq")
        if not seq:
            continue

        try:
            r = requests.get(url_tpl.format(seq=seq), headers=headers, timeout=6)
            items = r.json().get("data", {}).get("teeTimeList", [])
            print(f"[Teescan] {name} {date_str} ▶ {len(items)}")
            for it in items:
                price = int(it["price"])
                h = int(it["teetime_time"].split(":")[0])
                res.append({
                    "golf": name,
                    "date": date_str,
                    "hour": f"{h:02d}시대",
                    "hour_num": h,
                    "price": price,
                    "benefit": "",
                    "url": "https://www.teescanner.com/",
                    "source": "teescan"
                })
        except Exception as e:
            print(f"[Teescan] {name} 오류: {e}")
    return res


def crawl_golfpang(date_str: str, favorite):
    url = "https://www.golfpang.com/web/round/booking_tblList.do"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "*/*",
    }
    res = []
    visited = set()

    for club in GOLF_CLUBS:
        name = club.get("name")
        if not name or name in visited:
            continue
        visited.add(name)

        code = club.get("Golpang_code")
        if not code:
            continue

        address = club.get("address", "")
        if address.startswith("경기도"):
            sector = "5"
        elif address.startswith("충청"):
            sector = "4"
        elif address.startswith("강원"):
            sector = "8"
        #elif address.startswith("전라"):
            sector = "16"
        else:
            print(f"[Golfpang] {name} 주소로 지역 판단 실패: {address}")
            continue

        page = 1
        while True:
            payload = {
                "pageNum": str(page),
                "bkOrder": "clubname_desc",
                "rd_date": date_str,
                "ampm": "",
                "sector": sector,
                "clubname": code,
            }

            try:
                r = requests.post(url, headers=headers, data=payload, verify=False, timeout=8)
                soup = BeautifulSoup(r.text, "html.parser")
                rows = soup.select("tr[id^=tr_]")
                if not rows:
                    break

                print(f"[Golfpang] {name} {date_str} sector {sector} page {page} ▶ {len(rows)}")

                for row in rows:
                    cols = row.select("td")
                    if len(cols) < 6:
                        continue
                    hour_num = int(cols[2].text.split(":")[0])
                    price_tag = row.select_one(".price")
                    if not price_tag:
                        continue
                    price = int(price_tag.text.replace(",", ""))
                    res.append({
                        "golf": name,
                        "date": date_str,
                        "hour": f"{hour_num:02d}시대",
                        "hour_num": hour_num,
                        "price": price,
                        "benefit": "",
                        "url": "https://www.golfpang.com/",
                        "source": "golfpang"
                    })

                page += 1
            except Exception as e:
                print(f"[Golfpang] {name} sector {sector} page {page} 오류: {e}")
                break

    return res
