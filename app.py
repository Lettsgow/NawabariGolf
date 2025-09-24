from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import threading, time, os, subprocess

from crawler_utils import crawl_teescan, crawl_golfpang, GOLF_CLUBS

# ─────────────────────────────────────────────────────────────────────────────
# (옵션) IPv6 경로 문제 우회: FORCE_IPV4=1 환경변수를 주면 IPv4만 사용
# Render 무료티어에서 -6 경로가 막히거나 느릴 때 유용
try:
    if os.environ.get("FORCE_IPV4") == "1":
        import socket
        import urllib3.util.connection as urllib3_cn
        urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
        print("🔧 IPv4-only mode enabled (FORCE_IPV4=1)")
except Exception as e:
    print("⚠️ IPv4-only 설정 실패:", e)
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

MEMORY_CACHE = {}
CACHE_LOCK = threading.Lock()
MAX_DAYS = 18

# 고정 섹터: 5, 4, 8만 크롤링
GOLFPANG_SECTORS = [5, 4, 8]

# ─────────────────────────────────────────────────────────────────────────────
# Golfpang 회로 차단기(circuit breaker)
# - 연속 실패가 THRESH 이상이면 COOL_MIN 분 동안 Golfpang 호출을 잠시 스킵
GOLFPANG_CB = {
    "fails": 0,
    "open_until": None,   # datetime or None
    "THRESH": 3,          # 연속 3회 실패 시
    "COOL_MIN": 5         # 5분 쿨다운
}

def _golfpang_allowed_now():
    now = datetime.now()
    if GOLFPANG_CB["open_until"] and now < GOLFPANG_CB["open_until"]:
        return False
    return True

def _golfpang_on_success():
    GOLFPANG_CB["fails"] = 0
    GOLFPANG_CB["open_until"] = None

def _golfpang_on_failure():
    GOLFPANG_CB["fails"] += 1
    if GOLFPANG_CB["fails"] >= GOLFPANG_CB["THRESH"]:
        cool = timedelta(minutes=GOLFPANG_CB["COOL_MIN"])
        GOLFPANG_CB["open_until"] = datetime.now() + cool
        print(f"🧯 Golfpang 회로 열림: {GOLFPANG_CB['COOL_MIN']}분 동안 스킵 (연속실패={GOLFPANG_CB['fails']})")
# ─────────────────────────────────────────────────────────────────────────────


def full_refresh_cache():
    today = datetime.now().date()
    updated_count = 0

    for i in range(MAX_DAYS):
        date_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            teescan_items = []
            golfpang_items = []

            # Teescan은 그대로 시도
            try:
                teescan_items = crawl_teescan(date_str, favorite=[])
            except Exception as e_ts:
                print(f"❗️ {date_str} Teescan 실패: {e_ts}")

            # Golfpang은 회로차단기 상태에 따라 호출/스킵 (섹터 5,4,8만)
            if _golfpang_allowed_now():
                try:
                    golfpang_items = crawl_golfpang(date_str, favorite=[], sectors=GOLFPANG_SECTORS)
                    _golfpang_on_success()
                except Exception as e_gp:
                    print(f"❗️ {date_str} Golfpang 실패: {e_gp}")
                    _golfpang_on_failure()
            else:
                left = int((GOLFPANG_CB["open_until"] - datetime.now()).total_seconds())
                print(f"⏸️ {date_str} Golfpang 스킵(회로 열림, {left}s 남음)")
                golfpang_items = []  # 스킵

            items = teescan_items + golfpang_items

            if items:
                got_lock = CACHE_LOCK.acquire(timeout=5)
                if got_lock:
                    try:
                        MEMORY_CACHE[date_str] = items
                        updated_count += len(items)
                        print(f"✅ {date_str} 캐시 갱신 완료 ({len(items)}건)")
                    finally:
                        CACHE_LOCK.release()
                else:
                    print(f"⛔️ {date_str} 캐시 갱신 실패 - 락 획득 실패")
            else:
                print(f"⚠️ {date_str} 크롤링 결과 없음 (TS:{len(teescan_items)}, GP:{len(golfpang_items)})")

        except Exception as e:
            print(f"❌ {date_str} 크롤링 실패(전체 루프): {e}")

    got_lock = CACHE_LOCK.acquire(timeout=5)
    if got_lock:
        try:
            print("🧠 MEMORY_CACHE keys:", list(MEMORY_CACHE.keys()))
            for k, v in MEMORY_CACHE.items():
                print(f"📅 {k}: {len(v)}건 저장됨")
        finally:
            CACHE_LOCK.release()

    print(f"🧠 전체 캐시 갱신 완료: {updated_count}건")


def run_async_refresh_once():
    def _start():
        print("🚀 서버 부팅 후 1회 캐시 수집 시작")
        try:
            full_refresh_cache()
        except Exception as e:
            print("❌ 초기 캐시 수집 실패:", e)
    threading.Thread(target=_start, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get_all_golfclubs")
def get_all_golfclubs():
    names = sorted(c["name"] for c in GOLF_CLUBS)
    return jsonify(names)


@app.route("/get_ttime_grouped", methods=["POST"])
def get_grouped_teetime():
    try:
        data = request.get_json(force=True)
        print("📥 POST 요청 수신:", data)

        start = datetime.strptime(data["start_date"], "%Y-%m-%d")
        end = datetime.strptime(data["end_date"], "%Y-%m-%d")
        hour_range = data.get("hour_range")
        favorite = data.get("favorite_clubs", [])

        return jsonify(get_consolidated_teetime(start, end, hour_range, favorite))
    except Exception as e:
        print("❌ API 오류:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/get_ttime_grouped", methods=["GET"])
def get_grouped_teetime_gpt():
    start_str = request.args.get("start_date")
    end_str = request.args.get("end_date")
    if not start_str or not end_str:
        return jsonify({"error": "Missing start_date or end_date"}), 400
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
    except Exception as e:
        return jsonify({"error": f"Invalid date format: {e}"}), 400
    return jsonify(get_consolidated_teetime(start, end, None, []))


def get_from_cache(date_str, favorite):
    got_lock = CACHE_LOCK.acquire(timeout=3)
    if not got_lock:
        print(f"⛔️ {date_str} 캐시 잠금 획득 실패 - 다른 작업 중")
        return []

    try:
        base = MEMORY_CACHE.get(date_str, [])
        print(f"🔍 캐시 요청: {date_str}, 전체 {len(base)}건")
        filtered = [item for item in base if not favorite or item["golf"] in favorite]
        print(f"🧠 캐시 {date_str} → 필터 후 {len(filtered)}건")
        return filtered
    finally:
        CACHE_LOCK.release()


def get_consolidated_teetime(start, end, hour_range=None, favorite=[]):
    print(f"📅 통합 티타임 조회: {start} ~ {end}, 시간 필터: {hour_range}, 선호: {favorite}")
    consolidated = []
    for d in (start + timedelta(days=i) for i in range((end - start).days + 1)):
        print(f"🔁 날짜 루프 진입: {d.strftime('%Y-%m-%d')}")
        consolidated += get_from_cache(d.strftime("%Y-%m-%d"), favorite)

    by_key = {}
    for it in consolidated:
        try:
            h = int(it["hour_num"]) 
            if hour_range and h not in hour_range:
                continue
        except:
            continue
        k = (it["golf"], it["date"], it["hour"])
        if k not in by_key or it["price"] < by_key[k]["price"]:
            by_key[k] = it

    result = [dict(
        golf=v["golf"],
        date=datetime.strptime(v["date"], "%Y-%m-%d").strftime("%m/%d"),
        hour=v["hour"],
        price=v["price"],
        source=v["source"],
        url=v["url"]
    ) for v in by_key.values()]
    print(f"📤 최종 결과 {len(result)}건 반환")
    return result


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/admin/refresh", methods=["POST"])
def admin_refresh():
    def _refresh_task():
        print("🔧 수동 캐시 갱신 요청 수신됨")
        full_refresh_cache()
    threading.Thread(target=_refresh_task, daemon=True).start()
    return jsonify({"status": "refresh started"})


# ─────────────────────────────────────────────────────────────────────────────
# Render 무료티어용 네트워크 진단 엔드포인트 (/debug)
# - 서버 내부에서 실제 curl을 실행해 응답/타임아웃을 브라우저로 확인
@app.route("/debug")
def debug():
    cmds = [
        ["curl", "-I", "-4", "--connect-timeout", "8", "https://www.golfpang.com"],
        ["curl", "-I", "-6", "--connect-timeout", "8", "https://www.golfpang.com"],
        [
            "curl", "-s", "-o", "/dev/null", "-w", "ajax:%{http_code}\\n",
            "-H", "X-Requested-With: XMLHttpRequest",
            "-H", "Referer: https://www.golfpang.com/web/round/booking.do",
            "-H", "Origin: https://www.golfpang.com",
            "--data", "sector=5&page=1",
            "--connect-timeout", "10", "-m", "20",
            "https://www.golfpang.com/web/round/booking_tblList.do"
        ]
    ]
    out_lines = []
    for c in cmds:
        try:
            res = subprocess.run(c, capture_output=True, text=True)
            out_lines.append(f"$ {' '.join(c)}\\n{res.stdout}{res.stderr}\\n")
        except Exception as e:
            out_lines.append(f"$ {' '.join(c)}\\nERROR: {e}\\n")
    return ("<pre>" + "\\n".join(out_lines) + "</pre>", 200)
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    run_async_refresh_once()
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask 서버 실행 시작: 포트 {port}")
    app.run(host="0.0.0.0", port=port)
