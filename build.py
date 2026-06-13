# -*- coding: utf-8 -*-
"""
config + data/series.json -> output/checklist.html (단일 파일, 데이터 임베드)

보조 의견(참고 의견) 계산:
  지표 월별 시계열로부터
    - 12개월 선형회귀 기울기(방향)
    - 6개월 변화량
    - 5년 범위 내 백분위(고점/바닥 근접)
    - 최근 고점/저점 대비 위치
  를 구해, 문항 유형(상승/하락추세·고점·바닥·반등·역전 등)별로
  '그렇다 / 아니다 / 애매' 3단계 + 근거 수치 한 줄을 만든다.
"""
import json, os, math, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))

def load(p):
    return json.load(open(os.path.join(HERE, p), encoding="utf-8"))

# ---------- 보조 의견 엔진 ----------
def linreg_slope(ys):
    n = len(ys)
    if n < 2: return 0.0
    xs = list(range(n))
    mx = sum(xs)/n; my = sum(ys)/n
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    den = sum((x-mx)**2 for x in xs) or 1e-9
    return num/den

def metrics(points):
    vals = [p["v"] for p in points]
    n = len(vals)
    if n == 0:
        return None
    w5 = vals[-60:] if n >= 60 else vals
    rng = (max(w5) - min(w5)) or 1e-9
    win = vals[-13:] if n >= 13 else vals          # 최근 12개월
    last = vals[-1]
    slope = linreg_slope(win)
    chg_win = win[-1] - win[0]
    chg6 = (last - vals[-7]) if n >= 7 else (last - vals[0])
    chg3 = (last - vals[-4]) if n >= 4 else (last - vals[0])
    pct_rank = (last - min(w5)) / rng * 100.0
    recent_max = max(win); recent_min = min(win)
    # 최근 저점/고점이 며칠 전인지(되돌림 판단)
    imin = max(range(len(win)), key=lambda i: -win[i])
    imax = max(range(len(win)), key=lambda i: win[i])
    return {
        "last": round(last, 2), "rng": rng,
        "slope": slope, "chg_win": chg_win, "chg6": chg6, "chg3": chg3,
        "pct_rank": round(pct_rank, 1),
        "recent_max": recent_max, "recent_min": recent_min,
        "imin_from_end": len(win)-1-imin, "imax_from_end": len(win)-1-imax,
        "rel_win": chg_win/rng, "rel6": chg6/rng,
    }

def fmt(x, unit=""):
    s = f"{x:+.1f}" if abs(x) < 1000 else f"{x:+.0f}"
    return s + unit

def gspc_yoy(points):
    vals = [p["v"] for p in points]
    if len(vals) < 13: return None
    return (vals[-1]/vals[-13]-1)*100.0

def suggest(q, ser):
    """문항 1개에 대한 참고 의견."""
    if ser is None or ser.get("manual") or not ser.get("points"):
        return {"verdict": "수동", "basis": "자동 데이터 없음 — 차트를 직접 보고 판단하세요."}
    pts = ser["points"]; m = metrics(pts)
    if m is None:
        return {"verdict": "수동", "basis": "데이터 부족"}
    unit = "%p" if ser["transform"] in ("yoy",) else ""
    iid = q["indicator_id"]; phase = q["phase"]; types = q["qtypes"]

    votes = []   # (level, reason)  level: 2=yes,1=maybe,0=no
    def add(level, reason): votes.append((level, reason))

    # ---- 주가지수는 낙폭(조정/하락장) 기준으로 별도 판단 ----
    if iid == "gspc":
        dd = (m["last"] - m["recent_max"]) / m["recent_max"] * 100.0
        yoy = gspc_yoy(pts)
        yoy_s = f"YoY {yoy:+.1f}%" if yoy is not None else ""
        near_high = m["last"] >= m["recent_max"] * 0.97
        if phase == "침체":      # 조정/하락장 진행중?
            if dd <= -10: add(2, f"고점대비 {dd:.1f}% (조정/하락장 영역)")
            elif dd <= -4: add(1, f"고점대비 {dd:.1f}% (소폭 조정)")
            else: add(0, f"고점대비 {dd:.1f}% (하락장 아님)")
        elif phase == "회복":    # 저점 이후 반등?
            up_from_low = (m["last"]-m["recent_min"])/m["recent_min"]*100
            if m["imin_from_end"] >= 2 and up_from_low >= 5: add(2, f"최근 저점대비 +{up_from_low:.1f}% 반등")
            elif up_from_low >= 2: add(1, f"저점대비 +{up_from_low:.1f}% (약한 반등)")
            else: add(0, f"저점대비 +{up_from_low:.1f}% (반등 미약)")
        elif phase == "확장":    # 강세장/신고가?
            if (near_high or (yoy or 0) > 10) and (yoy or 0) > 3: add(2, f"강세장({yoy_s}, 고점대비 {dd:.1f}%)")
            elif (yoy or 0) > 0: add(1, f"{yoy_s}, 고점대비 {dd:.1f}%")
            else: add(0, f"{yoy_s} (강세 아님)")
        else:                    # 둔화: 조정 경험/상승폭 둔화?
            if dd <= -5: add(2, f"최근 고점대비 {dd:.1f}% (조정 경험)")
            elif yoy is not None and yoy < 5 and near_high is False: add(1, f"{yoy_s} (상승폭 둔화 가능)")
            else: add(0, f"{yoy_s}, 고점대비 {dd:.1f}%")
        v = max(votes)[0]
        verdict = {2:"그렇다",1:"애매",0:"아니다"}[v]
        return {"verdict": verdict, "basis": "; ".join(r for _,r in votes),
                "metrics": {"last": m["last"], "pct_rank": m["pct_rank"]}}

    base = f"기울기 {m['slope']:+.3f}, 6개월 {fmt(m['chg6'],unit)}, 5년 백분위 {m['pct_rank']:.0f}%"

    for t in types:
        if t == "uptrend":
            if m["rel_win"] > 0.12 and m["chg6"] > 0: add(2, "상승 추세 뚜렷")
            elif m["rel_win"] > 0.04: add(1, "완만한 상승")
            else: add(0, "상승 추세 아님")
        elif t == "downtrend":
            if m["rel_win"] < -0.12 and m["chg6"] < 0: add(2, "하락 추세 뚜렷")
            elif m["rel_win"] < -0.04: add(1, "완만한 하락")
            else: add(0, "하락 추세 아님")
        elif t == "peak":
            if m["pct_rank"] >= 72 and m["chg3"] <= 0: add(2, "고점권 & 꺾임")
            elif m["pct_rank"] >= 72: add(1, "고점권이나 아직 상승")
            else: add(0, f"고점권 아님(백분위 {m['pct_rank']:.0f}%)")
        elif t == "trough":
            if m["pct_rank"] <= 28: add(2, "바닥권")
            elif m["pct_rank"] <= 42: add(1, "바닥 근접")
            else: add(0, f"바닥권 아님(백분위 {m['pct_rank']:.0f}%)")
        elif t == "rebound":
            up = (m["last"]-m["recent_min"]) / (abs(m["recent_min"]) or 1) * 100
            if m["imin_from_end"] >= 2 and m["chg3"] > 0: add(2, "저점 이후 반등 중")
            elif m["chg3"] > 0: add(1, "단기 반등 신호")
            else: add(0, "반등 미확인")
        elif t == "invert":
            mn = min(p["v"] for p in pts[-12:])
            if mn < 0: add(2, f"최근 1년 내 역전(최저 {mn:.2f})")
            else: add(0, f"역전 없음(최저 {mn:.2f})")
        elif t == "low_level":
            if m["pct_rank"] <= 32: add(2, "낮은 수준")
            elif m["pct_rank"] <= 45: add(1, "다소 낮음")
            else: add(0, "낮은 수준 아님")
        elif t == "high_level":
            if m["pct_rank"] >= 68: add(2, "높은 수준")
            elif m["pct_rank"] >= 55: add(1, "다소 높음")
            else: add(0, "높은 수준 아님")
        elif t == "neutral":
            if abs(m["rel_win"]) < 0.06 and abs(m["rel6"]) < 0.06: add(2, "중립/횡보")
            else: add(1, "중립 여부 애매")
        elif t == "drop6m":
            if m["rel6"] < -0.18: add(2, "6개월 내 큰 폭 하락")
            elif m["rel6"] < -0.10: add(1, "6개월 내 하락")
            else: add(0, "급락 아님")
        # 'other' 는 의견 없음

    if not votes:
        return {"verdict": "애매", "basis": base, "metrics": {"pct_rank": m["pct_rank"], "last": m["last"]}}
    v = max(votes)[0]
    verdict = {2:"그렇다",1:"애매",0:"아니다"}[v]
    reasons = "; ".join(r for lv,r in votes if lv == v) or base
    return {"verdict": verdict, "basis": reasons + f"  ({base})",
            "metrics": {"pct_rank": m["pct_rank"], "last": m["last"]}}

# ---------- 빌드 ----------
def build():
    qdoc = load("config/questions.json")
    meta = load("config/indicator_meta.json")
    series = load("data/series.json")
    try:
        asset_returns = load("config/asset_returns.json")
    except FileNotFoundError:
        asset_returns = {}

    ser_by_id = series.get("series", {})
    # 문항별 보조의견 부착
    for q in qdoc["questions"]:
        q["suggest"] = suggest(q, ser_by_id.get(q["indicator_id"]))

    # 임베드 데이터
    app_data = {
        "asof": series.get("asof"),
        "phases": qdoc["phases"],
        "questions": qdoc["questions"],
        "indicators": meta["indicators"],
        "series": ser_by_id,
        "cli": series.get("cli", {}),
        "asset_returns": asset_returns,
        "built_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    tpl = open(os.path.join(HERE, "app_template.html"), encoding="utf-8").read()
    payload = json.dumps(app_data, ensure_ascii=False)
    html = tpl.replace("/*__APP_DATA__*/null", payload)
    # 로컬용(output/checklist.html) + 웹 배포용(site/index.html, GitHub Pages)
    targets = [os.path.join(HERE, "output", "checklist.html"),
               os.path.join(HERE, "site", "index.html")]
    for out in targets:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"생성: output/checklist.html + site/index.html  ({len(html):,} bytes, asof {series.get('asof')})")

if __name__ == "__main__":
    build()
