# -*- coding: utf-8 -*-
"""
엑셀(경기순환체크리스트 예시.xlsx) -> config/questions.json + config/indicator_meta.json

- "체크리스트 문항" 시트 = 68문항 원본
- "지표별 설명" 시트 = 지표별/국면별 특징 + 설명(툴팁용)

가중치 규칙:
  분류명에 "(2점)" 포함 -> 2점
  단, 지표가 '원자재 가격' 이면 예외로 항상 1점
  그 외 -> 1점
"""
import json, os, re
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = r"C:\Users\ydk39\OneDrive\문서\카카오톡 받은 파일\경기순환체크리스트 예시.xlsx"

# 지표 id <-> 데이터 소스 정의 (fetch.py 와 공유)
# transform: yoy(전년대비 %), level(원값), claims4w(4주 이동평균)
INDICATORS = [
    # id,        한글명,                  분류(정규화),  source, code,            transform
    ("gdp",      "실질 GDP",              "총생산",     "fred", "GDPC1",          "yoy"),
    ("indpro",   "산업생산",              "총생산",     "fred", "INDPRO",         "yoy"),
    ("tcu",      "설비가동률",            "총생산",     "fred", "TCU",            "level"),
    ("ism",      "ISM 제조업 PMI",        "총생산",     "manual","ISM",           "level"),
    ("payems",   "비농업 취업자수",       "노동시장",   "fred", "PAYEMS",         "yoy"),
    ("unrate",   "실업률",                "노동시장",   "fred", "UNRATE",         "level"),
    ("icsa",     "주간 실업수당 청구건수","노동시장",   "fred", "ICSA",           "claims4w"),
    ("pi",       "개인 소득",             "소비자",     "fred", "PI",             "yoy"),
    ("umcsent",  "미시간 소비자 심리지수","소비자",     "fred", "UMCSENT",        "level"),
    ("permit",   "주택 건설허가건수",     "주택&건설",  "fred", "PERMIT",         "yoy"),
    ("fedfunds", "기준금리",              "통화량&금리","fred", "FEDFUNDS",       "level"),
    ("m2real",   "실질 M2",               "통화량&금리","fred", "M2REAL",         "yoy"),
    ("t10y2y",   "장단기 금리차",         "통화량&금리","fred", "T10Y2Y",         "level"),
    ("gspc",     "주가지수",              "자산군 측면","yf",   "^GSPC",          "price"),
    ("dgs10",    "장기채 금리",           "자산군 측면","fred", "DGS10",          "level"),
    ("spgsci",   "원자재 가격",           "자산군 측면","yf",   "^SPGSCI",        "price"),
    ("bamlh0a0", "하이일드 스프레드",     "자산군 측면","fred", "BAMLH0A0HYM2",   "level"),
]

# 문항 시트의 지표 표기 -> id (공백/표기 흔들림 흡수)
def norm(s):
    return re.sub(r"\s+", "", str(s)).strip()

NAME2ID = {norm(name): iid for (iid, name, *_ ) in INDICATORS}
# 별칭(시트마다 표기가 다름)
NAME2ID[norm("비농업 취업자 수")] = "payems"
NAME2ID[norm("GSCI 원자재 지수")] = "spgsci"
NAME2ID[norm("원자재")] = "spgsci"

PHASES = ["침체", "회복", "확장", "둔화"]
CAT_NORM = {  # 문항 시트 분류 -> 정규화 분류(결과 집계 단위)
    "총생산 (성장)": "총생산",
    "노동시장": "노동시장",
    "소비자": "소비자",
    "주택&건설": "주택&건설",
    "통화량&금리 (2점)": "통화량&금리",
    "자산군 측면 (2점 / 원자재는 1점)": "자산군 측면",
}

def weight_for(category_raw, indicator_id):
    if indicator_id == "spgsci":   # 원자재는 예외로 1점
        return 1
    return 2 if "(2점" in category_raw else 1

# ---- 문항 유형 추론(보조의견 계산에 사용) ----
def infer_qtype(text, phase):
    t = text
    types = []
    if "역전" in t: types.append("invert")
    if "피크아웃" in t or "고점을 기록" in t or "고점대비" in t: types.append("peak")
    if "바닥" in t or "저점" in t: types.append("trough")
    if "반등" in t: types.append("rebound")
    if "상승 추세" in t or "상승추세" in t or "증가 추세" in t or "상승하" in t or "증가율이 상승" in t: types.append("uptrend")
    if "하락 추세" in t or "하락추세" in t or "감소 추세" in t or "하락하" in t or "하락 중" in t: types.append("downtrend")
    if "낮은 수준" in t: types.append("low_level")
    if "높은 수준" in t: types.append("high_level")
    if "중립" in t or "동결" in t: types.append("neutral")
    if "크게 감소" in t or "크게 하락" in t or "급락" in t or "가파르게 하락" in t: types.append("drop6m")
    if not types:
        types.append("other")
    return types

def main():
    xl = pd.ExcelFile(XLSX)
    q_sheet = [s for s in xl.sheet_names if "문항" in s][0]
    d_sheet = [s for s in xl.sheet_names if "설명" in s][0]
    df = xl.parse(q_sheet, header=None).fillna("")

    questions = []
    for _, row in df.iterrows():
        seq = str(row[0]).strip()
        if not re.fullmatch(r"\d+", seq):
            continue
        cat_raw = str(row[1]).strip()
        phase = str(row[2]).strip()
        ind_name = str(row[3]).strip()
        text = str(row[4]).strip()
        iid = NAME2ID.get(norm(ind_name))
        if iid is None:
            raise SystemExit(f"지표 매칭 실패: {ind_name!r} (순번 {seq})")
        questions.append({
            "seq": int(seq),
            "category": CAT_NORM.get(cat_raw, cat_raw),
            "category_raw": cat_raw,
            "phase": phase,
            "indicator_id": iid,
            "indicator_name": ind_name,
            "text": text,
            "weight": weight_for(cat_raw, iid),
            "qtypes": infer_qtype(text, phase),
        })

    # ---- 지표별 설명 파싱 (툴팁용) ----
    dd = xl.parse(d_sheet, header=None).fillna("")
    meta = {}
    cur = None
    for _, row in dd.iterrows():
        ind_name = str(row[1]).strip()   # B열: 지표
        phase = str(row[9]).strip()      # J열: 국면
        feature = str(row[10]).strip()   # K열: 특징
        desc = str(row[11]).strip()      # L열: 설명
        if ind_name:
            # "실질 GDP (YoY)" 같은 표기에서 핵심명만
            base = re.sub(r"\s*\(.*?\)\s*", "", ind_name).strip()
            iid = NAME2ID.get(norm(base)) or NAME2ID.get(norm(ind_name))
            cur = iid
            if iid:
                meta.setdefault(iid, {"name": ind_name, "desc": "", "phase_features": {}})
                if desc:
                    meta[iid]["desc"] = desc
        if cur and phase in PHASES and feature:
            meta.setdefault(cur, {"name": ind_name, "desc": "", "phase_features": {}})
            meta[cur]["phase_features"][phase] = feature

    # INDICATORS 정의를 meta 에 합치기 (소스/transform)
    out_indicators = []
    for (iid, name, cat, source, code, transform) in INDICATORS:
        m = meta.get(iid, {})
        out_indicators.append({
            "id": iid, "name": name, "category": cat,
            "source": source, "code": code, "transform": transform,
            "desc": m.get("desc", ""),
            "phase_features": m.get("phase_features", {}),
        })

    os.makedirs(os.path.join(HERE, "config"), exist_ok=True)
    with open(os.path.join(HERE, "config", "questions.json"), "w", encoding="utf-8") as f:
        json.dump({"phases": PHASES, "questions": questions}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "config", "indicator_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"indicators": out_indicators}, f, ensure_ascii=False, indent=1)

    # ---- 검증 출력 ----
    print(f"문항 수: {len(questions)}  (기대 68)")
    # 가중치 합계: 각 국면별 max
    from collections import defaultdict
    by_phase = defaultdict(int)
    for q in questions:
        by_phase[q["phase"]] += q["weight"]
    print("국면별 가중치 총합(=만점):", dict(by_phase))
    print("지표 수:", len(out_indicators))
    miss = [i["id"] for i in out_indicators if not i["phase_features"]]
    print("설명 누락 지표:", miss if miss else "없음")

if __name__ == "__main__":
    main()
