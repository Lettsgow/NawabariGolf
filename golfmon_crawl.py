import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_golfmon_prices(date):
    url = "https://www.golfmon.net/booking/post_booking_plaza_board.php"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0"
    }
    data = {
        "yyyymmdd": date.replace("-", ""),
        "area": "GYEONGGI",
        "search_type": "date"
    }

    try:
        resp = requests.post(url, headers=headers, data=data, timeout=5)
        return resp.json().get("data", [])
    except Exception as e:
        print(f"[골프몬] {date} 요청 실패: {e}")
        return []
