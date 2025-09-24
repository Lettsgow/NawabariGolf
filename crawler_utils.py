import requests, json, os, time, re
from bs4 import BeautifulSoup
from typing import List, Dict
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────────────────────────────────────────────────────────────────────────
# 구장 정보 로딩
base_dir = os.path.dirname(__file__)
golf_club_path = os.path.join(base_dir, "static", "golf_clubs.json")
with open(golf_club_path, "r", encoding="utf-8") as f:
    GOLF_CLUBS = json.load(f)

# ─────────────────────────────────────────────────────────────────────────────
# 공통 유틸
GOLFPANG_BASE = "https://www.golfpang.com"
LIST_URL = f"{GOLFPANG_BASE}/web/round/booking_list.do"
SECTORS = [5, 4, 8]  # 경기/충청/강원

# 환경변수로 세부 튜닝
MAX_PAGES_PER_SECTOR = int(os.environ.get("GPANG_MAX_PAGES", 5))
CONNECT_TIMEOUT = int(os.environ.get("GPANG_CONNECT_TIMEOUT", 5))
READ_TIMEOUT = int(os.environ.get("GPANG_READ_TIMEOUT", 20))
SLEEP_BETWEEN = float(os.environ.get("GPANG_SLEEP", 0.6))

HEADERS_HTML = {
    "User-Agent": os.environ.get(
        "GPANG_UA",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko,en;q=0.9",
    "Referer": f"{GOLFPANG_BASE}/web/round/booking.do",
}

def _make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=6, connect=6, read=6, backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=40)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def _parse_price(txt: str) -> int:
    digits = re.sub(r"[^0-9]", "", txt or "")
    return int(digits) if digits else 10**12

def _parse_hour_num(hour_text: str) -> int:
    m = re.search(r"(\d{1,2})", hour_text or "")
    return int(m.group(1)) if m else -1

# ─────────────────────────────────────────────────────────────────────────────
# Teescan (기존 로직 유지, 사소한 안정화만)
def crawl_teescan(date_str: str, favorite: List[str]):
    url_tpl = (
        "https://foapi.teescanner.com/v1/booking/getTeeTimeListbyGolfclub"
        "?golfclub_seq={seq}&roundDay=" + date_str + "&orderType="
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    res: List[Dict] = []
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
                price = int(it.get("price", 10**12))
                h = int(str(it.get("teetime_time", "00")).split(":")[0])
                res.append({
                    "golf": name,
                    "date": date_str,
                    "hour": f"{h:02d}시대",
                    "hour_num": h,
                    "price": price,
                    "benefit": "",
                    "url": "https://www.teescanner.com/",
                    "source": "teescan",
                })
        except Exception as e:
            print(f"[Teescan] {name} 오류: {e}")
    return res

# ─────────────────────────────────────────────────────────────────────────────
# Golfpang — booking_list.do (HTML) 섹터 5,4,8만 순회
def crawl_golfpang(date_str: str, favorite: List[str]):
    """
    - 섹터 5,4,8만 순회하며 booking_list.do(HTML)를 페이지별로 파싱
    - 페이지에 아이템이 없으면 해당 섹터 종료
    - date_str 정확히 일치하는 항목만 반환
    - favorite가 주어지면 구장명 부분일치 필터
    """
    out: List[Dict] = []
    with _make_session() as s:
        for sector in SECTORS:
            for page in range(1, MAX_PAGES_PER_SECTOR + 1):
                params = {"sector": sector, "page": page}
                try:
                    print(f"[Golfpang] GET {LIST_URL}?sector={sector}&page={page}")
                    r = s.get(
                        LIST_URL,
                        params=params,
                        headers=HEADERS_HTML,
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),  # (connect, read)
                        verify=False,  # 인증서 경고 무시
                    )
                    if r.status_code != 200:
                        print(f"[Golfpang] sector {sector} page {page} HTTP {r.status_code}")
                        break

                    soup = BeautifulSoup(r.text, "html.parser")
                    candidates = soup.select("li, div.card, div.item, tr")
                    items_found = 0

                    for c in candidates:
                        text = c.get_text(" ", strip=True)
                        if not text:
                            continue

                        # 이름
                        name_el = c.select_one(".golf-name, .tit, .name, .club, .clubNm")
                        name = name_el.get_text(strip=True) if name_el else None
                        if not name:
                            m = re.search(r"([가-힣A-Za-z0-9\s]+?)(?:CC|컨트리클럽|GC|GCC|CC)\b", text)
                            name = m.group(0) if m else None

                        # 날짜/시간
                        date_el = c.select_one(".date, .day, .bk-date")
                        time_el = c.select_one(".time, .bk-time")
                        date_txt = date_el.get_text(strip=True) if date_el else None
                        time_txt = time_el.get_text(strip=True) if time_el else None
                        if not date_txt:
                            m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
                            date_txt = m.group(1) if m else None
                        if not time_txt:
                            m = re.search(r"(\d{1,2}:\d{2})", text)
                            time_txt = m.group(1) if m else None

                        # 가격
                        price_el = c.select_one(".price, .bk-price, .won, .fee")
                        price_txt = price_el.get_text(" ", strip=True) if price_el else None
                        if not price_txt:
                            m = re.search(r"([0-9,]{4,})\s*원?", text)
                            price_txt = m.group(1) if m else None

                        # 링크(있는 경우)
                        link_el = c.select_one("a[href]")
                        href = link_el.get("href") if link_el else None
                        url = href if (href and href.startswith("http")) else (f"{GOLFPANG_BASE}{href}" if href else "https://www.golfpang.com/")

                        if not (name and date_txt and time_txt and price_txt):
                            continue
                        if date_txt != date_str:
                            continue
                        if favorite and not any(f in name for f in favorite):
                            continue

                        price = _parse_price(price_txt)
                        hour_num = _parse_hour_num(time_txt)
                        out.append({
                            "golf": name,
                            "date": date_txt,
                            "hour": f"{hour_num:02d}시대" if hour_num >= 0 else time_txt,
                            "hour_num": hour_num,
                            "price": price,
                            "benefit": "",
                            "url": url,
                            "source": "golfpang",
                        })
                        items_found += 1

                    if items_found == 0:
                        break  # 이 페이지엔 더 없음 → 다음 섹터
                    time.sleep(SLEEP_BETWEEN)

                except requests.exceptions.ConnectTimeout as e:
                    print(f"[Golfpang] sector {sector} page {page} 연결타임아웃: {e}")
                    break
                except Exception as e:
                    print(f"[Golfpang] sector {sector} page {page} 오류: {e}")
                    break

    return out
