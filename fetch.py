# -*- coding: utf-8 -*-
"""
17개 지표의 최근 시계열 수집 -> data/series.json (HTML에 임베드됨)

소스:
  - FRED  : API 키 없이 fredgraph.csv 직접 다운로드
  - yfinance : ^GSPC(주가), ^SPGSCI(원자재, 실패 시 DBC)
  - ISM   : 무료 소스 없음 -> 수동 입력(점수만, 차트 자리엔 안내)

캐시: data/cache/<code>.parquet (원본 보관, 증분 업데이트)
출력: data/series.json
  { "asof": "YYYY-MM-DD",
    "series": { id: {"name","unit","transform","points":[{"d":"YYYY-MM","v":float}, ...],
                     "last":..., "manual":bool} } }
"""
import json, os, io, sys, urllib.request, datetime as dt
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache")
os.makedirs(CACHE, exist_ok=True)

START = "2013-01-01"          # 10년 표시 + YoY 계산 여유분
KEEP_MONTHS = 156             # series.json 에 남길 개월 수(약 13년 → 1/5/10년 보기 지원)

def log(*a): print(*a, file=sys.stderr)

def _fred_key():
    """로컬 키 파일(data/.fred_key) 또는 환경변수 FRED_API_KEY."""
    p = os.path.join(HERE, "data", ".fred_key")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    return os.environ.get("FRED_API_KEY", "").strip()

FRED_KEY = _fred_key()

def fred_csv(code):
    """FRED 공식 API(api.stlouisfed.org)로 단일 시리즈 조회. DataFrame[date,value] 반환.
    (그래프 CSV 호스트 fred.stlouisfed.org 는 일부 망에서 차단되어 API 호스트 사용)"""
    if not FRED_KEY:
        raise RuntimeError("FRED API 키 없음 — data/.fred_key 파일을 만드세요.")
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={code}"
           f"&api_key={FRED_KEY}&file_type=json&observation_start={START}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.loads(r.read().decode("utf-8"))
    obs = j.get("observations", [])
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # 결측 '.' -> NaN
    return df.dropna()

def yf_series(ticker):
    import yfinance as yf
    d = yf.download(ticker, start=START, interval="1mo", progress=False, auto_adjust=True)
    if d is None or len(d) == 0:
        return None
    s = d["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    df = pd.DataFrame({"date": pd.to_datetime(s.index), "value": pd.to_numeric(s.values.ravel(), errors="coerce")})
    return df.dropna()

def to_monthly(df, how="last"):
    s = df.set_index("date")["value"].sort_index()
    if how == "mean":
        m = s.resample("ME").mean()
    else:
        m = s.resample("ME").last()
    return m

def transform_series(df, transform):
    """원본 df -> 월별 표시값 시리즈(pandas Series, index=월말)."""
    if transform == "yoy":
        # 분기/월 모두: 같은 빈도에서 12개월(혹은 4분기) 전 대비.
        s = df.set_index("date")["value"].sort_index()
        # 월/분기 자동: 간격 추정
        freq_days = s.index.to_series().diff().dt.days.median()
        if freq_days and freq_days > 70:      # 분기 데이터
            yoy = (s / s.shift(4) - 1.0) * 100.0
        else:
            ms = s.resample("ME").last()
            yoy = (ms / ms.shift(12) - 1.0) * 100.0
        m = yoy.resample("ME").last().ffill()
        return m
    if transform == "claims4w":
        s = df.set_index("date")["value"].sort_index()
        s4 = s.rolling(4, min_periods=1).mean()
        return s4.resample("ME").last()
    # level / price
    return to_monthly(df, "last")

def build():
    meta = json.load(open(os.path.join(HERE, "config", "indicator_meta.json"), encoding="utf-8"))
    out = {}
    for ind in meta["indicators"]:
        iid, name, source, code, transform = ind["id"], ind["name"], ind["source"], ind["code"], ind["transform"]
        if source == "manual":
            out[iid] = {"name": name, "unit": _unit(transform), "transform": transform,
                        "points": [], "last": None, "manual": True,
                        "note": "무료 데이터 소스 없음 — 차트를 직접 확인하고 점수만 체크하세요."}
            log(f"[manual] {iid} {name}")
            continue
        try:
            if source == "fred":
                raw = fred_csv(code)
            else:  # yf
                raw = yf_series(code)
                if (raw is None or len(raw) == 0) and code == "^SPGSCI":
                    log("  ^SPGSCI 실패 -> DBC 대체")
                    raw = yf_series("DBC"); code = "DBC"
            raw.to_parquet(os.path.join(CACHE, f"{iid}.parquet"))
            ser = transform_series(raw, transform).dropna()
            ser = ser.iloc[-KEEP_MONTHS:]
            points = [{"d": d.strftime("%Y-%m"), "v": round(float(v), 4)} for d, v in ser.items()]
            out[iid] = {"name": name, "unit": _unit(transform), "transform": transform,
                        "code": code, "points": points,
                        "last": points[-1]["v"] if points else None, "manual": False}
            log(f"[ok] {iid:9s} {name:18s} n={len(points):3d} last={out[iid]['last']}")
        except Exception as e:
            # 실패 시 캐시 재사용
            p = os.path.join(CACHE, f"{iid}.parquet")
            if os.path.exists(p):
                raw = pd.read_parquet(p)
                ser = transform_series(raw, transform).dropna().iloc[-KEEP_MONTHS:]
                points = [{"d": d.strftime("%Y-%m"), "v": round(float(v), 4)} for d, v in ser.items()]
                out[iid] = {"name": name, "unit": _unit(transform), "transform": transform,
                            "code": code, "points": points,
                            "last": points[-1]["v"] if points else None, "manual": False,
                            "stale": True}
                log(f"[cache] {iid} {name} (다운로드 실패: {e})")
            else:
                out[iid] = {"name": name, "unit": _unit(transform), "transform": transform,
                            "points": [], "last": None, "manual": False, "error": str(e)}
                log(f"[FAIL] {iid} {name}: {e}")

    # ---- OECD 경기선행지수(CLI) : 매크로 신호등과 동일 소스(FRED, 미국) ----
    # 표준 CLI 시계(clock): 100 위/아래 × 상승/하락 으로 4국면 분류
    cli = {"phase": None, "points": [], "note": ""}
    try:
        raw = fred_csv("USALOLITONOSTSAM")  # OECD CLI, normalised, 미국
        raw.to_parquet(os.path.join(CACHE, "cli.parquet"))
        s = raw.set_index("date")["value"].sort_index().iloc[-KEEP_MONTHS:]
        cli["points"] = [{"d": d.strftime("%Y-%m"), "v": round(float(v), 3)} for d, v in s.items()]
        if len(s) >= 2:
            lvl = float(s.iloc[-1]); rising = float(s.iloc[-1]) >= float(s.iloc[-2])
            if lvl >= 100 and rising:       cli["phase"] = "확장"
            elif lvl >= 100 and not rising: cli["phase"] = "둔화"
            elif lvl < 100 and not rising:  cli["phase"] = "침체"
            else:                           cli["phase"] = "회복"
            cli["level"] = round(lvl, 2); cli["rising"] = rising
        log(f"[ok] cli  OECD CLI  level={cli.get('level')} phase={cli['phase']}")
    except Exception as e:
        log(f"[FAIL] cli: {e}")
        cli["note"] = f"CLI 수집 실패: {e}"

    asof = dt.date.today().isoformat()
    result = {"asof": asof, "start": START, "series": out, "cli": cli}
    with open(os.path.join(HERE, "data", "series.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log(f"\n저장: data/series.json  (asof {asof})")
    return result

def _unit(transform):
    return {"yoy": "% (YoY)", "level": "", "claims4w": "건(4주평균)", "price": "지수"}.get(transform, "")

if __name__ == "__main__":
    build()
