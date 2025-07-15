# weather.py – 기상청 단기예보(fetch) 모듈 (Render SSL 우회 포함 + 호출 딜레이)

"""
Usage:
    from weather import fetch_weather
    data = fetch_weather(lat=37.2, lng=127.3, target_date="2025-07-15")

Return (dict):
    {
       6:  {"desc": "맑음", "temp": 24.3, "rain": 0.0},
       7:  {"desc": "비",   "temp": 23.1, "rain": 3.2},
       ...
    }
"""

import os, math, requests, urllib3, time
from datetime import datetime
from typing import Dict, Any

# ───────────────────────── API 설정 ─────────────────────────
SERVICE_KEY = os.getenv("0pufYd46gOsX61f/gjCIhoD1jrtJcgclBVmFnsryJ5AxXV9g1+Td+26feW3O46x9tl0iIY7DJS12GFuHlraF4w==", "")  # ✅ 환경변수에서 읽기
VILAGE_URL  = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

# Render SSL 오류 우회
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────────────────── 좌표 변환(GPS→격자) ───────────────────────

def latlon_to_xy(lat: float, lon: float):
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0       # 격자 간격(km)
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi: theta -= 2.0 * math.pi
    if theta < -math.pi: theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + XO + 0.5)
    y = int(ro - ra * math.cos(theta) + YO + 0.5)
    return x, y

# ─────────────────────── Helper ───────────────────────

def nearest_base_time(now: datetime) -> str:
    base_times = [2,5,8,11,14,17,20,23]
    hour = now.hour
    for bt in reversed(base_times):
        if hour >= bt:
            return f"{bt:02d}00"
    return "2300"  # 자정 직후

# ─────────────────────── Main fetch ───────────────────────

def fetch_weather(lat: float, lng: float, target_date: str | None = None) -> Dict[int, Dict[str, Any]]:
    """Return hour→{desc, temp, rain} dict. target_date="YYYY-MM-DD"""
    if not SERVICE_KEY:
        print("[weather] ⚠️  KMA_API_KEY not set")
        return {}

    now = datetime.now()
    base_date = target_date or now.strftime("%Y-%m-%d")
    base_date_str = base_date.replace("-", "")
    base_time = nearest_base_time(now)

    nx, ny = latlon_to_xy(lat, lng)

    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": 1000,
        "dataType": "JSON",
        "pageNo": 1,
        "base_date": base_date_str,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    try:
        # ✅ 요청 전 sleep 추가 (1.2초)
        time.sleep(1.2)

        resp = requests.get(VILAGE_URL, params=params, timeout=6, verify=False)
        resp.raise_for_status()
        items = resp.json()["response"]["body"]["items"]["item"]
    except Exception as e:
        print(f"[weather] ❌ API error: {e}")
        return {}

    fcst = {}
    for it in items:
        hour = int(it["fcstTime"][:2])
        cat  = it["category"]
        val  = it["fcstValue"]
        if isinstance(val, list):
            val = val[0]
        if hour not in fcst:
            fcst[hour] = {}
        fcst[hour][cat] = val

    result = {}
    for h, v in fcst.items():
        sky = v.get("SKY", "")  # 1~4
        pty = v.get("PTY", "0")  # 0:없음 1:비 2:비/눈 3:눈 4:소나기
        desc = "맑음"
        if pty in {"1","2","4"}: desc = "비"
        elif pty == "3": desc = "눈"
        elif sky == "4": desc = "흐림"
        elif sky == "3": desc = "구름"

        # temp
        try:
            tmp = float(v.get("TMP", 0))
        except ValueError:
            tmp = 0.0

        # rain mm (PCP) 또는 강수확률(POP)
        raw_rain = str(v.get("PCP", "0"))
        rain = 0.0
        if raw_rain not in {"-", "강수없음"}:
            rain = float(raw_rain.replace("mm", "").replace("M", "0").strip())

        result[h] = {"desc": desc, "temp": tmp, "rain": rain}

    return result

# ─────────────────────── Quick Test ───────────────────────
if __name__ == "__main__":
    print(fetch_weather(37.199742, 127.340926))
