# weather.py – 기상청 단기예보(fetch) 모듈 (Render SSL 우회 + 날짜 형 변환 처리 + sleep 포함)

import os, math, requests, urllib3, time
from datetime import datetime
from typing import Dict, Any

# SSL 인증서 경고 무시 (Render 환경 대응)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 기상청 단기예보 API 설정
SERVICE_KEY = os.getenv("0pufYd46gOsX61f/gjCIhoD1jrtJcgclBVmFnsryJ5AxXV9g1+Td+26feW3O46x9tl0iIY7DJS12GFuHlraF4w==", "")
VILAGE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

# ───────────────────────────── 좌표 변환 ─────────────────────────────
def convert_grid(lat: float, lon: float):
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2, OLON, OLAT = 30.0, 60.0, 126.0, 38.0
    XO, YO = 43, 136
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

# ───────────────────────────── 기준 시간 계산 ─────────────────────────────
def get_base_time(now: datetime):
    base_times = [2, 5, 8, 11, 14, 17, 20, 23]
    for bt in reversed(base_times):
        if now.hour >= bt:
            return f"{bt:02d}00"
    return "2300"

# ───────────────────────────── 메인 함수 ─────────────────────────────
def fetch_weather(golf_name, lat, lng, base_date=None) -> Dict[int, Dict[str, Any]]:
    if not SERVICE_KEY:
        print("[weather] ⚠️  KMA_API_KEY not set")
        return {}

    # 날짜 안전 처리
    if isinstance(base_date, datetime):
        base_date_str = base_date.strftime("%Y%m%d")
    elif isinstance(base_date, str):
        base_date_str = base_date.replace("-", "")
    else:
        base_date_str = datetime.now().strftime("%Y%m%d")

    base_time = get_base_time(datetime.now())
    nx, ny = convert_grid(lat, lng)

    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": "1000",
        "dataType": "JSON",
        "base_date": base_date_str,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    try:
        time.sleep(1.2)  # 💡 API 호출 간 딜레이 추가
        resp = requests.get(VILAGE_URL, params=params, timeout=6, verify=False)
        resp.raise_for_status()
        items = resp.json()["response"]["body"]["items"]["item"]
    except Exception as e:
        print(f"[weather] ❌ {golf_name} 날씨 수집 실패:", e)
        return {}

    forecast = {}
    for it in items:
        fcst_time = it["fcstTime"]
        category = it["category"]
        value = it["fcstValue"]
        if fcst_time not in forecast:
            forecast[fcst_time] = {}
        forecast[fcst_time][category] = value

    result = {}
    for time_str, values in forecast.items():
        hour = int(time_str[:2])
        desc = "맑음"
        if values.get("PTY") in {"1", "4"}:
            desc = "비"
        elif values.get("PTY") == "3":
            desc = "눈"
        elif values.get("SKY") == "4":
            desc = "흐림"
        elif values.get("SKY") == "3":
            desc = "구름"

        def to_float(v):
            v = str(v).replace("강수없음", "0").replace("-", "0").replace("mm", "").strip()
            try:
                return float(v)
            except ValueError:
                return 0.0

        result[hour] = {
            "desc": desc,
            "temp": to_float(values.get("TMP", 0)),
            "rain": to_float(values.get("PCP", "0")),
        }

    return result

# ───────────────────────────── 테스트 ─────────────────────────────
if __name__ == "__main__":
    print(fetch_weather("세현", 37.199742, 127.340926))
