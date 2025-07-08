import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_teescanner_prices(club_seq, club_name, date):
    url = f"https://foapi.teescanner.com/v1/booking/getTeeTimeListbyGolfclub?golfclub_seq={club_seq}&roundDay={date}&orderType="
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json().get("data", {}).get("teeTimeList", [])
        results = []

        for item in data:
            try:
                price = int(item["price"])
                hour = f"{int(item['teetime_time'].split(':')[0]):02d}시대"
                benefit = item.get("benefit_tag_name", "")
                results.append({
                    "golf": club_name,
                    "date": date,
                    "hour": hour,
                    "price": price,
                    "benefit": benefit
                })
            except Exception as e:
                print(f"[티스캐너] 항목 파싱 오류 ({club_name}): {e}")
        return results

    except Exception as e:
        print(f"[티스캐너] {club_name} 요청 오류: {e}")
        return []
