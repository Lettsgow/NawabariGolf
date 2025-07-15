# crawler_utils.py – 티타임 + 단기예보(weather.py) 통합 수집 헬퍼
"""
▶ 기능 변경 요약
1. Teescan / Golfpang 크롤링 로직은 그대로 유지.
2. 각 club 의 위경도를 사용해 weather.fetch_weather() 호출 (단기예보 기반).
3. 티타임 항목마다 해당 시간(hour_num) 의 날씨 dict 삽입.
   └ {"desc": "맑음", "temp": 26.8, "rain": 0.0}
4. weather 모듈 오류 시 weather=None 으로 graceful degrade.
"""

import json, os, requests, urllib3
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, Any, List

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ────────────────────────────── 데이터 로딩 ──────────────────────────────
JSON_DIR = "json"
golf_club_path = os.path.join(JSON_DIR, "golf_clubs.json")
with open(golf_club_path, "r", encoding="utf-8") as f:
    GOLF_CLUBS = json.load(f)

# weather.py 모듈 (단기예보)
try:
    from weather import fetch_weather  # fetch_weather(golf, lat, lng, base_date) -> {hour: {...}}
except ImportError:
    def fetch_weather(*_, **__):
        return {}

# ────────────────────────────── 공통 ──────────────────────────────
HEADERS_DEFAULT = {"User-Agent": "Mozilla/5.0"}

# 클럽별 날씨 캐시 (하루 기준) {date: {club_name: {hour: weather_dict}}}
_WEATHER_CACHE: Dict[str, Dict[str, Dict[int, Dict[str, Any]]]] = {}


def _get_weather_for(club: dict, date_str: str):
    """club(dict) 과 날짜에 대한 시간대별 날씨 dict 반환 (캐시 사용)"""
    if date_str not in _WEATHER_CACHE:
        _WEATHER_CACHE[date_str] = {}
    if club["name"] not in _WEATHER_CACHE[date_str]:
        lat, lng = club.get("lat"), club.get("lng")
        if lat is None or lng is None:
            _WEATHER_CACHE[date_str][club["name"]] = {}
        else:
            _WEATHER_CACHE[date_str][club["name"]] = fetch_weather(club["name"], lat, lng, base_date=date_str)
    return _WEATHER_CACHE[date_str][club["name"]]

# ────────────────────────────── Teescan ──────────────────────────────

def crawl_teescan(date_str: str, favorite: List[str]):
    url_tpl = (
        "https://foapi.teescanner.com/v1/booking/getTeeTimeListbyGolfclub"
        "?golfclub_seq={seq}&roundDay=" + date_str + "&orderType="
    )
    res = []
    for club in GOLF_CLUBS:
        if favorite and club["name"] not in favorite:
            continue
        seq = club.get("seq")
        if not seq:
            continue
        try:
            r = requests.get(url_tpl.format(seq=seq), headers=HEADERS_DEFAULT, timeout=6)
            items = r.json().get("data", {}).get("teeTimeList", [])
            print(f"[Teescan] {club['name']} {date_str} ▶ {len(items)}")
            weather_map = _get_weather_for(club, date_str)
            for it in items:
                price = int(it["price"])
                h = int(it["teetime_time"].split(":"))[0]
                res.append({
                    "golf": club["name"],
                    "date": date_str,
                    "hour": f"{h:02d}시대",
                    "hour_num": h,
                    "price": price,
                    "benefit": "",
                    "url": "https://www.teescanner.com/",
                    "source": "teescan",
                    "weather": weather_map.get(h)
                })
        except Exception as e:
            print(f"[Teescan] {club['name']} 오류: {e}")
    return res

# ────────────────────────────── Golfpang ──────────────────────────────

def crawl_golfpang(date_str: str, favorite: List[str]):
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
            "ampm": "",
            "sector": "5",
            "clubname": code,
        }
        try:
            r = requests.post(url, headers=headers, data=payload, verify=False, timeout=8)
            soup = BeautifulSoup(r.text, "html.parser")
            rows = soup.select("tr[id^=tr_]")
            print(f"[Golfpang] {club['name']} {date_str} ▶ {len(rows)}")
            weather_map = _get_weather_for(club, date_str)
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
                    "golf": club["name"],
                    "date": date_str,
                    "hour": f"{hour_num:02d}시대",
                    "hour_num": hour_num,
                    "price": price,
                    "benefit": "",
                    "url": "https://www.golfpang.com/",
                    "source": "golfpang",
                    "weather": weather_map.get(hour_num)
                })
        except Exception as e:
            print(f"[Golfpang] {club['name']} 오류: {e}")
    return res
